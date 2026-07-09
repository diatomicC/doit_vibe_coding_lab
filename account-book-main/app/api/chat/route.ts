import { GoogleGenerativeAI } from "@google/generative-ai";
import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ExpenseData = {
  date: string;
  amount: number;
  description: string;
};

type ExpenseRecord = ExpenseData & {
  id?: number;
  created_at?: string;
};

type GeminiResponse = {
  message: string;
  expense: ExpenseData | null;
};

type GeminiError = {
  status?: number;
  message?: string;
};

type Intent = "expense" | "query";

const GEMINI_MODELS = [
  "gemini-2.0-flash-lite",
  "gemini-2.5-flash",
  "gemini-2.0-flash",
  "gemini-1.5-flash-8b",
];

function getSupabase() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}

function getDateContext() {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const format = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };

  return { today: format(today), yesterday: format(yesterday) };
}

function classifyIntent(message: string): Intent {
  const trimmed = message.trim();

  const isQuestion =
    /[?？]/.test(trimmed) ||
    /(?:얼마|뭐(?:야|니|지|더라|였|를|가)?|어떻게|어떤|몇\s|가장|제일|총\s*지출|지출(?:이|은)?|썼(?:어|니|나|더라|지|을)?|샀(?:어|니|나|더라|지|을)?|알려|보여|말해|확인|조회|통계|합계|평균|비교|순위|랭킹|내역|목록|리스트|정리|요약|분석|식비|교통비|쇼핑|지난\s*주|이번\s*달|저번\s*달|작년|올해)/.test(
      trimmed,
    );

  const hasAmount =
    /(?:\d{1,3}(?:,\d{3})+|\d{3,})\s*원?|\d+\s*만\s*원?|\d+\s*천\s*원?|\d+(?:\.\d+)?\s*만/.test(
      trimmed,
    );

  if (isQuestion) return "query";
  if (hasAmount) return "expense";
  return "expense";
}

function isValidExpense(expense: unknown): expense is ExpenseData {
  if (!expense || typeof expense !== "object") return false;
  const e = expense as Record<string, unknown>;
  return (
    typeof e.date === "string" &&
    /^\d{4}-\d{2}-\d{2}$/.test(e.date) &&
    typeof e.amount === "number" &&
    Number.isFinite(e.amount) &&
    e.amount > 0 &&
    typeof e.description === "string" &&
    e.description.trim().length > 0
  );
}

function buildExpensePrompt(today: string, yesterday: string) {
  return `당신은 친절한 AI 가계부 챗봇입니다. 사용자의 자연어 메시지에서 지출 정보를 추출합니다.

오늘 날짜: ${today}
어제 날짜: ${yesterday}

## 역할
1. 사용자가 지출을 말하면 date, amount, description을 추출합니다.
2. 정보가 충분하면 확인 메시지를 작성합니다.
3. 날짜나 금액을 파악할 수 없으면 expense는 null로 두고, 부족한 정보를 다시 물어봅니다.

## 규칙
- 항상 한국어로 답변합니다.
- 금액은 원화 정수로 변환합니다 (예: "2만 원" → 20000, "5천원" → 5000).
- "오늘" → ${today}, "어제" → ${yesterday}
- 날짜·금액·내용 중 하나라도 불명확하면 expense를 null로 설정하고 message에서 다시 질문합니다.

## 예시
사용자: "어제 택시 탔는데 2만 원 나왔어."
→ expense: { "date": "${yesterday}", "amount": 20000, "description": "택시" }
→ message: "12월 29일 택시 20,000원을 저장했어요!"

## 응답 형식 (JSON만)
{
  "message": "사용자에게 보여줄 답변",
  "expense": null 또는 { "date": "YYYY-MM-DD", "amount": 정수, "description": "내용" }
}`;
}

function buildQueryPrompt(
  today: string,
  yesterday: string,
  expenses: ExpenseRecord[],
) {
  const expenseJson =
    expenses.length > 0
      ? JSON.stringify(expenses, null, 2)
      : "[] (저장된 지출 없음)";

  return `당신은 친절한 AI 가계부 챗봇입니다. 사용자의 지출 데이터를 분석해 질문에 답합니다.

오늘 날짜: ${today}
어제 날짜: ${yesterday}

## 지출 데이터
${expenseJson}

각 항목: date(YYYY-MM-DD), amount(원), description(내용)

## 규칙
- 항상 한국어로 친근하고 자연스럽게 답변합니다.
- 위 데이터만 근거로 정확히 계산하고 답합니다. 추측하지 않습니다.
- 금액은 천 단위 콤마를 사용합니다 (예: 15,000원).
- 해당 기간/항목에 데이터가 없으면 솔직히 알려줍니다.
- 여러 항목이면 읽기 쉽게 정리해서 알려줍니다.

## 예시 질문과 답변
- "이번 달 총 지출이 얼마야?" → 이번 달 date 기준 amount 합계
- "가장 많이 쓴 항목이 뭐야?" → amount가 가장 큰 항목
- "어제 뭐 샀더라?" → 어제(${yesterday}) date 항목 나열
- "지난주에 얼마 썼어?" → 지난 7일 합계
- "식비로 얼마나 쓰고 있어?" → description에 식사/점심/저녁/식비 등 포함 항목 합계

## 응답 형식 (JSON만)
{
  "message": "사용자에게 보여줄 답변"
}`;
}

function getUserErrorMessage(errors: GeminiError[]): string {
  const hasQuotaError = errors.some((e) => e.status === 429);
  const hasAuthError = errors.some(
    (e) => e.status === 401 || e.status === 403,
  );

  if (hasAuthError) {
    return "Gemini API 키가 올바르지 않습니다. Google AI Studio에서 새 API 키를 발급해 주세요.";
  }
  if (hasQuotaError) {
    return "Gemini API 사용량 한도를 초과했습니다. 1~2분 기다린 후 다시 시도해 주세요.";
  }
  return "AI 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

async function callGemini<T extends { message: string }>(
  apiKey: string,
  systemInstruction: string,
  contents: { role: "user" | "model"; parts: { text: string }[] }[],
): Promise<T> {
  const genAI = new GoogleGenerativeAI(apiKey);
  const errors: GeminiError[] = [];

  for (const modelName of GEMINI_MODELS) {
    try {
      const model = genAI.getGenerativeModel({
        model: modelName,
        systemInstruction,
        generationConfig: {
          responseMimeType: "application/json",
        },
      });

      const result = await model.generateContent({ contents });
      const parsed = JSON.parse(result.response.text()) as T;

      if (!parsed.message || typeof parsed.message !== "string") {
        throw new Error("Invalid response format");
      }

      return parsed;
    } catch (error) {
      const geminiError = error as GeminiError;
      errors.push(geminiError);
      console.error(`Gemini model ${modelName} failed:`, error);

      if (geminiError.status === 401 || geminiError.status === 403) {
        break;
      }
    }
  }

  const userMessage = getUserErrorMessage(errors);
  const err = new Error(userMessage) as Error & { userMessage: string };
  err.userMessage = userMessage;
  throw err;
}

async function fetchAllExpenses(): Promise<ExpenseRecord[]> {
  const supabase = getSupabase();
  const { data, error } = await supabase
    .from("expenses")
    .select("id, date, amount, description, created_at")
    .order("created_at", { ascending: false });

  if (error) {
    console.error("Supabase fetch error:", error);
    return [];
  }

  return data ?? [];
}

export async function POST(req: NextRequest) {
  try {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        {
          error:
            "Gemini API 키가 설정되지 않았습니다. .env.local을 확인해 주세요.",
        },
        { status: 500 },
      );
    }

    const { messages } = (await req.json()) as { messages: ChatMessage[] };

    if (!messages?.length) {
      return NextResponse.json(
        { error: "메시지가 필요합니다." },
        { status: 400 },
      );
    }

    const lastMessage = messages[messages.length - 1];
    if (lastMessage.role !== "user") {
      return NextResponse.json({ error: "잘못된 요청입니다." }, { status: 400 });
    }

    const { today, yesterday } = getDateContext();
    const intent = classifyIntent(lastMessage.content);

    const contents = messages.map((m) => ({
      role: m.role === "user" ? ("user" as const) : ("model" as const),
      parts: [{ text: m.content }],
    }));

    if (intent === "query") {
      const expenses = await fetchAllExpenses();
      const systemInstruction = buildQueryPrompt(today, yesterday, expenses);

      try {
        const parsed = await callGemini<{ message: string }>(
          apiKey,
          systemInstruction,
          contents,
        );

        return NextResponse.json({
          message: parsed.message,
          expense: null,
          savedExpense: null,
          intent: "query",
        });
      } catch (error) {
        const userMessage =
          (error as Error & { userMessage?: string }).userMessage ??
          "AI 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
        return NextResponse.json({ error: userMessage }, { status: 503 });
      }
    }

    const systemInstruction = buildExpensePrompt(today, yesterday);

    let parsed: GeminiResponse;
    try {
      parsed = await callGemini<GeminiResponse>(
        apiKey,
        systemInstruction,
        contents,
      );
    } catch (error) {
      const userMessage =
        (error as Error & { userMessage?: string }).userMessage ??
        "AI 응답을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.";
      return NextResponse.json({ error: userMessage }, { status: 503 });
    }

    const expense = parsed.expense;
    let savedExpense = null;

    if (expense && isValidExpense(expense)) {
      const supabase = getSupabase();

      const { data, error } = await supabase
        .from("expenses")
        .insert({
          date: expense.date,
          amount: Math.round(expense.amount),
          description: expense.description.trim(),
        })
        .select()
        .single();

      if (error) {
        console.error("Supabase insert error:", error);
        return NextResponse.json({
          message:
            "지출 정보는 확인했지만 저장 중 오류가 발생했어요. 다시 시도해 주세요.",
          expense,
          savedExpense: null,
          intent: "expense",
        });
      }

      savedExpense = data;
    }

    return NextResponse.json({
      message: parsed.message,
      expense: savedExpense ? expense : null,
      savedExpense,
      intent: "expense",
    });
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      { error: "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요." },
      { status: 500 },
    );
  }
}
