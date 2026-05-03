"""
손창우님 딕테이션 정답 발송 (점심)
매일 12:00 KST에 GitHub Actions에서 실행

오전 봇이 저장한 정답 파일을 읽어 정답 + 한국어 번역 + 해설 발송
"""
import os
import sys
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST)
DATE_STR = TODAY.strftime("%Y-%m-%d")

ANSWERS_DIR = Path("dictation_answers")


def load_answers():
    """오늘 날짜 정답 파일 로드"""
    answer_file = ANSWERS_DIR / f"{DATE_STR}.json"
    if not answer_file.exists():
        print(f"⚠️ 오늘 정답 파일 없음: {answer_file}", file=sys.stderr)
        # 오전 봇이 실패했을 가능성. 오전 봇 다시 실행하라는 안내만 발송
        return None
    with open(answer_file, encoding="utf-8") as f:
        return json.load(f)


def format_answers(dictation):
    """정답 + 해설 메시지"""
    parts = []
    parts.append(f"✅ *Dictation Answers* — {DATE_STR}")
    parts.append("━" * 15)
    parts.append("")
    parts.append("아침에 받으신 딕테이션 정답입니다.")
    parts.append("받아쓴 것과 비교해보세요!")
    parts.append("")
    parts.append("━" * 15)
    parts.append("")

    for s in dictation["sentences"]:
        level_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🟠", "challenge": "🔴"}.get(s["level"], "⚪")
        parts.append(f"{level_emoji} *Sentence #{s['id']}*")
        parts.append("")
        parts.append(f"📝 {s['text']}")
        parts.append("")
        parts.append(f"🇰🇷 {s['translation_kr']}")
        parts.append("")

        if s.get("tricky_parts"):
            parts.append("👂 *Tricky parts*")
            for tp in s["tricky_parts"]:
                parts.append(f"• `{tp['part']}`")
                parts.append(f"  → {tp['why_kr']}")
            parts.append("")

        if s.get("key_vocab"):
            parts.append("📚 *Key vocab*")
            for v in s["key_vocab"]:
                parts.append(f"• *{v['word']}* — {v['meaning_kr']}")
            parts.append("")

        parts.append("━" * 15)
        parts.append("")

    parts.append("🎯 *복습 팁*")
    parts.append("1. 틀린 부분만 다시 들으며 반복 청취")
    parts.append("2. 헷갈렸던 단어 *3번 따라 말하기*")
    parts.append("3. 5문장 전체를 *처음부터 끝까지 셰도잉* 1회")
    parts.append("")
    parts.append("내일도 7시에 만나요 👋")

    return "\n".join(parts)


def format_no_answers_message():
    """오전 봇이 실패했을 때 안내"""
    return (
        f"⚠️ *Dictation* — {DATE_STR}\n\n"
        "오늘 아침 딕테이션 문제가 정상 생성되지 않았습니다.\n"
        "GitHub Actions 로그를 확인해주세요.\n\n"
        "내일 다시 정상 발송됩니다."
    )


def send_telegram_text(text):
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
                print(f"❌ 텍스트 발송 실패: {resp.text}", file=sys.stderr)
                sys.exit(1)
        print(f"✅ 텍스트 발송 ({i+1}/{len(chunks)})")


def main():
    print(f"📨 딕테이션 정답 발송 시작 — {TODAY.isoformat()}")

    dictation = load_answers()
    if dictation is None:
        send_telegram_text(format_no_answers_message())
        return

    text = format_answers(dictation)
    send_telegram_text(text)
    print("✅ 완료")


if __name__ == "__main__":
    main()
