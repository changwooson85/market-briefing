"""
손창우님 아침 시황 브리핑 자동화 (Gemini 버전)
매일 06:50 KST에 GitHub Actions에서 실행되어 텔레그램으로 발송
"""
import os
import sys
import requests
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
import google.generativeai as genai

# ─────────────────────────────────────────────
# 환경 변수 (GitHub Secrets에서 주입)
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST)

# Gemini 초기화
genai.configure(api_key=GEMINI_API_KEY)


# ─────────────────────────────────────────────
# 1. 데이터 수집
# ─────────────────────────────────────────────
def fetch_market_data():
    """주요 지수, 환율, 원자재, 채권금리를 yfinance로 수집"""
    tickers = {
        # 미국 지수
        "S&P 500":       "^GSPC",
        "Nasdaq":        "^IXIC",
        "Dow":           "^DJI",
        "Russell 2000":  "^RUT",
        "VIX":           "^VIX",
        "필라델피아 반도체 (SOX)": "^SOX",
        # 채권 금리
        "미국 10년물":   "^TNX",
        "미국 2년물":    "^IRX",
        # 환율 / 원자재
        "원/달러":       "KRW=X",
        "달러 인덱스":   "DX-Y.NYB",
        "WTI":           "CL=F",
        "금":            "GC=F",
        # 암호화폐
        "비트코인":      "BTC-USD",
        # 관심 종목
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
            chg = last - prev
            pct = (chg / prev) * 100
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "—")
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
            chg = last - prev
            pct = (chg / prev) * 100
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "—")
            rows.append(f"- {name}: {last:,.2f} {arrow}{abs(pct):.2f}%")
        except Exception:
            rows.append(f"- {name}: 조회 실패")
    return "\n".join(rows)


def fetch_korea_top_volume():
    """네이버 금융 코스피 거래량 상위 종목"""
    try:
        from bs4 import BeautifulSoup
        url = "https://finance.naver.com/sise/sise_quant.naver?sosok=0"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        rows = []
        table = soup.select_one("table.type_2")
        if not table:
            return "거래량 상위 데이터 조회 실패"

        for tr in table.select("tr")[2:22]:
            tds = tr.select("td")
            if len(tds) < 7:
                continue
            name = tds[1].get_text(strip=True)
            price = tds[2].get_text(strip=True)
            change = tds[4].get_text(strip=True).replace("\n", "").replace("\t", "")
            volume = tds[5].get_text(strip=True)
            if name:
                rows.append(f"- {name}: {price}원 ({change}) 거래량 {volume}")

        return "\n".join(rows[:20]) if rows else "데이터 없음"
    except Exception as e:
        return f"네이버 금융 크롤링 실패: {e}"


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
# 2. Gemini API로 시황 리포트 생성
# ─────────────────────────────────────────────
def generate_briefing(market_data, korea_data, top_volume, news):
    """Gemini에게 시황 리포트 생성 요청"""
    today_str = TODAY.strftime("%Y년 %m월 %d일 (%a)")

    prompt = f"""당신은 한국 개인 투자자를 위한 시황 브리핑 작성자입니다.
아래 데이터를 바탕으로 텔레그램으로 발송할 아침 시황 브리핑을 작성해주세요.

[작성 원칙]
- 한국어로 작성
- 텔레그램에서 읽기 좋게 구성 (이모지 적절히 사용, 너무 길지 않게)
- 투자자 관심사: 반도체(삼성전자/SK하이닉스/SOX), 2차전지(LGES/삼성SDI), 비트코인 관련주(MSTR), AI/빅테크
- 한국 투자자 관점에서 미국 시장 흐름이 한국 시장에 미칠 영향 위주로 해석
- 마지막에 "오늘의 액션 아이템" 3줄 포함
- 투자 자문이 아니며, 매매 결정 책임은 본인에게 있다는 면책 문구 포함
- 글자 수는 3,500자 이내 (텔레그램 메시지 한도 4,096자 고려)

[오늘 날짜]
{today_str}

[글로벌 지수/원자재/채권 시세]
{market_data}

[한국 지수]
{korea_data}

[코스피 거래량 상위 20위 (참고)]
{top_volume}

[주요 뉴스 헤드라인]
{news}

이제 위 데이터를 분석해 아침 시황 브리핑을 작성해주세요. 표보다는 섹션별 정리가 텔레그램에 적합합니다.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────
# 3. 텔레그램 발송
# ─────────────────────────────────────────────
def send_to_telegram(text):
    """텔레그램 봇 API로 본인에게 메시지 발송"""
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

    print("📊 시장 데이터 수집 중...")
    market_data = fetch_market_data()
    korea_data = fetch_korea_indices()

    print("📈 코스피 거래량 상위 수집 중...")
    top_volume = fetch_korea_top_volume()

    print("📰 뉴스 헤드라인 수집 중...")
    news = fetch_news_headlines()

    print("🤖 Gemini로 시황 리포트 생성 중...")
    briefing = generate_briefing(market_data, korea_data, top_volume, news)

    print("📱 텔레그램 발송 중...")
    send_to_telegram(briefing)

    print("✅ 완료")


if __name__ == "__main__":
    main()
