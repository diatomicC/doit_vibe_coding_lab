import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ARXIV_ID_PATTERN = re.compile(r"arXiv:(\d{4}\.\d{4,5})")
DEFAULT_LIST_URL = "https://arxiv.org/list/cs.AI/recent"
DEFAULT_OUTPUT_PATH = Path(__file__).parent / "papers.csv"
DEFAULT_LOG_PATH = Path(__file__).parent / "crawler.log"
REQUEST_DELAY = 15


def _setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("arxiv_crawler")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def _format_remaining_time(seconds: float) -> str:
    remaining = max(0, int(seconds))
    minutes, secs = divmod(remaining, 60)
    if minutes > 0:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


def fetch_arxiv_ids(url: str = DEFAULT_LIST_URL) -> list[str]:
    """카테고리 목록 페이지에서 최신 논문의 arXiv ID 리스트를 반환한다."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    ids: list[str] = []

    for dt in soup.find_all("dt"):
        match = ARXIV_ID_PATTERN.search(dt.get_text())
        if match:
            ids.append(match.group(1))

    return ids


def _strip_label(text: str, label: str) -> str:
    if text.startswith(label):
        return text[len(label) :].strip()
    return text.strip()


def _normalize_arxiv_id(arxiv_id: str) -> str:
    """CSV float 변환 등으로 손실된 trailing zero를 복원한다."""
    prefix, suffix = str(arxiv_id).strip().split(".", 1)
    while len(suffix) < 5:
        suffix += "0"
    return f"{prefix}.{suffix}"


def _load_existing_papers(output_path: Path) -> pd.DataFrame:
    if not output_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(output_path, dtype={"arxiv_id": str})
    df["arxiv_id"] = df["arxiv_id"].map(_normalize_arxiv_id)
    return df.drop_duplicates(subset="arxiv_id", keep="first").reset_index(drop=True)


def _parse_paper_html(soup: BeautifulSoup, arxiv_id: str, url: str) -> dict[str, str]:
    title_el = soup.find("h1", class_="title")
    authors_el = soup.find("div", class_="authors")
    abstract_el = soup.find("blockquote", class_="abstract")
    subjects_el = soup.find("td", class_="tablecell subjects")
    date_el = soup.find("div", class_="dateline")

    if title_el is None:
        raise ValueError("제목(h1.title)을 찾을 수 없습니다.")

    return {
        "arxiv_id": _normalize_arxiv_id(arxiv_id),
        "title": _strip_label(title_el.get_text(strip=True), "Title:"),
        "authors": _strip_label(authors_el.get_text(" ", strip=True), "Authors:") if authors_el else "",
        "abstract": _strip_label(abstract_el.get_text(" ", strip=True), "Abstract:") if abstract_el else "",
        "subjects": subjects_el.get_text(" ", strip=True) if subjects_el else "",
        "submitted_date": date_el.get_text(" ", strip=True) if date_el else "",
        "url": url,
    }


def fetch_paper(arxiv_id: str) -> dict[str, str]:
    """arXiv ID로 논문 상세 페이지를 크롤링한다."""
    url = f"https://arxiv.org/abs/{arxiv_id}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    return _parse_paper_html(soup, arxiv_id, url)


def fetch_paper_safe(
    arxiv_id: str,
    logger: logging.Logger,
) -> dict[str, str] | None:
    """오류를 처리하며 논문 1건을 크롤링한다. 실패 시 None을 반환한다."""
    url = f"https://arxiv.org/abs/{arxiv_id}"
    normalized_id = _normalize_arxiv_id(arxiv_id)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        logger.error("HTTP 오류 | arxiv_id=%s | status=%s | %s", normalized_id, status, exc)
        return None
    except requests.RequestException as exc:
        logger.error("네트워크 오류 | arxiv_id=%s | %s", normalized_id, exc)
        return None

    try:
        soup = BeautifulSoup(response.text, "lxml")
        paper = _parse_paper_html(soup, arxiv_id, url)
    except (ValueError, AttributeError) as exc:
        logger.error("파싱 오류 | arxiv_id=%s | %s", normalized_id, exc)
        return None

    logger.info("크롤링 성공 | arxiv_id=%s | title=%s", normalized_id, paper["title"])
    return paper


def crawl_multiple_papers(
    arxiv_ids: list[str],
    delay: float = REQUEST_DELAY,
    log_path: str | Path = DEFAULT_LOG_PATH,
) -> tuple[list[dict[str, str]], list[str]]:
    """여러 논문을 안전하게 크롤링한다. (성공 목록, 실패 ID 목록)을 반환한다."""
    logger = _setup_logger(Path(log_path))
    total = len(arxiv_ids)
    papers: list[dict[str, str]] = []
    failed_ids: list[str] = []

    if total == 0:
        logger.info("크롤링할 논문이 없습니다.")
        return papers, failed_ids

    logger.info("크롤링 시작 | 총 %d건 | 요청 간격 %d초", total, int(delay))
    start_time = datetime.now()

    for index, arxiv_id in enumerate(arxiv_ids, start=1):
        remaining_count = total - index + 1
        remaining_seconds = remaining_count * delay
        remaining_time = _format_remaining_time(remaining_seconds)

        print(
            f"[{index}/{total}] 대기 중... ({delay}초) | "
            f"arxiv_id={arxiv_id} | 예상 남은 시간: {remaining_time}"
        )
        time.sleep(delay)

        print(f"[{index}/{total}] 크롤링 중: {arxiv_id}")
        paper = fetch_paper_safe(arxiv_id, logger)

        if paper:
            papers.append(paper)
        else:
            failed_ids.append(_normalize_arxiv_id(arxiv_id))
            print(f"[{index}/{total}] 실패: {arxiv_id}")

    elapsed = datetime.now() - start_time
    logger.info(
        "크롤링 완료 | 성공 %d건 | 실패 %d건 | 소요 시간 %s",
        len(papers),
        len(failed_ids),
        str(timedelta(seconds=int(elapsed.total_seconds()))),
    )
    print(
        f"크롤링 완료: 성공 {len(papers)}건, 실패 {len(failed_ids)}건 | "
        f"소요 시간 {str(timedelta(seconds=int(elapsed.total_seconds())))}"
    )

    return papers, failed_ids


def crawl_papers(
    list_url: str = DEFAULT_LIST_URL,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    delay: float = REQUEST_DELAY,
    log_path: str | Path = DEFAULT_LOG_PATH,
) -> pd.DataFrame:
    """ID 목록을 수집하고 논문을 크롤링한 뒤 DataFrame으로 반환하고 CSV에 저장한다."""
    output_path = Path(output_path)
    arxiv_ids = fetch_arxiv_ids(list_url)

    existing_df = _load_existing_papers(output_path)
    existing_ids = set(existing_df["arxiv_id"]) if not existing_df.empty else set()

    new_ids = [arxiv_id for arxiv_id in arxiv_ids if _normalize_arxiv_id(arxiv_id) not in existing_ids]
    skipped_count = len(arxiv_ids) - len(new_ids)

    print(f"수집된 ID: {len(arxiv_ids)}개 | 기존 저장: {len(existing_ids)}건")
    if skipped_count > 0:
        print(f"{len(arxiv_ids)}개 중 {skipped_count}개는 이미 있어서 건너뜀")
    elif existing_ids:
        print(f"{len(arxiv_ids)}개 모두 새로운 논문입니다.")
    else:
        print("기존 papers.csv가 없어 전체를 새로 크롤링합니다.")

    new_papers, failed_ids = crawl_multiple_papers(new_ids, delay=delay, log_path=log_path)

    if failed_ids:
        print(f"실패한 논문 ID: {', '.join(failed_ids)}")

    if new_papers:
        new_df = pd.DataFrame(new_papers)
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = existing_df
        if not new_ids:
            print("새로 크롤링할 논문이 없습니다.")

    df.to_csv(output_path, index=False)
    print(f"저장 완료: {output_path} (총 {len(df)}건, 이번에 추가 {len(new_papers)}건)")

    return df


if __name__ == "__main__":
    crawl_papers()
