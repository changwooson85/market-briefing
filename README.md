# 📊 손창우님 자동화 봇 (시황 + 영어)

매일 텔레그램으로 시황·영어 학습 콘텐츠 자동 발송. **완전 무료**.

## 📅 발송 스케줄

| 시간 (KST) | 봇 | 요일 | 내용 |
|---|---|---|---|
| **07:00** | 📝 딕테이션 (문제) | 매일 | 5문장 받아쓰기 + 음성 (느린 + 보통 속도) |
| **06:50** | 📊 시황 브리핑 | 평일 | 글로벌·한국 시장 + 수급 분석 |
| **07:30** | 🎙️ 영어 학습 | 매일 | 1분 영어 뉴스 + 학습자료 + 음성 |
| **12:00** | ✅ 딕테이션 (정답) | 매일 | 정답 + 한국어 번역 + 해설 |

> 실제로는 GitHub Actions cron 5~15분 지연이 있어서 위 시간에서 약간 늦게 도착할 수 있습니다.

## 🛠️ 셋업 가이드

### 1. Telegram Bot
이미 완료 ✅

### 2. Gemini API Key
이미 완료 ✅

### 3. GitHub Secrets
이미 완료 ✅

| Name | 용도 |
|---|---|
| `GEMINI_API_KEY` | AI 콘텐츠 생성 |
| `TELEGRAM_BOT_TOKEN` | 메시지 발송 |
| `TELEGRAM_CHAT_ID` | 발송 대상 |

### 4. 신규 추가 봇 활성화
1. zip 풀어서 새 파일들 업로드
2. Actions 탭 → 신규 워크플로우 두 개 (`Daily Dictation (Morning)`, `Daily Dictation (Noon - Answers)`) → **Run workflow**로 테스트
3. 텔레그램 도착 확인

## 📂 파일 구조

```
.
├── briefing.py                              # 시황 브리핑
├── english_lesson.py                        # 영어 학습 (스크립트 + TTS)
├── dictation_morning.py                     # 딕테이션 문제 (07:00)
├── dictation_noon.py                        # 딕테이션 정답 (12:00)
├── dictation_answers/                       # 정답 임시 저장 (자동 생성)
│   └── 2026-05-04.json
├── requirements.txt
├── .github/workflows/
│   ├── daily-briefing.yml                   # 시황
│   ├── daily-english.yml                    # 영어 학습
│   ├── dictation-morning.yml                # 딕테이션 문제
│   └── dictation-noon.yml                   # 딕테이션 정답
└── README.md
```

## 🔄 딕테이션 동작 원리

```
07:00  dictation_morning.py 실행
   ├─▶ Gemini가 5문장 + 해설 생성
   ├─▶ Edge TTS가 mp3 생성 (각 문장 느린 + 보통 속도)
   ├─▶ 텔레그램에 문제 + 음성 발송
   └─▶ dictation_answers/2026-05-04.json 파일로 정답 저장
       └─▶ 자동으로 git commit + push (점심 봇이 읽기 위해)

12:00  dictation_noon.py 실행
   ├─▶ dictation_answers/2026-05-04.json 읽기
   └─▶ 텔레그램에 정답 + 해설 발송
```

## 🎨 커스터마이징

### 딕테이션 — 문장 개수 변경
`dictation_morning.py`의 prompt에서 `5 English dictation sentences` 부분 수정.

### 딕테이션 — 발송 시간 변경
`.github/workflows/dictation-morning.yml`, `dictation-noon.yml`의 cron 수정.

| KST | UTC cron |
|---|---|
| 06:30 | `30 21` |
| 07:00 | `0 22` |
| 07:30 | `30 22` |
| 12:00 | `0 3` |
| 13:00 | `0 4` |
| 18:00 | `0 9` |

> ⚠️ 점심 봇 시간을 바꿀 때 오전 봇보다 *최소 1시간 후*로 잡으세요.

### 음성 속도 조정
`dictation_morning.py`의 `make_dictation_audio` 함수:
```python
slow:   rate="-25%"  # 학습용 느린 속도
normal: rate="-5%"   # 자연스러운 속도
```

### 음성 목소리
`en-US-AriaNeural`(여), `en-US-GuyNeural`(남), `en-GB-SoniaNeural`(영국 여)...

## 💰 비용

| 항목 | 비용 |
|---|---|
| GitHub Actions | 무료 (월 2,000분, 사용량 ~120분) |
| Gemini API | 무료 (일 1,500회, 사용량 일 3회) |
| Edge TTS | 무료, 무제한 |
| Telegram | 무료 |
| **합계** | **0원** |

## 🐛 문제 해결

| 증상 | 해결 |
|---|---|
| 12시에 정답이 "정상 생성되지 않았다"고 옴 | 오전 7시 봇이 실패. Actions 탭에서 로그 확인 |
| 음성 파일이 너무 빠름/느림 | `dictation_morning.py`의 `rate` 값 조정 |
| ffmpeg 관련 에러 | 워크플로우의 `Install ffmpeg` 단계 확인 |
| `permission denied` (git push) | 워크플로우 파일의 `permissions: contents: write` 확인 |

## 📝 면책

본 시스템 콘텐츠는 학습/참고용입니다. 시황은 투자 자문이 아니며 매매 결정 책임은 본인에게 있습니다. 영어 학습 콘텐츠는 AI가 생성한 가상 시나리오입니다.
