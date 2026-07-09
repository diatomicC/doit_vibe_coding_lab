import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import date
from plotly.subplots import make_subplots

PERIOD_OPTIONS = {
    "1개월": "1mo",
    "3개월": "3mo",
    "6개월": "6mo",
    "1년": "1y",
}

COMPARE_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]


def parse_tickers(ticker_text: str) -> list[str]:
    return [ticker.strip() for ticker in ticker_text.split(",") if ticker.strip()]


def normalize_returns(close_series):
    return (close_series / close_series.iloc[0] - 1) * 100


def fetch_comparison_data(tickers: list[str], period: str) -> list[dict]:
    comparison_data = []
    for ticker in tickers:
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period=period)
        if history.empty:
            continue

        company_name = info.get("longName") or info.get("shortName", ticker)
        comparison_data.append(
            {
                "ticker": ticker,
                "company_name": company_name,
                "returns": normalize_returns(history["Close"]),
            }
        )
    return comparison_data


def create_comparison_chart(comparison_data: list[dict]) -> go.Figure:
    fig = go.Figure()

    for index, item in enumerate(comparison_data):
        color = COMPARE_COLORS[index % len(COMPARE_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=item["returns"].index,
                y=item["returns"],
                mode="lines",
                name=item["company_name"],
                line={"color": color, "width": 2},
                hovertemplate=(
                    f"{item['company_name']}<br>"
                    "날짜: %{x|%Y-%m-%d}<br>"
                    "수익률: %{y:+.2f}%<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="종목 수익률 비교 (시작일 기준)",
        xaxis_title="날짜",
        yaxis_title="수익률 (%)",
        yaxis_ticksuffix="%",
        height=500,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
        showlegend=True,
        legend_title="종목",
    )
    return fig


def format_amount(amount: float, currency: str | None) -> str:
    if currency == "KRW":
        return f"{amount:,.0f} KRW"
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency or ''}".strip()


def get_close_on_date(history, buy_date: date) -> float | None:
    closes_by_date = {idx.date(): close for idx, close in zip(history.index, history["Close"])}
    if buy_date in closes_by_date:
        return closes_by_date[buy_date]

    earlier_dates = [d for d in closes_by_date if d <= buy_date]
    if not earlier_dates:
        return None
    return closes_by_date[max(earlier_dates)]


def calculate_profit(
    history,
    current_price: float | None,
    buy_date: date,
    buy_amount: float,
) -> dict | None:
    buy_price = get_close_on_date(history, buy_date)
    if buy_price is None or buy_price <= 0 or buy_amount <= 0:
        return None

    effective_current_price = current_price or history["Close"].iloc[-1]
    shares = buy_amount / buy_price
    current_value = shares * effective_current_price
    profit = current_value - buy_amount
    return_pct = (current_value / buy_amount - 1) * 100

    return {
        "buy_price": buy_price,
        "current_value": current_value,
        "profit": profit,
        "return_pct": return_pct,
    }


def render_profit_calculator(history, current_price: float | None, currency: str | None) -> None:
    st.sidebar.header("수익률 계산기")

    min_date = history.index.min().date()
    max_date = history.index.max().date()
    default_amount = 1_000_000.0 if currency == "KRW" else 1_000.0
    amount_step = 10_000.0 if currency == "KRW" else 100.0

    buy_date = st.sidebar.date_input(
        "매수 날짜",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )
    buy_amount = st.sidebar.number_input(
        "매수 금액",
        min_value=0.0,
        value=default_amount,
        step=amount_step,
        format="%.0f" if currency == "KRW" else "%.2f",
    )

    result = calculate_profit(history, current_price, buy_date, buy_amount)
    if result is None:
        st.sidebar.warning("수익률을 계산할 수 없습니다. 입력값을 확인해 주세요.")
        return

    color = "#1f77b4" if result["profit"] >= 0 else "#d62728"

    st.sidebar.markdown("**매수 단가**")
    st.sidebar.write(format_price(result["buy_price"], currency))
    st.sidebar.markdown("**현재 가치**")
    st.sidebar.write(format_amount(result["current_value"], currency))
    st.sidebar.markdown(
        f'<p style="color:{color}; font-size: 1.05rem; font-weight: 600;">'
        f"수익률: {result['return_pct']:+.2f}%<br>"
        f"손익: {format_amount(result['profit'], currency)}"
        f"</p>",
        unsafe_allow_html=True,
    )


def format_price(price: float | None, currency: str | None) -> str:
    if price is None:
        return "N/A"
    if currency == "KRW":
        return f"{price:,.0f} KRW"
    if currency == "USD":
        return f"${price:,.2f}"
    return f"{price:,.2f} {currency or ''}".strip()


def get_currency_format(currency: str | None) -> tuple[str, str]:
    if currency == "KRW":
        return "날짜: %{x|%Y-%m-%d}<br>가격: %{y:,.0f}<extra></extra>", ",.0f"
    if currency == "USD":
        return "날짜: %{x|%Y-%m-%d}<br>가격: $%{y:,.2f}<extra></extra>", "$,.2f"
    return "날짜: %{x|%Y-%m-%d}<br>가격: %{y:,.2f}<extra></extra>", ",.2f"


def add_moving_averages(history):
    history = history.copy()
    history["MA20"] = history["Close"].rolling(window=20).mean()
    history["MA60"] = history["Close"].rolling(window=60).mean()
    return history


def add_ma_traces(
    fig,
    history,
    currency: str | None,
    show_ma20: bool,
    show_ma60: bool,
    row: int | None = None,
    col: int | None = None,
) -> None:
    hover_template, _ = get_currency_format(currency)
    use_subplot = row is not None and col is not None

    if show_ma20:
        trace = go.Scatter(
            x=history.index,
            y=history["MA20"],
            mode="lines",
            name="MA20",
            line={"color": "orange", "width": 1.5},
            hovertemplate=hover_template,
        )
        if use_subplot:
            fig.add_trace(trace, row=row, col=col)
        else:
            fig.add_trace(trace)

    if show_ma60:
        trace = go.Scatter(
            x=history.index,
            y=history["MA60"],
            mode="lines",
            name="MA60",
            line={"color": "green", "width": 1.5},
            hovertemplate=hover_template,
        )
        if use_subplot:
            fig.add_trace(trace, row=row, col=col)
        else:
            fig.add_trace(trace)


def create_price_chart(
    history,
    company_name: str,
    currency: str | None,
    show_ma20: bool,
    show_ma60: bool,
) -> go.Figure:
    hover_template, yaxis_tickformat = get_currency_format(currency)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=history.index,
            y=history["Close"],
            mode="lines",
            name="종가",
            line={"width": 2},
            hovertemplate=hover_template,
        )
    )
    add_ma_traces(fig, history, currency, show_ma20, show_ma60)

    fig.update_layout(
        title=f"{company_name} 주가 추이",
        xaxis_title="날짜",
        yaxis_title="가격",
        yaxis_tickformat=yaxis_tickformat,
        height=500,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
        showlegend=show_ma20 or show_ma60,
    )
    return fig


def get_volume_bar_colors(history) -> list[str]:
    volume_threshold = history["Volume"].quantile(0.75)
    colors = []
    for _, row in history.iterrows():
        is_up = row["Close"] >= row["Open"]
        is_high_volume = row["Volume"] >= volume_threshold
        if is_high_volume:
            colors.append("blue" if is_up else "red")
        else:
            colors.append("rgba(100, 149, 237, 0.35)" if is_up else "rgba(220, 20, 60, 0.35)")
    return colors


def create_candlestick_chart(
    history,
    company_name: str,
    currency: str | None,
    show_ma20: bool,
    show_ma60: bool,
) -> go.Figure:
    _, yaxis_tickformat = get_currency_format(currency)
    bar_colors = get_volume_bar_colors(history)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    fig.add_trace(
        go.Candlestick(
            x=history.index,
            open=history["Open"],
            high=history["High"],
            low=history["Low"],
            close=history["Close"],
            increasing_line_color="blue",
            increasing_fillcolor="blue",
            decreasing_line_color="red",
            decreasing_fillcolor="red",
            name="주가",
        ),
        row=1,
        col=1,
    )
    add_ma_traces(fig, history, currency, show_ma20, show_ma60, row=1, col=1)
    fig.add_trace(
        go.Bar(
            x=history.index,
            y=history["Volume"],
            marker_color=bar_colors,
            name="거래량",
            hovertemplate="날짜: %{x|%Y-%m-%d}<br>거래량: %{y:,.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"{company_name} 주가 추이",
        height=650,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        showlegend=show_ma20 or show_ma60,
    )
    fig.update_yaxes(title_text="가격", tickformat=yaxis_tickformat, row=1, col=1)
    fig.update_yaxes(title_text="거래량", tickformat=",.0f", row=2, col=1)
    fig.update_xaxes(title_text="날짜", row=2, col=1)
    return fig


st.set_page_config(page_title="주식 데이터 분석기", layout="wide")

with st.sidebar:
    if "stock_data" in st.session_state:
        stock_data = st.session_state["stock_data"]
        render_profit_calculator(
            stock_data["history"],
            stock_data["current_price"],
            stock_data["currency"],
        )
    else:
        st.header("수익률 계산기")
        st.caption("종목 조회 후 사용할 수 있습니다.")

st.title("주식 데이터 분석기")

ticker = st.text_input(
    "종목 코드 (비교 시 쉼표 구분)",
    value="005930.KS",
    placeholder="예: 005930.KS, 000660.KS",
)
period_label = st.selectbox("기간 선택", list(PERIOD_OPTIONS.keys()))

if st.button("데이터 조회"):
    tickers = parse_tickers(ticker)
    if not tickers:
        st.error("종목 코드를 입력해 주세요.")
    else:
        with st.spinner("데이터를 가져오는 중..."):
            try:
                primary_ticker = tickers[0]
                stock = yf.Ticker(primary_ticker)
                info = stock.info
                history = stock.history(period=PERIOD_OPTIONS[period_label])

                if history.empty:
                    st.error("해당 종목의 데이터를 찾을 수 없습니다. 종목 코드를 확인해 주세요.")
                else:
                    comparison_data = fetch_comparison_data(tickers, PERIOD_OPTIONS[period_label])
                    st.session_state["stock_data"] = {
                        "history": add_moving_averages(history),
                        "company_name": info.get("longName") or info.get("shortName", primary_ticker),
                        "currency": info.get("currency"),
                        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                        "change_percent": info.get("regularMarketChangePercent"),
                        "period_label": period_label,
                        "tickers": tickers,
                        "comparison_data": comparison_data,
                    }
            except Exception as e:
                st.error(f"데이터 조회 중 오류가 발생했습니다: {e}")

if "stock_data" in st.session_state:
    data = st.session_state["stock_data"]
    history = data["history"]
    company_name = data["company_name"]
    currency = data["currency"]
    current_price = data["current_price"]
    change_percent = data["change_percent"]
    period_label = data["period_label"]

    st.success("데이터 조회가 완료되었습니다.")
    st.subheader(company_name)

    col1, col2, col3 = st.columns(3)
    col1.metric("현재가", format_price(current_price, currency))
    if change_percent is not None:
        col2.metric("전일 대비 등락률", f"{change_percent:+.2f}%")
    col3.metric("조회 기간", period_label)

    ma_col1, ma_col2 = st.columns(2)
    show_ma20 = ma_col1.checkbox("20일 이동평균", value=True)
    show_ma60 = ma_col2.checkbox("60일 이동평균", value=True)

    tab_line, tab_candle, tab_compare = st.tabs(["선 차트", "캔들스틱", "종목 비교"])

    with tab_line:
        st.plotly_chart(
            create_price_chart(history, company_name, currency, show_ma20, show_ma60),
            use_container_width=True,
        )

    with tab_candle:
        st.plotly_chart(
            create_candlestick_chart(history, company_name, currency, show_ma20, show_ma60),
            use_container_width=True,
        )

    with tab_compare:
        comparison_data = data.get("comparison_data", [])
        tickers = data.get("tickers", [])

        if len(tickers) < 2:
            st.info("2개 이상의 종목을 쉼표로 구분해 입력하면 수익률 비교 차트를 볼 수 있습니다.")
        elif len(comparison_data) < 2:
            st.error("비교할 수 있는 종목 데이터가 충분하지 않습니다. 종목 코드를 확인해 주세요.")
        else:
            st.plotly_chart(
                create_comparison_chart(comparison_data),
                use_container_width=True,
            )

    st.markdown("### 역사적 데이터")
    display_history = history.copy()
    display_history.index = display_history.index.strftime("%Y-%m-%d")
    st.dataframe(display_history, use_container_width=True)
