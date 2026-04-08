# CLAUDE.md

## 프로젝트 개요
Slack `/write <주제>` 명령 → AI 리서치·작성 → 미리보기 승인 → Blogger 발행 자동화 시스템.
광고(AdSense, 쿠팡파트너스) 자동 주입 포함.

## 디렉토리 구조

```
agents/          # LLM 백엔드 추상화 (claude/local/gemini/openclaw)
bots/            # 핵심 로직 (publisher, writer, collector, engine_loader 등)
integrations/    # Slack FastAPI 라우터
jobs/            # Job 오케스트레이션 (create/run/publish/reject)
monetization/    # AdSense + 쿠팡파트너스 HTML 주입
dashboard/
  backend/       # FastAPI (port 8080)
  frontend/      # React + Tailwind (port 5173)
config/          # persona.json, quality_rules.json 등 런타임 설정
data/            # pending_review/, originals/, published/ (gitignored)
tests/           # pytest 테스트
```

## 서버 기동
```bash
# 백엔드
uvicorn dashboard.backend.server:app --reload --port 8080

# 프론트엔드
cd dashboard/frontend && npm run dev
```

## 테스트
```bash
python -m pytest tests/ -q
# 현재 36 tests passing
```

## 주요 설정 파일
- `.env` — API 키 및 환경변수 (`.env.example` 참고)
- `config/persona.json` — 블로그 이름, 저자, blog_url, AdSense 슬롯 위치 등
- `config/blogs.json` — 코너(카테고리) 설정

## Blogger 인증
API Key 방식 아님 — **Google OAuth2** 사용.
- `BLOG_MAIN_ID` = Blogger 블로그 ID (숫자)
- `credentials.json` = Google Cloud Console OAuth 클라이언트 파일
- `token.json` = 최초 1회 `python scripts/get_token.py` 실행 후 자동 생성
- 두 파일 모두 gitignore 됨

## Agent 백엔드 선택
```
AGENT_BACKEND=claude         # Anthropic API
AGENT_BACKEND=local          # 집 서버 (Ollama 등), LOCAL_AGENT_URL 필요
AGENT_BACKEND_WRITE=local    # 작업별 오버라이드
AGENT_FALLBACK=claude,local  # 장애 시 폴백 체인
```

## Slack 연동
- `/write <주제>` → `POST /slack/commands`
- Approve/Reject 버튼 → `POST /slack/interactivity`
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` 필요
- 로컬 테스트: ngrok으로 8080 포트 외부 노출 후 Slack App Request URL 설정

## Job 흐름
```
create_job() → data/pending_review/job_{id}.json (status=requested)
run_job()    → research → write → media_prompts → draft 저장
             → status=preview_ready → Slack Block Kit 카드 전송
publish_job() → status=published (Blogger API 발행 TODO 연결 필요)
reject_job()  → status=rejected
```

## 수익화
- AdSense: `ADSENSE_CLIENT_ID` + `ADSENSE_SLOT_*` 설정 시 본문에 자동 주입
- 쿠팡파트너스: `COUPANG_ACCESS_KEY` 설정 시 추천 상품 섹션 + 법적 고지문 자동 삽입
- 훅 위치: `bots/publisher_bot.py` → `build_full_html()` 마지막

## 주의사항
- `config/persona.json`의 "The 4th Path" / "22B Labs" → 본인 정보로 교체 필요
- `bots/` 파일은 직접 수정 가급적 지양 — 기능 추가는 `agents/`, `jobs/`, `monetization/`에
- `data/` 폴더 내용은 gitignore (민감 데이터)
- `repo/` 폴더는 참조용 원본 클론 (gitignore, 코드에서 import 금지)
