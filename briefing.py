"""
손창우님 아침 시황 브리핑 자동화 (Gemini 버전, 풀 데이터)
매일 06:50 KST에 GitHub Actions에서 실행되어 텔레그램으로 발송

추가 데이터:
- 거래대금 상위 20위 (코스피/코스닥)
- 외국인 순매수 상위 20위
- 기관 순매수 상위 20위
"""
import os
import sys
import requests
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import google.generativeai as genai

# ─────────────────────────────────────────────
# 환경 변수
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST)

genai.configure(api_key=GEMINI_API_KEY)

# 네이버 금융용 공통 헤더
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://finance.naver.com/",
}


# ─────────────────────────────────────────────
# 1. 글로벌 시장 데이터 (yfinance)
# ─────────────────────────────────────────────
def fetch_market_data():
    """주요 지수, 환율, 원자재, 채권금리"""
    tickers = {
        "S&P 500":       "^GSPC",
        "Nasdaq":        "^IXIC",
        "Dow":           "^DJI",
        "Russell 2000":  "^RUT",
        "VIX":           "^VIX",
        "필라델피아 반도체 (SOX)": "^SOX",
        "미국 10년물":   "^TNX",
        "미국 2년물":    "^IRX",
        "원/달러":       "KRW=X",
        "달러 인덱스":   "DX-Y.NYB",
        "WTI":           "CL=F",
        "금":            "GC=F",
        "비트코인":      "BTC-USD",
        "MSTR":          "MSTR",
        "Apple":         "AAPL",
        "NVIDIA":        "NVDA",
        "TSMC":          "TSM",
    }
    rows = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist.empty or len(hist) < 2:
                rows.append(f"- {name}: 데이터 없음")
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            pct = ((last - prev) / prev) * 100
            arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
            rows.append(f"- {name}: {last:,.2f} {arrow}{abs(pct):.2f}%")
        except Exception:
            rows.append(f"- {name}: 조회 실패")
    return "\n".join(rows)


def fetch_korea_indices():
    """코스피, 코스닥"""
    rows = []
    for name, ticker in [("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")]:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist.empty or len(hist) < 2:
                rows.append(f"- {name}: 데이터 없음")
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            pct = ((last - prev) / prev) * 100
            arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
            rows.append(f"- {name}: {last:,.2f} {arrow}{abs(pct):.2f}%")
        except Exception:
            rows.append(f"- {name}: 조회 실패")
    return "\n".join(rows)


# ─────────────────────────────────────────────
# 2. 네이버 금융 크롤링 (한국 시장 수급)
# ─────────────────────────────────────────────
def _parse_naver_table(url, top_n=20, name_idx=1, price_idx=2, change_idx=4, extra_idx=6, extra_label="거래대금"):
    """
    네이버 금융 sise 페이지 공통 파서.
    table.type_2 구조 기반.
    """
    try:
        sess = requests.Session()
        sess.headers.update(NAVER_HEADERS)
        # 메인 먼저 방문하여 쿠키 획득
        sess.get("https://finance.naver.com/", timeout=10)
        resp = sess.get(url, timeout=15)
        resp.encoding = "euc-kr"
        if resp.status_code != 200:
            return f"조회 실패 (HTTP {resp.status_code})"

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.select_one("table.type_2")
        if not table:
            return "테이블 구조 변경됨"

        rows = []
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < max(name_idx, price_idx, change_idx, extra_idx) + 1:
                continue
            name = tds[name_idx].get_text(strip=True)
            if not name or name == "":
                continue
            price = tds[price_idx].get_text(strip=True)
            change = tds[change_idx].get_text(" ", strip=True)
            change = " ".join(change.split())  # 공백 정리
            extra = tds[extra_idx].get_text(strip=True)
            rows.append(f"- {name}: {price}원 ({change}) {extra_label} {extra}")
            if len(rows) >= top_n:
                break

        return "\n".join(rows) if rows else "데이터 없음"
    except Exception as e:
        return f"크롤링 실패: {e}"


def fetch_top_value_kospi():
    """코스피 거래대금 상위 20위"""
    url = "https://finance.naver.com/sise/sise_quant_value.naver?sosok=0"
    return _parse_naver_table(url, top_n=20, extra_idx=6, extra_label="거래대금")


def fetch_top_value_kosdaq():
    """코스닥 거래대금 상위 20위"""
    url = "https://finance.naver.com/sise/sise_quant_value.naver?sosok=1"
    return _parse_naver_table(url, top_n=20, extra_idx=6, extra_label="거래대금")


def fetch_foreign_net_buy():
    """외국인 순매수 상위 20위 (전일 기준)"""
    # 네이버: 외국인/기관 매매현황 페이지
    # https://finance.naver.com/sise/investorDealTrendDay.naver
    # 종목별 순매수 상위는 다른 페이지: sise_deal_rank
    url = "https://finance.naver.com/sise/sise_deal_rank.naver?sosok=01&investor_gubun=9000&type=2"
    try:
        sess = requests.Session()
        sess.headers.update(NAVER_HEADERS)
        sess.get("https://finance.naver.com/", timeout=10)
        resp = sess.get(url, timeout=15)
        resp.encoding = "euc-kr"
        if resp.status_code != 200:
            return f"조회 실패 (HTTP {resp.status_code})"

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.select_one("table.type_5") or soup.select_one("table.type_2")
        if not table:
            return "테이블 구조 변경됨"

        rows = []
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < 5:
                continue
            name = tds[1].get_text(strip=True) if len(tds) > 1 else ""
            if not name:
                continue
            # 컬럼: 종목명 | 현재가 | 전일비 | 등락률 | 매수량 | 매도량 | 순매수량
            price = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            change = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            net_buy = tds[-1].get_text(strip=True) if tds else ""
            rows.append(f"- {name}: {price}원 ({change}) 순매수 {net_buy}주")
            if len(rows) >= 20:
                break
        return "\n".join(rows) if rows else "데이터 없음"
    except Exception as e:
        return f"크롤링 실패: {e}"


def fetch_institution_net_buy():
    """기관 순매수 상위 20위"""
    url = "https://finance.naver.com/sise/sise_deal_rank.naver?sosok=01&investor_gubun=1000&type=2"
    try:
        sess = requests.Session()
        sess.headers.update(NAVER_HEADERS)
        sess.get("https://finance.naver.com/", timeout=10)
        resp = sess.get(url, timeout=15)
        resp.encoding = "euc-kr"
        if resp.status_code != 200:
            return f"조회 실패 (HTTP {resp.status_code})"

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.select_one("table.type_5") or soup.select_one("table.type_2")
        if not table:
            return "테이블 구조 변경됨"

        rows = []
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < 5:
                continue
            name = tds[1].get_text(strip=True) if len(tds) > 1 else ""
            if not name:
                continue
            price = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            change = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            net_buy = tds[-1].get_text(strip=True) if tds else ""
            rows.append(f"- {name}: {price}원 ({change}) 순매수 {net_buy}주")
            if len(rows) >= 20:
                break
        return "\n".join(rows) if rows else "데이터 없음"
    except Exception as e:
        return f"크롤링 실패: {e}"


def fetch_news_headlines():
    """Yahoo Finance 주요 뉴스 헤드라인"""
    try:
        url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^IXIC,AAPL,MSTR,NVDA&region=US&lang=en-US"
        resp = requests.get(url, timeout=10)
        from xml.etree import ElementTree as ET
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:10]
        headlines = [f"- {item.find('title').text}" for item in items if item.find("title") is not None]
        return "\n".join(headlines) if headlines else "뉴스 조회 실패"
    except Exception as e:
        return f"뉴스 조회 실패: {e}"


# ─────────────────────────────────────────────
# 3. Gemini로 시황 리포트 생성
# ─────────────────────────────────────────────
def generate_briefing(market_data, korea_data, top_value_kospi, top_value_kosdaq,
                      foreign_buy, inst_buy, news):
    today_str = TODAY.strftime("%Y년 %m월 %d일 (%a)")

    prompt = f"""당신은 한국 개인 투자자를 위한 시황 브리핑 작성자입니다.
아래 데이터를 바탕으로 텔레그램으로 발송할 아침 시황 브리핑을 작성해주세요.

[작성 원칙]
- 한국어로 작성
- 텔레그램에서 읽기 좋게 구성 (이모지 적절히 사용)
- 투자자 관심사: 반도체(삼성전자/SK하이닉스/SOX), 2차전지(LGES/삼성SDI), 비트코인 관련주(MSTR), AI/빅테크
- 한국 투자자 관점에서 미국 시장 흐름이 한국 시장에 미칠 영향 위주로 해석
- **수급 데이터(거래대금/외국인/기관 순매수) 분석을 반드시 포함** — 어떤 섹터에 자금이 몰리는지, 어떤 종목에 외국인/기관이 동시 매수하는지 등을 짚어줄 것
- 외국인과 기관이 동시에 순매수하는 종목은 별도 강조
- 마지막에 "오늘의 액션 아이템" 3줄 포함
- 투자 자문이 아니며 매매 결정 책임은 본인에게 있다는 면책 문구 포함
- 글자 수는 텔레그램 한 메시지(4,096자)에 들어가도록 3,800자 이내

[오늘 날짜]
{today_str}

[글로벌 지수/원자재/채권 시세]
{market_data}

[한국 지수]
{korea_data}

[코스피 거래대금 상위 20]
{top_value_kospi}

[코스닥 거래대금 상위 20]
{top_value_kosdaq}

[외국인 순매수 상위 20 (전일 기준)]
{foreign_buy}

[기관 순매수 상위 20 (전일 기준)]
{inst_buy}

[주요 뉴스 헤드라인]
{news}

이제 위 데이터를 분석해 아침 시황 브리핑을 작성해주세요. 표보다는 섹션별 정리가 텔레그램에 적합합니다.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# 4. 텔레그램 발송
# ─────────────────────────────────────────────
def send_to_telegram(text):
    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)]
    for i, chunk in enumerate(chunks):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code != 200:
            payload.pop("parse_mode")
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code != 200:
                print(f"❌ 텔레그램 발송 실패: {resp.text}", file=sys.stderr)
                sys.exit(1)
        print(f"✅ 텔레그램 발송 완료 ({i+1}/{len(chunks)})")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print(f"🌅 시황 브리핑 시작 — {TODAY.isoformat()}")

    print("📊 글로벌 시장 데이터 수집 중...")
    market_data = fetch_market_data()
    korea_data = fetch_korea_indices()

    print("💰 코스피 거래대금 상위 수집 중...")
    top_value_kospi = fetch_top_value_kospi()

    print("💰 코스닥 거래대금 상위 수집 중...")
    top_value_kosdaq = fetch_top_value_kosdaq()

    print("🌐 외국인 순매수 상위 수집 중...")
    foreign_buy = fetch_foreign_net_buy()

    print("🏛️ 기관 순매수 상위 수집 중...")
    inst_buy = fetch_institution_net_buy()

    print("📰 뉴스 헤드라인 수집 중...")
    news = fetch_news_headlines()

    print("🤖 Gemini로 시황 리포트 생성 중...")
    briefing = generate_briefing(market_data, korea_data,
                                 top_value_kospi, top_value_kosdaq,
                                 foreign_buy, inst_buy, news)

    print("📱 텔레그램 발송 중...")
    send_to_telegram(briefing)

    print("✅ 완료")


if __name__ == "__main__":
    main()
