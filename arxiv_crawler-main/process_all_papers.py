import re
import time
from pathlib import Path

import pandas as pd

from summarize_paper import summarize_paper

INPUT_PATH = Path(__file__).parent / "papers.csv"
OUTPUT_PATH = Path(__file__).parent / "papers_with_summary.csv"
API_DELAY = 2
MAX_RETRIES = 3

SUMMARY_COLUMNS = [
    "summary_one_line",
    "summary_easy",
    "real_world",
    "limitations",
]


def _format_remaining_time(seconds: float) -> str:
    remaining = max(0, int(seconds))
    minutes, secs = divmod(remaining, 60)
    if minutes > 0:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


def _truncate_title(title: str, max_len: int = 50) -> str:
    if len(title) <= max_len:
        return title
    return title[: max_len - 3] + "..."


def _is_summarized(row: pd.Series) -> bool:
    return bool(str(row.get("summary_one_line", "")).strip())


def _parse_retry_delay(error: Exception) -> float | None:
    match = re.search(r"retry in ([\d.]+)s", str(error), re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1
    return None


def _summarize_with_retry(title: str, abstract: str) -> dict[str, str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return summarize_paper(title, abstract)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise

            wait = _parse_retry_delay(e) or (API_DELAY * attempt * 5)
            print(f"  재시도 {attempt}/{MAX_RETRIES - 1} ({int(wait)}초 대기)...")
            time.sleep(wait)


def process_all_papers(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    delay: float = API_DELAY,
) -> pd.DataFrame:
    if output_path.exists():
        df = pd.read_csv(output_path)
        print(f"기존 결과 로드: {output_path.name}")
    else:
        df = pd.read_csv(input_path)

    for col in SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    total = len(df)
    pending = [i for i in range(total) if not _is_summarized(df.iloc[i])]

    print(f"입력: {input_path.name} ({total}편)")
    print(f"출력: {output_path.name}")
    print(f"요약 필요: {len(pending)}편 | 이미 완료: {total - len(pending)}편\n")

    if not pending:
        print("모든 논문이 이미 요약되었습니다.")
        return df

    start = time.time()

    for done, i in enumerate(pending, start=1):
        row = df.iloc[i]
        title = row["title"]
        short_title = _truncate_title(title)

        print(f"[{done}/{len(pending)}] 요약 중: {short_title}")

        try:
            summary = _summarize_with_retry(title, row["abstract"])
            for col in SUMMARY_COLUMNS:
                df.at[i, col] = summary[col]
            print(f"  → {summary['summary_one_line']}")
            df.to_csv(output_path, index=False)
        except Exception as e:
            print(f"  ✗ 오류: {e}")

        elapsed = time.time() - start
        remaining = (elapsed / done) * (len(pending) - done)
        print(f"  진행: {done}/{len(pending)} | 예상 남은 시간: {_format_remaining_time(remaining)}\n")

        if done < len(pending):
            time.sleep(delay)

    print(f"완료! {output_path.name}에 저장했습니다.")
    return df


if __name__ == "__main__":
    process_all_papers()
