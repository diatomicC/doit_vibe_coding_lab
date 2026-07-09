import json
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

URL = "https://arxiv.org/abs/2301.00001"
USER_AGENT = "Educational Crawler (contact: 3261127@naver.com)"
ARXIV_ID_PATTERN = re.compile(r"/abs/(\d{4}\.\d{4,5})")


def _strip_label(text: str, label: str) -> str:
    if text.startswith(label):
        return text[len(label) :].strip()
    return text.strip()


def extract_paper_info(url: str) -> dict:
    """arXiv 논문 페이지에서 모든 정보를 추출해 딕셔너리로 반환한다."""
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    match = ARXIV_ID_PATTERN.search(urlparse(url).path)
    arxiv_id = match.group(1) if match else ""

    soup = BeautifulSoup(response.text, "lxml")

    title_el = soup.find("h1", class_="title")
    authors_el = soup.find("div", class_="authors")
    abstract_el = soup.find("blockquote", class_="abstract")
    date_el = soup.find("div", class_="dateline")
    categories_el = soup.find("span", class_="primary-subject")

    authors = []
    if authors_el:
        authors = [a.get_text(strip=True) for a in authors_el.find_all("a")]

    return {
        "arxiv_id": arxiv_id,
        "title": _strip_label(title_el.get_text(strip=True), "Title:") if title_el else "",
        "authors": authors,
        "abstract": _strip_label(abstract_el.get_text(" ", strip=True), "Abstract:") if abstract_el else "",
        "submitted_date": date_el.get_text(" ", strip=True) if date_el else "",
        "categories": categories_el.get_text(" ", strip=True) if categories_el else "",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
    }


def main() -> None:
    paper = extract_paper_info(URL)
    print(json.dumps(paper, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
