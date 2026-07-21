# arXiv Crawler — 요청 프롬프트 정리

---

## 1. 논문 요약 모듈 생성

```
summarize_paper.py 파일을 만들어줘.
Gemini API로 논문을 쉽게 요약하는 함수:
입력: 논문 제목, 초록
출력: 딕셔너리
  - summary_one_line: 한 줄 요약 (20자 이내)
  - summary_easy: 쉬운 설명 (3-4문장, 중학생도 이해 가능)
  - real_world: 현실 적용 (어디에 쓰이는지, 2-3줄)
  - limitations: 한계점 (1-2줄)
프롬프트를 아주 명확하게 작성해서,
항상 같은 형식으로 결과가 나오게 해줘.
Gemini api key는 .env.local에 넣어놨어.
arxiv_papers.csv의 첫 논문으로 테스트하고 결과 보여줘.

최신 gemini api를 리서치해서 가장 싼 모델을 사용해.
```

**결과:** `summarize_paper.py` 생성, 모델 `gemini-2.5-flash-lite` 사용

---

## 2. 일괄 요약 스크립트 생성

```
papers.csv의 모든 논문에 한국어로 된 쉬운 요약 추가하는 스크립트 만들어줘.
process_all_papers.py:
1. papers.csv 읽기
2. 각 논문마다 Gemini로 요약 생성
3. 새 칼럼 추가 (summary_one_line, summary_easy, real_world, limitations)
4. 2초 대기 (API 제한 고려)
5. 진행 상황 표시
6. papers_with_summary.csv로 저장
```

**결과:** `process_all_papers.py` 생성 (이어하기, 재시도, 중간 저장 포함)

---

## 3. Streamlit UI 구현

```
지금까지 만든 모든 기능을 쉽게 사용할 수 있도록 스트림릿으로 UI를 구현해 줘.
```

**결과:** `app.py` 생성 — 대시보드, 논문 크롤링, AI 요약, 논문 탐색 메뉴

---

## 4. 대시보드 UI 수정 (API 표시 제거 + 이모지)

```
제미나이 API 연결됨은 표시 안 해도 돼. 항목(크롤링된 논문, 요약 완료, 요약 대기)마다 적절한 이모지를 추가해 줘.
```

**결과:**
- 📄 크롤링된 논문
- ✅ 요약 완료
- ⏳ 요약 대기
- Gemini API 연결 상태 메트릭 제거

---

## 5. 사이드바·최근 논문 UI 수정

```
사이드바의 설정 항목도 표시 안 해도 돼. 최근 논문 항목에도 적절한 이모지를 추가해 줘.
```

**결과:** 사이드바 설정 섹션 제거, "📚 최근 논문"으로 변경

---

## 6. 사이드바 색상 변경 (1차)

```
사이드바 색상을 밝게 변경해 줘
```

**결과:** 민트→하늘색 그라데이션, 카드형 메뉴 버튼, 하늘색 테두리·그림자

---

## 7. GitHub 저장소 연결 및 푸시

```
깃허브_저장소_주소 이게 내 저장소야. 깃 연결하고 main 브랜치에 푸시해.
```

**결과:** Git 초기화, `.gitignore` 추가, `main` 브랜치 푸시 (`.env.local` 제외)

---

## 8. Streamlit Cloud 배포

```
streamlit에 배포해 줘.
```

**결과:**
- Streamlit secrets 지원 추가
- `.streamlit/config.toml`, `secrets.toml.example` 생성
- GitHub 푸시 및 Streamlit Cloud 배포 페이지 안내


---

# 부록: Gemini 요약 프롬프트 (`summarize_paper.py`)

요청 1번에서 작성된, 논문 요약에 실제로 사용되는 AI 프롬프트입니다.

## 시스템 프롬프트

```
당신은 학술 논문을 일반인에게 쉽게 설명하는 전문가입니다.

반드시 아래 규칙을 지키세요:
1. 입력으로 주어진 논문 제목과 초록만 근거로 사용하세요. 추측하지 마세요.
2. 모든 출력은 한국어로 작성하세요.
3. JSON 스키마의 각 필드 형식을 정확히 따르세요.
4. summary_one_line: 핵심만 담은 한 줄, 20자 이내(공백 포함). 마침표 없이.
5. summary_easy: 중학생도 이해 가능한 쉬운 설명, 정확히 3~4문장.
6. real_world: 실생활·산업·연구에서의 활용 가능성, 2~3줄.
7. limitations: 이 연구의 한계·주의점, 1~2줄.
8. JSON 외 다른 텍스트는 출력하지 마세요.
```

## 사용자 프롬프트 템플릿

```
{SYSTEM_PROMPT}

[논문 제목]
{title}

[논문 초록]
{abstract}

위 논문을 요약하여 JSON으로 응답하세요.
```

## 출력 스키마 (Pydantic)

| 필드 | 설명 |
|------|------|
| `summary_one_line` | 20자 이내 한 줄 요약 (한국어) |
| `summary_easy` | 3~4문장, 중학생 수준 설명 (한국어) |
| `real_world` | 2~3줄, 현실 적용 사례 (한국어) |
| `limitations` | 1~2줄, 한계점 (한국어) |

## 모델

- **`gemini-2.5-flash-lite`** — 2026년 6월 기준 Gemini API 최저가 모델
