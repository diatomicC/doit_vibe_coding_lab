import time
from pathlib import Path

import pandas as pd
import streamlit as st

from crawler import (
    DEFAULT_LIST_URL,
    DEFAULT_OUTPUT_PATH,
    REQUEST_DELAY,
    _load_existing_papers,
    _normalize_arxiv_id,
    _setup_logger,
    crawl_multiple_papers,
    fetch_arxiv_ids,
    fetch_paper,
)
from process_all_papers import (
    API_DELAY,
    INPUT_PATH,
    OUTPUT_PATH,
    SUMMARY_COLUMNS,
    _is_summarized,
    _summarize_with_retry,
    _truncate_title,
)
from summarize_paper import MODEL, _load_api_key, summarize_paper

BASE_DIR = Path(__file__).parent

ARXIV_CATEGORIES = {
    "cs.AI — Artificial Intelligence": "https://arxiv.org/list/cs.AI/recent",
    "cs.CL — Computation and Language": "https://arxiv.org/list/cs.CL/recent",
    "cs.LG — Machine Learning": "https://arxiv.org/list/cs.LG/recent",
    "cs.CV — Computer Vision": "https://arxiv.org/list/cs.CV/recent",
    "stat.ML — Machine Learning (Stats)": "https://arxiv.org/list/stat.ML/recent",
    "cs.NE — Neural and Evolutionary Computing": "https://arxiv.org/list/cs.NE/recent",
}


def _api_key_configured() -> bool:
    try:
        _load_api_key()
        return True
    except ValueError:
        return False


def _load_papers(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"arxiv_id": str})
    if "arxiv_id" in df.columns:
        df["arxiv_id"] = df["arxiv_id"].map(_normalize_arxiv_id)
    return df


def _count_summarized(df: pd.DataFrame) -> int:
    if df.empty or "summary_one_line" not in df.columns:
        return 0
    return sum(1 for _, row in df.iterrows() if _is_summarized(row))


def _render_summary_card(summary: dict) -> None:
    st.markdown(f"**한 줄 요약** · {summary['summary_one_line']}")
    st.markdown("**쉬운 설명**")
    st.info(summary["summary_easy"])
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**현실 적용**")
        st.success(summary["real_world"])
    with col2:
        st.markdown("**한계점**")
        st.warning(summary["limitations"])


def _render_paper_card(row: pd.Series, show_summary: bool = False) -> None:
    title = row.get("title", "제목 없음")
    arxiv_id = row.get("arxiv_id", "")
    url = row.get("url", f"https://arxiv.org/abs/{arxiv_id}")

    with st.expander(f"**{title}**", expanded=False):
        st.caption(f"arXiv ID: `{arxiv_id}` · {row.get('submitted_date', '')}")
        if url:
            st.link_button("arXiv에서 보기", url, use_container_width=False)

        st.markdown("**저자**")
        st.write(row.get("authors", ""))

        st.markdown("**분야**")
        st.write(row.get("subjects", ""))

        st.markdown("**초록**")
        st.write(row.get("abstract", ""))

        if show_summary and _is_summarized(row):
            st.divider()
            _render_summary_card(
                {col: row.get(col, "") for col in SUMMARY_COLUMNS}
            )


def page_dashboard() -> None:
    st.header("대시보드")

    papers_df = _load_papers(INPUT_PATH)
    summary_df = _load_papers(OUTPUT_PATH)

    col1, col2, col3 = st.columns(3)
    col1.metric("📄 크롤링된 논문", len(papers_df))
    col2.metric("✅ 요약 완료", _count_summarized(summary_df))
    col3.metric("⏳ 요약 대기", max(0, len(papers_df) - _count_summarized(summary_df)))

    if not _api_key_configured():
        st.error(
            "Gemini API 키가 설정되지 않았습니다. Streamlit Cloud에서는 "
            "Advanced settings > Secrets에 `GEMINI_API_KEY`를 추가하세요."
        )

    st.subheader("📚 최근 논문")
    display_df = summary_df if not summary_df.empty else papers_df
    if display_df.empty:
        st.info("아직 논문이 없습니다. **논문 크롤링** 페이지에서 시작하세요.")
        return

    for _, row in display_df.head(5).iterrows():
        _render_paper_card(row, show_summary=not summary_df.empty)


def page_crawl() -> None:
    st.header("논문 크롤링")
    st.caption("arXiv 카테고리 목록에서 최신 논문을 수집합니다.")

    col1, col2 = st.columns([2, 1])
    with col1:
        category = st.selectbox(
            "카테고리",
            options=list(ARXIV_CATEGORIES.keys()) + ["직접 입력"],
            index=0,
        )
        if category == "직접 입력":
            list_url = st.text_input("목록 URL", value=DEFAULT_LIST_URL)
        else:
            list_url = ARXIV_CATEGORIES[category]
            st.text_input("목록 URL", value=list_url, disabled=True)

    with col2:
        delay = st.number_input(
            "요청 간격 (초)",
            min_value=3,
            max_value=60,
            value=REQUEST_DELAY,
            help="arXiv 서버 부하를 줄이기 위한 대기 시간입니다.",
        )
        output_path = st.text_input("저장 파일", value=str(DEFAULT_OUTPUT_PATH.name))

    output_file = BASE_DIR / output_path

    if st.button("ID 목록 미리보기", use_container_width=False):
        with st.spinner("목록 페이지를 가져오는 중..."):
            try:
                ids = fetch_arxiv_ids(list_url)
                existing_df = _load_existing_papers(output_file)
                existing_ids = set(existing_df["arxiv_id"]) if not existing_df.empty else set()
                new_ids = [
                    i for i in ids if _normalize_arxiv_id(i) not in existing_ids
                ]
                st.success(f"수집된 ID: {len(ids)}개 · 신규: {len(new_ids)}개 · 기존: {len(existing_ids)}개")
                if new_ids:
                    st.dataframe(
                        pd.DataFrame({"arxiv_id": new_ids}),
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as e:
                st.error(f"목록 조회 실패: {e}")

    st.divider()

    single_id = st.text_input(
        "단일 논문 크롤링 (arXiv ID)",
        placeholder="예: 2606.13670",
    )
    if st.button("단일 논문 가져오기", disabled=not single_id.strip()):
        with st.spinner(f"{single_id} 크롤링 중..."):
            try:
                paper = fetch_paper(single_id.strip())
                st.success("크롤링 완료!")
                st.json(paper)
            except Exception as e:
                st.error(f"크롤링 실패: {e}")

    st.divider()

    if st.button("전체 크롤링 시작", type="primary", use_container_width=True):
        progress = st.progress(0, text="준비 중...")
        status = st.empty()
        log_area = st.empty()

        try:
            ids = fetch_arxiv_ids(list_url)
            existing_df = _load_existing_papers(output_file)
            existing_ids = set(existing_df["arxiv_id"]) if not existing_df.empty else set()
            new_ids = [
                i for i in ids if _normalize_arxiv_id(i) not in existing_ids
            ]

            if not new_ids:
                st.info("새로 크롤링할 논문이 없습니다. 모든 논문이 이미 저장되어 있습니다.")
                return

            status.info(f"총 {len(new_ids)}편 크롤링 예정 (기존 {len(existing_ids)}편 건너뜀)")

            logger = _setup_logger(BASE_DIR / "crawler.log")
            papers: list[dict] = []
            failed: list[str] = []
            total = len(new_ids)

            for idx, arxiv_id in enumerate(new_ids, start=1):
                progress.progress(
                    (idx - 1) / total,
                    text=f"[{idx}/{total}] {arxiv_id} 대기 중... ({delay}초)",
                )
                time.sleep(delay)

                from crawler import fetch_paper_safe

                progress.progress(
                    (idx - 0.5) / total,
                    text=f"[{idx}/{total}] {arxiv_id} 크롤링 중...",
                )
                paper = fetch_paper_safe(arxiv_id, logger)
                if paper:
                    papers.append(paper)
                    log_area.success(f"✓ {arxiv_id}: {paper['title'][:60]}...")
                else:
                    failed.append(_normalize_arxiv_id(arxiv_id))
                    log_area.error(f"✗ {arxiv_id}: 실패")

                progress.progress(idx / total, text=f"[{idx}/{total}] 완료")

            if papers:
                new_df = pd.DataFrame(papers)
                df = pd.concat([existing_df, new_df], ignore_index=True)
                df.to_csv(output_file, index=False)

            status.success(
                f"완료! 성공 {len(papers)}건, 실패 {len(failed)}건 → `{output_file.name}`"
            )
            if papers:
                st.dataframe(pd.DataFrame(papers), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"크롤링 오류: {e}")


def page_summarize() -> None:
    st.header("AI 요약")
    st.caption(f"Gemini 모델: `{MODEL}`")

    if not _api_key_configured():
        st.error(
            "API 키가 필요합니다. Streamlit Cloud에서는 "
            "Advanced settings > Secrets에 `GEMINI_API_KEY`를 추가하세요."
        )
        return

    tab_single, tab_batch = st.tabs(["단일 논문 요약", "일괄 요약"])

    papers_df = _load_papers(INPUT_PATH)

    with tab_single:
        st.subheader("단일 논문 요약")

        mode = st.radio("입력 방식", ["CSV에서 선택", "직접 입력"], horizontal=True)

        title = ""
        abstract = ""

        if mode == "CSV에서 선택":
            if papers_df.empty:
                st.warning("먼저 논문을 크롤링하세요.")
            else:
                options = {
                    f"{row['arxiv_id']} — {_truncate_title(row['title'], 60)}": i
                    for i, row in papers_df.iterrows()
                }
                selected = st.selectbox("논문 선택", options=list(options.keys()))
                row = papers_df.iloc[options[selected]]
                title = row["title"]
                abstract = row["abstract"]
                with st.expander("선택한 논문 미리보기"):
                    st.markdown(f"**{title}**")
                    st.write(abstract[:500] + ("..." if len(abstract) > 500 else ""))
        else:
            title = st.text_input("논문 제목")
            abstract = st.text_area("논문 초록", height=200)

        if st.button("요약 생성", type="primary", disabled=not (title and abstract)):
            with st.spinner("Gemini가 요약을 생성하는 중..."):
                try:
                    result = summarize_paper(title, abstract)
                    st.success("요약 완료!")
                    _render_summary_card(result)
                except Exception as e:
                    st.error(f"요약 실패: {e}")

    with tab_batch:
        st.subheader("일괄 요약")
        st.caption("papers.csv의 모든 논문을 요약하여 papers_with_summary.csv에 저장합니다.")

        summary_df = _load_papers(OUTPUT_PATH)
        total = len(papers_df) if not papers_df.empty else len(summary_df)
        done = _count_summarized(summary_df) if not summary_df.empty else 0
        pending = max(0, total - done)

        col1, col2, col3 = st.columns(3)
        col1.metric("전체", total)
        col2.metric("완료", done)
        col3.metric("남음", pending)

        batch_delay = st.slider(
            "API 호출 간격 (초)",
            min_value=1,
            max_value=10,
            value=API_DELAY,
        )

        if papers_df.empty and summary_df.empty:
            st.warning("요약할 논문이 없습니다. 먼저 크롤링을 실행하세요.")
            return

        if pending == 0:
            st.success("모든 논문이 이미 요약되었습니다!")
            return

        if st.button(f"일괄 요약 시작 ({pending}편)", type="primary", use_container_width=True):
            if OUTPUT_PATH.exists():
                df = pd.read_csv(OUTPUT_PATH)
            else:
                df = papers_df.copy()

            for col in SUMMARY_COLUMNS:
                if col not in df.columns:
                    df[col] = ""

            pending_indices = [i for i in range(len(df)) if not _is_summarized(df.iloc[i])]
            progress = st.progress(0, text="시작...")
            log = st.empty()

            start = time.time()
            for done_count, i in enumerate(pending_indices, start=1):
                row = df.iloc[i]
                short = _truncate_title(row["title"])
                progress.progress(
                    (done_count - 1) / len(pending_indices),
                    text=f"[{done_count}/{len(pending_indices)}] {short}",
                )

                try:
                    summary = _summarize_with_retry(row["title"], row["abstract"])
                    for col in SUMMARY_COLUMNS:
                        df.at[i, col] = summary[col]
                    df.to_csv(OUTPUT_PATH, index=False)
                    log.success(f"✓ {short} → {summary['summary_one_line']}")
                except Exception as e:
                    log.error(f"✗ {short}: {e}")

                progress.progress(done_count / len(pending_indices))

                if done_count < len(pending_indices):
                    time.sleep(batch_delay)

            elapsed = time.time() - start
            st.success(f"일괄 요약 완료! ({int(elapsed)}초 소요) → `{OUTPUT_PATH.name}`")


def page_browse() -> None:
    st.header("논문 탐색")

    has_summary = OUTPUT_PATH.exists() and not _load_papers(OUTPUT_PATH).empty
    has_papers = INPUT_PATH.exists() and not _load_papers(INPUT_PATH).empty

    if not has_papers and not has_summary:
        st.info("표시할 논문이 없습니다.")
        return

    source = st.radio(
        "데이터 소스",
        ["요약 포함 (papers_with_summary.csv)", "원본 (papers.csv)"],
        horizontal=True,
        disabled=not has_summary,
    )

    df = _load_papers(OUTPUT_PATH if "요약" in source and has_summary else INPUT_PATH)
    show_summary = "요약" in source and has_summary

    search = st.text_input("검색 (제목, 저자, 초록)", placeholder="키워드를 입력하세요")
    if search.strip():
        mask = (
            df["title"].str.contains(search, case=False, na=False)
            | df["authors"].str.contains(search, case=False, na=False)
            | df["abstract"].str.contains(search, case=False, na=False)
        )
        if show_summary and "summary_one_line" in df.columns:
            mask |= df["summary_one_line"].str.contains(search, case=False, na=False)
        df = df[mask]

    st.caption(f"{len(df)}편 표시 중")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.download_button(
            "CSV 다운로드",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=OUTPUT_PATH.name if show_summary else INPUT_PATH.name,
            mime="text/csv",
            use_container_width=True,
        )

    for _, row in df.iterrows():
        _render_paper_card(row, show_summary=show_summary)


def _inject_sidebar_styles() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div,
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"],
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            background: linear-gradient(
                165deg,
                #f0fdfa 0%,
                #e0f7fa 35%,
                #e0f2fe 70%,
                #f0f9ff 100%
            ) !important;
        }

        section[data-testid="stSidebar"] {
            border-right: 2px solid #7dd3fc !important;
            box-shadow: 4px 0 18px rgba(14, 165, 233, 0.08) !important;
        }

        section[data-testid="stSidebar"] h1 {
            color: #0e7490 !important;
            font-weight: 700 !important;
        }

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stCaption {
            color: #155e75 !important;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            background: rgba(255, 255, 255, 0.85) !important;
            border: 1px solid #a5f3fc !important;
            border-radius: 10px !important;
            padding: 0.55rem 0.85rem !important;
            margin-bottom: 0.35rem !important;
            transition: all 0.15s ease !important;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            background: #ffffff !important;
            border-color: #38bdf8 !important;
            box-shadow: 0 2px 8px rgba(56, 189, 248, 0.18) !important;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
            background: #ffffff !important;
            border-color: #0ea5e9 !important;
            box-shadow: 0 2px 10px rgba(14, 165, 233, 0.22) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="arXiv Crawler",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_sidebar_styles()

    st.sidebar.title("📄 arXiv Crawler")
    st.sidebar.caption("논문 수집 · AI 요약 · 탐색")

    page = st.sidebar.radio(
        "메뉴",
        ["대시보드", "논문 크롤링", "AI 요약", "논문 탐색"],
        label_visibility="collapsed",
    )

    pages = {
        "대시보드": page_dashboard,
        "논문 크롤링": page_crawl,
        "AI 요약": page_summarize,
        "논문 탐색": page_browse,
    }
    pages[page]()


if __name__ == "__main__":
    main()
