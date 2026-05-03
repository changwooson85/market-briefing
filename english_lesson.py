"""
손창우님 매일 영어 학습 자동화
매일 07:30 KST에 GitHub Actions에서 실행

- AI가 1분짜리 영어 뉴스 스크립트 생성 (테크/금융/일상 로테이션)
- Edge TTS로 mp3 음성 변환
- 텔레그램으로 학습 자료 + 음성 파일 발송
"""
import os
import sys
import json
import random
import asyncio
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import google.generativeai as genai
import edge_tts

# ─────────────────────────────────────────────
# 환경 변수
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST)

genai.configure(api_key=GEMINI_API_KEY)

# 주제 로테이션 (요일별)
TOPICS_BY_WEEKDAY = {
    0: ("Technology / IT", "AI, 반도체, 빅테크, 스타트업, 자율주행, 사이버보안 등에서 하나"),  # 월
    1: ("Economy / Finance", "주식시장, 중앙은행 정책, 환율, 원자재, 실적 발표, 경제 지표 등에서 하나"),  # 화
    2: ("Daily Life / Culture", "건강, 음식, 여행, 라이프스타일, 사회 트렌드 등에서 하나"),  # 수
    3: ("Technology / IT", "AI, 반도체, 빅테크, 스타트업, 자율주행, 사이버보안 등에서 하나"),  # 목
    4: ("Economy / Finance", "주식시장, 중앙은행 정책, 환율, 원자재, 실적 발표, 경제 지표 등에서 하나"),  # 금
    5: ("Daily Life / Culture", "건강, 음식, 여행, 라이프스타일, 사회 트렌드 등에서 하나"),  # 토
    6: ("Daily Life / Culture", "건강, 음식, 여행, 라이프스타일, 사회 트렌드 등에서 하나"),  # 일
}


# ─────────────────────────────────────────────
# 1. Gemini로 영어 학습 자료 생성
# ─────────────────────────────────────────────
def generate_lesson():
    """오늘의 주제로 영어 학습 자료 생성. JSON 형태로 받음."""
    weekday = TODAY.weekday()
    category, topic_hint = TOPICS_BY_WEEKDAY[weekday]
    today_str = TODAY.strftime("%Y-%m-%d (%a)")

    prompt = f"""You are an English teacher creating a daily 1-minute news lesson 
for an intermediate Korean learner (TOEIC 700-1000 level).

Today's category: {category}
Topic hint: {topic_hint}
Today's date: {today_str}

Create a realistic, current-feeling English news script and learning materials.
The script should sound like a real news broadcast (not textbook English).
Use natural collocations and idiomatic expressions appropriate for intermediate learners.

Return ONLY valid JSON with no markdown code fences, no extra text. 
The JSON must have this exact structure:

{{
  "topic_title": "<short English title, e.g. 'Tesla Unveils New Affordable EV'>",
  "category": "{category}",
  "script": "<English news script, ~150 words, ~60 seconds when spoken naturally. Use clear sentences. Should feel current/realistic but does NOT need to reference real specific people or companies if uncertain - prefer plausible scenarios.>",
  "vocabulary": [
    {{"word": "<word/phrase>", "meaning_kr": "<한국어 뜻>", "example": "<example sentence in English from the script or similar context>"}}
  ],
  "grammar_points": [
    {{"point": "<grammar pattern, e.g. 'present perfect: has + p.p.'>", "explanation_kr": "<한국어 설명>", "example": "<example from script>"}}
  ],
  "pronunciation_tips": [
    {{"word": "<word>", "ipa": "<IPA>", "tip_kr": "<한국어 발음 팁>"}}
  ],
  "self_quiz": [
    "<English question 1 about the script>",
    "<English question 2>",
    "<English question 3>"
  ],
  "quiz_answers": [
    "<answer 1 in English>",
    "<answer 2 in English>",
    "<answer 3 in English>"
  ]
}}

Requirements:
- vocabulary: exactly 5 items
- grammar_points: exactly 2 items
- pronunciation_tips: exactly 3 items
- self_quiz: exactly 3 items
- All Korean fields must be in Korean. All English fields in English.
- Script must be safe for general audiences and avoid politically sensitive specific claims.
- Make the script genuinely useful for shadowing practice (clear pacing, natural language).
"""

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)

    text = response.text.strip()
    # 혹시 ```json 펜스가 있으면 제거
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)


# ─────────────────────────────────────────────
# 2. Edge TTS로 mp3 변환
# ─────────────────────────────────────────────
async def text_to_speech(text, output_path, voice="en-US-AriaNeural"):
    """
    Edge TTS로 영어 텍스트를 mp3로 변환.
    voice 옵션:
    - en-US-AriaNeural: 미국식 여성, 뉴스 앵커 톤 (기본)
    - en-US-GuyNeural: 미국식 남성
    - en-GB-SoniaNeural: 영국식 여성
    - en-GB-RyanNeural: 영국식 남성
    """
    # rate="-10%" 로 약간 천천히 읽기 (학습용)
    communicate = edge_tts.Communicate(text, voice, rate="-5%")
    await communicate.save(output_path)


# ─────────────────────────────────────────────
# 3. 학습자료를 텔레그램용 텍스트로 포맷팅
# ─────────────────────────────────────────────
def format_lesson_for_telegram(lesson):
    """JSON 학습자료를 텔레그램 메시지 텍스트로 변환"""
    today_str = TODAY.strftime("%Y-%m-%d (%a)")

    parts = []
    parts.append(f"🌅 *Daily English* — {today_str}")
    parts.append(f"📂 Category: {lesson['category']}")
    parts.append(f"📰 Topic: *{lesson['topic_title']}*")
    parts.append(f"⏱️ ~1 min · Intermediate level")
    parts.append("━" * 15)
    parts.append("")

    parts.append("🎙️ *SCRIPT*")
    parts.append("")
    parts.append(lesson["script"])
    parts.append("")
    parts.append("━" * 15)
    parts.append("")

    parts.append("📚 *Vocabulary (5)*")
    for i, v in enumerate(lesson["vocabulary"], 1):
        parts.append(f"{i}. *{v['word']}* — {v['meaning_kr']}")
        parts.append(f"   _e.g._ {v['example']}")
    parts.append("")

    parts.append("🎯 *Grammar Points*")
    for g in lesson["grammar_points"]:
        parts.append(f"• *{g['point']}*")
        parts.append(f"  → {g['explanation_kr']}")
        parts.append(f"  _e.g._ {g['example']}")
    parts.append("")

    parts.append("🎤 *Pronunciation Tips*")
    for p in lesson["pronunciation_tips"]:
        parts.append(f"• *{p['word']}* {p['ipa']}")
        parts.append(f"  → {p['tip_kr']}")
    parts.append("")

    parts.append("💬 *Self-Quiz*")
    for i, q in enumerate(lesson["self_quiz"], 1):
        parts.append(f"{i}. {q}")
    parts.append("")
    parts.append("_(정답은 음성 파일 캡션에 있어요)_")
    parts.append("")

    parts.append("🎧 *Shadowing 추천*")
    parts.append("1단계: 자막 보며 듣기 ×2")
    parts.append("2단계: 자막 보며 따라 말하기 ×2")
    parts.append("3단계: 자막 없이 따라 말하기 ×3")

    return "\n".join(parts)


def format_quiz_answers(lesson):
    """음성 파일 캡션에 들어갈 정답"""
    parts = ["🎧 Audio · Quiz Answers", ""]
    for i, a in enumerate(lesson["quiz_answers"], 1):
        parts.append(f"{i}. {a}")
    return "\n".join(parts)


# ─────────────────────────────────────────────
# 4. 텔레그램 발송
# ─────────────────────────────────────────────
def send_telegram_text(text):
    """긴 텍스트는 분할 발송"""
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
            # Markdown 파싱 에러 대비 plain text 재시도
            payload.pop("parse_mode")
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code != 200:
                print(f"❌ 텍스트 발송 실패: {resp.text}", file=sys.stderr)
                sys.exit(1)
        print(f"✅ 텍스트 발송 ({i+1}/{len(chunks)})")


def send_telegram_audio(audio_path, caption):
    """mp3 파일 + 캡션(정답) 발송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    with open(audio_path, "rb") as f:
        files = {"audio": f}
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "title": f"Daily English {TODAY.strftime('%Y-%m-%d')}",
            "performer": "Daily English Bot",
        }
        resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code != 200:
        print(f"❌ 오디오 발송 실패: {resp.text}", file=sys.stderr)
        sys.exit(1)
    print("✅ 오디오 발송 완료")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print(f"🌅 영어 학습 자료 생성 시작 — {TODAY.isoformat()}")

    print("🤖 Gemini로 학습 자료 생성 중...")
    lesson = generate_lesson()
    print(f"   토픽: {lesson['topic_title']}")
    print(f"   스크립트 길이: {len(lesson['script'])}자")

    print("🎙️ Edge TTS로 mp3 생성 중...")
    audio_path = "/tmp/lesson.mp3"
    asyncio.run(text_to_speech(lesson["script"], audio_path))
    print(f"   파일: {audio_path}")

    print("📝 텔레그램 메시지 포맷팅...")
    text = format_lesson_for_telegram(lesson)
    quiz_caption = format_quiz_answers(lesson)

    print("📱 텔레그램 텍스트 발송...")
    send_telegram_text(text)

    print("🎵 텔레그램 오디오 발송...")
    send_telegram_audio(audio_path, quiz_caption)

    print("✅ 완료")


if __name__ == "__main__":
    main()
