"""
손창우님 매일 영어 딕테이션 (오전 문제 발송)
매일 07:00 KST에 GitHub Actions에서 실행

- AI가 5문장 딕테이션 문제 생성 (난이도 점층)
- Edge TTS로 각 문장 mp3 변환 (느린 속도 + 보통 속도 2번 반복)
- 텔레그램으로 문제 + 음성 발송
- 정답은 별도 파일에 저장 → 점심 봇이 발송
"""
import os
import sys
import json
import asyncio
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import google.generativeai as genai
import edge_tts

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST)
DATE_STR = TODAY.strftime("%Y-%m-%d")

genai.configure(api_key=GEMINI_API_KEY)

# 정답 저장 디렉토리 (리포지토리 안에 커밋되어 점심 봇이 사용)
ANSWERS_DIR = Path("dictation_answers")
ANSWERS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# 1. 딕테이션 문제 생성
# ─────────────────────────────────────────────
def generate_dictation():
    """5문장 딕테이션 문제 생성"""
    weekday = TODAY.weekday()
    today_str = TODAY.strftime("%Y-%m-%d (%a)")
    # 요일별 주제
    themes = {
        0: "Technology / IT (AI, gadgets, tech companies)",
        1: "Economy / Finance (stock market, business, jobs)",
        2: "Daily Life (food, travel, health, relationships)",
        3: "Technology / IT (AI, gadgets, tech companies)",
        4: "Economy / Finance (stock market, business, jobs)",
        5: "Daily Life (food, travel, health, relationships)",
        6: "Daily Life (food, travel, health, relationships)",
    }
    theme = themes[weekday]

    prompt = f"""Create 5 English dictation sentences for an intermediate Korean learner 
(TOEIC 700-1000 level) for {today_str}.

Today's theme: {theme}

Each sentence should be 10-15 words long. Difficulty must increase from #1 to #5:
- #1: Easy everyday expression (clear pronunciation, common words)
- #2: Business basics (slightly more vocabulary)
- #3: News reporting style (formal structure, numbers/dates)
- #4: Includes an idiom or phrasal verb
- #5: Challenge — natural fast speech, contractions (e.g., "I've", "don't"), connected speech

For each sentence, also identify "tricky parts" — places where Korean learners typically 
mishear (silent letters, linking sounds, unstressed syllables, similar-sounding words, etc.)

Return ONLY valid JSON, no markdown:

{{
  "date": "{today_str}",
  "theme": "{theme}",
  "sentences": [
    {{
      "id": 1,
      "level": "easy",
      "text": "<English sentence>",
      "translation_kr": "<한국어 번역>",
      "tricky_parts": [
        {{"part": "<word or phrase from sentence>", "why_kr": "<왜 한국 학습자가 잘못 듣는지 한국어로>"}}
      ],
      "key_vocab": [
        {{"word": "<word>", "meaning_kr": "<한국어 뜻>"}}
      ]
    }}
  ]
}}

Requirements:
- Exactly 5 sentences
- Each sentence: 1-3 tricky_parts, 1-2 key_vocab
- All Korean fields in Korean, all English fields in English
- Sentences must be self-contained (no need for context to understand)
- Avoid politically sensitive content. Use plausible/generic scenarios.
- For sentence #5, use natural contractions like "you're", "they've", "it'll"
"""

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


# ─────────────────────────────────────────────
# 2. 음성 합성 (느린 속도 1회 + 보통 속도 1회)
# ─────────────────────────────────────────────
async def make_dictation_audio(sentences, output_path):
    """
    각 문장을:
    - 번호 안내: "Sentence 1"
    - 느린 속도로 1회 재생 (-25%)
    - 1초 쉼
    - 보통 속도로 1회 재생 (-5%)
    - 다음 문장으로 넘어가기 전 2초 쉼
    """
    voice = "en-US-AriaNeural"

    # SSML 사용해서 한 파일로 합치기
    # edge_tts는 SSML 직접 지원 안 하므로, 파일을 각각 만든 다음 합침
    temp_files = []
    for s in sentences:
        # 인트로
        intro_path = f"/tmp/intro_{s['id']}.mp3"
        intro_text = f"Sentence {s['id']}."
        await edge_tts.Communicate(intro_text, voice, rate="+0%").save(intro_path)
        temp_files.append(intro_path)

        # 느린 속도 (학습용)
        slow_path = f"/tmp/slow_{s['id']}.mp3"
        await edge_tts.Communicate(s["text"], voice, rate="-25%").save(slow_path)
        temp_files.append(slow_path)

        # 보통 속도 (실제 발화 속도)
        normal_path = f"/tmp/normal_{s['id']}.mp3"
        await edge_tts.Communicate(s["text"], voice, rate="-5%").save(normal_path)
        temp_files.append(normal_path)

    # ffmpeg로 합치기
    concat_list = "/tmp/concat_list.txt"
    with open(concat_list, "w") as f:
        for tp in temp_files:
            f.write(f"file '{tp}'\n")

    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", output_path],
        check=True, capture_output=True,
    )

    # 임시 파일 정리
    for tp in temp_files:
        try:
            os.remove(tp)
        except OSError:
            pass


# ─────────────────────────────────────────────
# 3. 텔레그램 메시지 포맷
# ─────────────────────────────────────────────
def format_problem(dictation):
    """오전 문제 발송 메시지 (정답 없이)"""
    parts = []
    parts.append(f"📝 *Daily Dictation* — {DATE_STR}")
    parts.append(f"🎯 Theme: {dictation['theme']}")
    parts.append("━" * 15)
    parts.append("")
    parts.append("🎧 *오디오 파일을 듣고 받아쓰기 해보세요*")
    parts.append("")
    parts.append("• 각 문장은 *느린 속도 → 보통 속도* 순서로 2번 재생됩니다")
    parts.append("• 5문장, 난이도 점층 (#1 쉬움 → #5 도전)")
    parts.append("• 정답은 *오늘 12시*에 발송됩니다")
    parts.append("")
    parts.append("━" * 15)
    parts.append("")

    for s in dictation["sentences"]:
        word_count = len(s["text"].split())
        level_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🟠", "challenge": "🔴"}.get(s["level"], "⚪")
        parts.append(f"{level_emoji} *Sentence #{s['id']}* — {s['level']} ({word_count} words)")
        parts.append("")
        # 빈 줄 5개로 받아쓰기 공간 표시
        parts.append("`______________________________________`")
        parts.append("")

    parts.append("━" * 15)
    parts.append("💡 *Tips*")
    parts.append("• 첫 듣기엔 메모만, 두 번째 들을 때 채워넣기")
    parts.append("• 안 들리면 그 부분 비워두고 다음 문장으로")
    parts.append("• 답 보기 전에 *최소 3번 반복* 권장")

    return "\n".join(parts)


# ─────────────────────────────────────────────
# 4. 텔레그램 발송
# ─────────────────────────────────────────────
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


def send_telegram_audio(audio_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    with open(audio_path, "rb") as f:
        files = {"audio": f}
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption,
            "title": f"Dictation {DATE_STR}",
            "performer": "Daily Dictation Bot",
        }
        resp = requests.post(url, data=data, files=files, timeout=60)
    if resp.status_code != 200:
        print(f"❌ 오디오 발송 실패: {resp.text}", file=sys.stderr)
        sys.exit(1)
    print("✅ 오디오 발송 완료")


# ─────────────────────────────────────────────
# 5. 정답 파일 저장 (점심 봇이 사용)
# ─────────────────────────────────────────────
def save_answers(dictation):
    """정답을 JSON 파일로 저장. 점심 봇이 이걸 읽어서 발송."""
    answer_file = ANSWERS_DIR / f"{DATE_STR}.json"
    with open(answer_file, "w", encoding="utf-8") as f:
        json.dump(dictation, f, ensure_ascii=False, indent=2)
    print(f"✅ 정답 저장: {answer_file}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print(f"📝 딕테이션 문제 생성 시작 — {TODAY.isoformat()}")

    print("🤖 Gemini로 5문장 딕테이션 생성 중...")
    dictation = generate_dictation()
    print(f"   {len(dictation['sentences'])}문장 생성됨")

    print("🎙️ Edge TTS로 음성 생성 중...")
    audio_path = "/tmp/dictation.mp3"
    asyncio.run(make_dictation_audio(dictation["sentences"], audio_path))

    print("📝 메시지 포맷팅...")
    text = format_problem(dictation)

    print("📱 텔레그램 텍스트 발송...")
    send_telegram_text(text)

    print("🎵 텔레그램 오디오 발송...")
    send_telegram_audio(audio_path, f"📝 Dictation {DATE_STR}\n각 문장 느린 속도 → 보통 속도로 2번씩 재생됩니다.")

    print("💾 정답 파일 저장 (점심 봇용)...")
    save_answers(dictation)

    print("✅ 완료")


if __name__ == "__main__":
    main()
