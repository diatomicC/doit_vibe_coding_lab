import json
import os
from pathlib import Path

import pandas as pd
from google import genai
from pydantic import BaseModel, Field

# 가장 저렴한 Gemini 모델 (2026-06 기준: $0.10/1M input, $0.40/1M output)
MODEL = "gemini-2.5-flash-lite"

ENV_PATH = Path(__file__).parent / ".env.local"
DEFAULT_CSV_PATH = Path(__file__).parent / "arxiv_papers.csv"
FALLBACK_CSV_PATH = Path(__file__).parent / "papers.csv"


class PaperSummary(BaseModel):
    summary_one_line: str = Field(
        description="논문 핵심을 담은 한 줄 요약. 반드시 20자 이내(공백 포함). 한국어."
    )
    summary_easy: str = Field(
        description="중학생도 이해할 수 있는 쉬운 설명. 정확히 3~4문장. 한국어."
    )
    real_world: str = Field(
        description="현실 적용 사례. 어디에 쓰이는지 2~3줄. 한국어."
    )
    limitations: str = Field(
        description="논문의 한계점. 1~2줄. 한국어."
    )


SYSTEM_PROMPT = """당신은 학술 논문을 일반인에게 쉽게 설명하는 전문가입니다.

반드시 아래 규칙을 지키세요:
1. 입력으로 주어진 논문 제목과 초록만 근거로 사용하세요. 추측하지 마세요.
2. 모든 출력은 한국어로 작성하세요.
3. JSON 스키마의 각 필드 형식을 정확히 따르세요.
4. summary_one_line: 핵심만 담은 한 줄, 20자 이내(공백 포함). 마침표 없이.
5. summary_easy: 중학생도 이해 가능한 쉬운 설명, 정확히 3~4문장.
6. real_world: 실생활·산업·연구에서의 활용 가능성, 2~3줄.
7. limitations: 이 연구의 한계·주의점, 1~2줄.
8. JSON 외 다른 텍스트는 출력하지 마세요."""


def _load_api_key() -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "GEMINI_API_KEY":
                return value.strip()

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key

    try:
        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    raise ValueError(
        "GEMINI_API_KEY를 .env.local, 환경변수, 또는 Streamlit secrets에 설정하세요."
    )


def _build_prompt(title: str, abstract: str) -> str:
    return f"""{SYSTEM_PROMPT}

[논문 제목]
{title}

[논문 초록]
{abstract}

위 논문을 요약하여 JSON으로 응답하세요."""


def summarize_paper(title: str, abstract: str) -> dict[str, str]:
    """논문 제목과 초록을 받아 Gemini API로 쉬운 요약을 생성한다.

    Returns:
        dict with keys: summary_one_line, summary_easy, real_world, limitations
    """
    client = genai.Client(api_key=_load_api_key())

    response = client.models.generate_content(
        model=MODEL,
        contents=_build_prompt(title, abstract),
        config={
            "response_mime_type": "application/json",
            "response_schema": PaperSummary,
        },
    )

    summary = PaperSummary.model_validate_json(response.text)
    return summary.model_dump()


def _resolve_csv_path() -> Path:
    if DEFAULT_CSV_PATH.exists():
        return DEFAULT_CSV_PATH
    if FALLBACK_CSV_PATH.exists():
        return FALLBACK_CSV_PATH
    raise FileNotFoundError(
        f"논문 CSV를 찾을 수 없습니다: {DEFAULT_CSV_PATH} 또는 {FALLBACK_CSV_PATH}"
    )


if __name__ == "__main__":
    csv_path = _resolve_csv_path()
    df = pd.read_csv(csv_path)
    first = df.iloc[0]

    print(f"모델: {MODEL}")
    print(f"CSV: {csv_path.name}")
    print(f"논문: {first['title']}\n")

    result = summarize_paper(first["title"], first["abstract"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
