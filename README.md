# 📊 손창우님 아침 시황 브리핑 자동화 (Gemini 버전)

매일 아침 06:50 KST에 텔레그램으로 시황 브리핑을 자동 발송합니다. **완전 무료**.

## 🎯 받게 되는 내용

- 미국/한국 주요 지수 마감 시세
- 채권 금리 (미 10년물, 2년물)
- 환율 / 원자재 / 비트코인
- 관심 종목 시세 (MSTR, AAPL, NVDA, TSM 등)
- 코스피 거래량 상위 20종목
- 주요 뉴스 헤드라인
- Gemini AI가 작성한 한국어 시황 분석 + 액션 아이템

## 💰 비용: 완전 무료

| 항목 | 무료 한도 |
|---|---|
| GitHub Actions | 월 2,000분 (사용량 1분 미만) |
| Gemini API | 분당 15회, 일 1,500회 (사용량 1회) |
| 텔레그램 | 무제한 |

## 🛠️ 사전 준비

### 1. 텔레그램 봇 (이미 완료)
- ✅ 봇 토큰
- ✅ Chat ID

### 2. Gemini API 키 발급 (3분, 무료)
1. https://aistudio.google.com/apikey 접속
2. Google 계정 로그인
3. **Create API key** 클릭
4. **Create API key in new project** 또는 기존 프로젝트 선택
5. 생성된 키 복사 (`AIza...` 형식)
   - ⚠️ 이 키는 한 번만 보여주므로 메모장에 임시 저장
6. **결제 카드 등록 불필요** (무료 티어로 사용)

## 🚀 GitHub 셋업

### 1. 리포지토리 생성
1. https://github.com/new
2. Repository name: `market-briefing`
3. **Private** 권장
4. Create repository

### 2. 코드 업로드
**방법 A — 웹 드래그**:
1. 빈 리포지토리 화면에서 **uploading an existing file** 링크 클릭
2. 파일들을 드래그:
   - `briefing.py`
   - `requirements.txt`
   - `.gitignore`
   - `README.md`
   - `.github` 폴더 (통째로!)
3. **Commit changes**

**방법 B — 명령어**:
```bash
cd 압축푼폴더
git init
git add .
git commit -m "Initial"
git branch -M main
git remote add origin https://github.com/<본인id>/market-briefing.git
git push -u origin main
```

### 3. Secrets 등록
**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
|---|---|
| `GEMINI_API_KEY` | `AIza...` (Google AI Studio에서 받은 키) |
| `TELEGRAM_BOT_TOKEN` | `8796837948:AAE...` (revoke 후 받은 새 토큰) |
| `TELEGRAM_CHAT_ID` | 본인 Chat ID 숫자 |

### 4. 동작 테스트
1. **Actions** 탭 → 최초 진입 시 활성화 버튼 클릭
2. 좌측 **Daily Market Briefing** 선택
3. 우측 **Run workflow** 버튼 → Run workflow
4. 1~2분 후 텔레그램 확인

## ⏰ 실행 시간 변경

`.github/workflows/daily-briefing.yml`의 cron 부분 수정:

```yaml
- cron: '50 21 * * 0-4'  # KST 06:50, 평일
```

| 원하는 KST | UTC cron |
|---|---|
| 06:00 평일 | `0 21 * * 0-4` |
| 06:30 평일 | `30 21 * * 0-4` |
| 07:00 평일 | `0 22 * * 0-4` |
| 07:30 평일 | `30 22 * * 0-4` |

> ⚠️ GitHub Actions cron은 5~15분 지연될 수 있음. 원하는 시간보다 5분 일찍 설정 권장.

## 🎨 커스터마이징

### 관심 종목 추가/제거
`briefing.py`의 `tickers` 딕셔너리 수정:
```python
"삼성전자":   "005930.KS",
"SK하이닉스": "000660.KS",
"LGES":      "373220.KS",
```

### 모델 변경 (더 똑똑하게)
`briefing.py`에서:
```python
model = genai.GenerativeModel("gemini-2.5-flash")  # 빠르고 무료
# →
model = genai.GenerativeModel("gemini-2.5-pro")    # 더 똑똑 (무료 티어 작음)
```

## 🐛 문제 해결

### 텔레그램 메시지가 안 와요
- Actions 로그 확인 (Actions 탭 → 실패한 run 클릭)
- Chat ID 다시 확인
- 봇과 한 번이라도 대화한 적 있는지 확인

### "GEMINI_API_KEY not found"
- Secrets 등록 시 이름이 정확히 `GEMINI_API_KEY`인지 확인
- 대소문자/언더스코어 일치해야 함

### Gemini API rate limit
- 무료 티어는 분당 15회 제한. 매일 1회 호출이라 문제될 일 없음

## 📝 면책

본 시스템이 제공하는 정보는 참고용이며 투자 자문이 아닙니다. 모든 매매 결정의 책임은 본인에게 있습니다.
