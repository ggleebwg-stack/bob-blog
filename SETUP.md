# Setup Guide

## Prerequisites
- Python 3.11+
- Node.js 20+ (for dashboard)
- A Slack workspace where you can install apps

## 1. Clone & install
```bash
git clone <this-repo>
cd blog
pip install -r requirements.txt
```

## 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your actual values
```

## 3. Start the dashboard
```bash
cd dashboard/backend
uvicorn server:app --reload --port 8080
```

In another terminal (optional frontend):
```bash
cd dashboard/frontend
npm install && npm run dev
```

## 4. Set up Slack App
1. Go to https://api.slack.com/apps → Create New App
2. Enable Slash Commands → /write
   - Request URL: `https://<your-domain>/slack/commands`
3. Enable Interactivity
   - Request URL: `https://<your-domain>/slack/interactivity`
4. OAuth Scopes: `commands`, `chat:write`
5. Install to workspace
6. Copy Bot Token → `SLACK_BOT_TOKEN` in `.env`
7. Copy Signing Secret → `SLACK_SIGNING_SECRET` in `.env`

## 5. Agent backend
Choose your LLM backend in `.env`:
- `AGENT_BACKEND=claude` → requires `ANTHROPIC_API_KEY`
- `AGENT_BACKEND=local` → requires `LOCAL_AGENT_URL` (e.g. Ollama at `http://192.168.1.x:11434`)
- Mix per task: `AGENT_BACKEND_WRITE=local`, `AGENT_BACKEND_RESEARCH=claude`

## 6. Monetization (optional)
- **AdSense**: set `ADSENSE_CLIENT_ID` + `ADSENSE_SLOT_*` (requires approved AdSense account)
- **Coupang Partners**: set `COUPANG_ACCESS_KEY` after approval at partners.coupang.com

## 7. Test
```bash
python -m pytest tests/ -q
```

## Usage
In Slack:
```
/write 봄 캠핑 용품 추천
```
