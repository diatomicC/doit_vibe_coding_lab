"""애플(AAPL) 주식 데이터 조회 테스트."""

import yfinance as yf

TICKER = "AAPL"


def main() -> None:
    stock = yf.Ticker(TICKER)
    info = stock.info

    company_name = info.get("longName") or info.get("shortName", "N/A")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    change_percent = info.get("regularMarketChangePercent")

    print("=== 애플 주식 정보 ===")
    print(f"회사명: {company_name}")
    print(f"현재가: ${current_price:,.2f}" if current_price else "현재가: N/A")
    if change_percent is not None:
        print(f"전일 대비 등락률: {change_percent:+.2f}%")
    else:
        print("전일 대비 등락률: N/A")

    print("\n=== 최근 1개월 역사적 데이터 (처음 5개 행) ===")
    history = stock.history(period="1mo")
    print(history.head())


if __name__ == "__main__":
    main()
