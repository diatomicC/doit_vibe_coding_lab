"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabase";

type Expense = {
  id: number;
  created_at: string;
  date: string;
  amount: number;
  description: string;
};

type Message = {
  role: "user" | "assistant";
  content: string;
};

const WELCOME_MESSAGE =
  "안녕하세요! AI 가계부 챗봇입니다 😊\n\n📝 지출 기록: \"오늘 점심 8500원\", \"어제 택시 2만원\"\n📊 통계 질문: \"이번 달 총 지출이 얼마야?\", \"가장 많이 쓴 항목이 뭐야?\"";

export default function Home() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: WELCOME_MESSAGE },
  ]);
  const [input, setInput] = useState("");
  const [loadingExpenses, setLoadingExpenses] = useState(true);
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchExpenses();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function fetchExpenses() {
    setLoadingExpenses(true);
    const { data, error } = await supabase
      .from("expenses")
      .select("*")
      .order("created_at", { ascending: false });

    if (!error && data) {
      setExpenses(data);
    }
    setLoadingExpenses(false);
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const userMessage: Message = { role: "user", content: text };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: updatedMessages }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              data.error ??
              "오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
          },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message },
      ]);

      if (data.savedExpense) {
        setExpenses((prev) => [data.savedExpense, ...prev]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "네트워크 오류가 발생했습니다. 다시 시도해 주세요.",
        },
      ]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  const formatAmount = (value: number) =>
    new Intl.NumberFormat("ko-KR").format(value);

  const formatDate = (value: string) => {
    const [year, month, day] = value.split("-");
    return `${year}.${month}.${day}`;
  };

  return (
    <div className="flex h-dvh w-full flex-col bg-zinc-100">
      <header className="shrink-0 border-b border-zinc-200/80 bg-white px-4 py-4 sm:px-6">
        <h1 className="text-center text-lg font-semibold text-zinc-900 sm:text-base">
          AI 가계부 챗봇
        </h1>
      </header>

      <section className="shrink-0 border-b border-zinc-200/60 bg-zinc-50 px-4 py-3 sm:px-6">
        <p className="mb-2.5 text-xs font-medium text-zinc-400">지출 내역</p>
        {loadingExpenses ? (
          <p className="py-2 text-sm text-zinc-400">불러오는 중...</p>
        ) : expenses.length === 0 ? (
          <p className="py-2 text-sm text-zinc-400">
            아직 기록된 지출이 없습니다.
          </p>
        ) : (
          <div className="flex gap-2.5 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {expenses.map((expense) => (
              <div
                key={expense.id}
                className="min-w-[148px] shrink-0 rounded-xl bg-white px-4 py-3"
              >
                <p className="truncate text-sm font-medium text-zinc-900">
                  {expense.description}
                </p>
                <p className="mt-1 font-mono text-base font-semibold tabular-nums text-zinc-900">
                  {formatAmount(expense.amount)}
                  <span className="ml-0.5 text-xs font-normal text-zinc-400">
                    원
                  </span>
                </p>
                <p className="mt-1 text-xs text-zinc-400">
                  {formatDate(expense.date)}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
          <div className="mx-auto flex max-w-lg flex-col gap-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-[15px] leading-relaxed sm:text-sm ${
                    msg.role === "user"
                      ? "rounded-br-sm bg-[#FEE500] text-zinc-900"
                      : "rounded-bl-sm bg-white text-zinc-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm bg-white px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-300 [animation-delay:0ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-300 [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-300 [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <form
          onSubmit={handleSend}
          className="shrink-0 border-t border-zinc-200/80 bg-white px-4 py-3 sm:px-6"
        >
          <div className="mx-auto flex max-w-lg items-center gap-2.5">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="메시지를 입력하세요"
              disabled={sending}
              className="min-h-12 flex-1 rounded-full bg-zinc-100 px-5 text-base text-zinc-900 outline-none placeholder:text-zinc-400 focus:bg-zinc-50 focus:ring-1 focus:ring-zinc-300 disabled:opacity-50 sm:min-h-10 sm:text-sm"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-blue-600 text-white transition hover:bg-blue-700 disabled:opacity-40 sm:h-10 sm:w-10"
              aria-label="전송"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="h-5 w-5"
              >
                <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
