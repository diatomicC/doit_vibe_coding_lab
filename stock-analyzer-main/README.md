# 주식 데이터 분석기

yfinance와 Streamlit으로 만든 주식 데이터 분석 웹 앱입니다. 종목 조회, 차트 분석, 종목 비교, 수익률 계산 기능을 제공합니다.

## 주요 기능

- **종목 조회**: Yahoo Finance API(yfinance)로 주가 데이터 조회
- **선 차트**: 종가 추이 및 20일/60일 이동평균선
- **캔들스틱 차트**: OHLC 캔들 차트 + 거래량 막대 그래프
- **종목 비교**: 여러 종목을 시작일 기준 수익률(%)로 정규화해 비교
- **수익률 계산기**: 매수 날짜·금액 기준 현재 가치와 손익 계산

## 기술 스택

- Python
- [Streamlit](https://streamlit.io/)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [Plotly](https://plotly.com/python/)

## 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd stock_analyzer

# 가상 환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 실행 방법

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

## 사용 예시

### 단일 종목 조회

```
005930.KS
```

### 여러 종목 비교

```
005930.KS, 000660.KS
```

### 해외 종목

```
AAPL
```

## 프로젝트 구조

```
stock_analyzer/
├── app.py                 # Streamlit 메인 앱
├── test_apple_stock.py    # yfinance 테스트 스크립트
├── requirements.txt       # Python 의존성
├── README.md
└── .gitignore
```

## 참고 사항

- 주가 데이터는 Yahoo Finance를 통해 제공되며, 실시간 데이터와 차이가 있을 수 있습니다.
- 투자 참고용 도구이며, 실제 투자 결정에 대한 책임은 사용자에게 있습니다.
