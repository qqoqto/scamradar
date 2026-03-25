# 🛡️ ScamRadar 獵詐雷達

台灣詐騙防護平台 — LINE Bot + Web Dashboard + Public API

[![LINE Bot](https://img.shields.io/badge/LINE_Bot-@693zkvby-00B900?logo=line)](https://line.me/R/ti/p/@693zkvby)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway)](https://scamradar-production.up.railway.app)

---

## 功能概覽

### Phase 1 — LINE Bot 核心
| 功能 | 說明 |
|------|------|
| 📝 內容分析 | 規則引擎 13 種詐騙模式 + Claude AI 語意分析 |
| 👤 帳號分析 | 風險評分演算法 |
| 🔗 網址檢查 | 偽冒偵測 + Google Safe Browsing |
| 📞 電話查詢 | 台灣號碼分類 + 國際詐騙高風險區偵測 |
| 📸 截圖辨識 | Claude Vision OCR |
| 🛡️ 群組防護 | 靜默監控，高風險才警告 |
| 🚨 回報機制 | 寫入 DB，累積黑名單 |

### Phase 2 — Web Dashboard + Public API
| 功能 | 說明 |
|------|------|
| 📊 儀表板 | 即時統計、14 日趨勢圖、風險分佈圓餅圖 |
| 🔍 查詢工具 | 電話/網址/帳號/內容 四合一檢測介面 |
| 📋 歷史紀錄 | 所有查詢紀錄 + 類型/風險篩選 |
| 🏆 黑名單排行 | 最多回報的可疑對象排名 |
| 🌐 Public API | RESTful API 供第三方串接 |

---

## 技術棧

- **後端**: Python 3.11 + FastAPI + SQLAlchemy (async) + Alembic
- **前端**: React 18 + Vite + Tailwind CSS + Recharts
- **資料庫**: PostgreSQL 16
- **快取**: Redis 7
- **AI**: Anthropic Claude API (語意分析 + Vision OCR)
- **部署**: Railway (Dockerfile multi-stage build)

---

## 快速開始

### 1. Clone & 設定環境變數

```bash
git clone https://github.com/qqoqto/scamradar.git
cd scamradar
cp .env.example .env
# 編輯 .env 填入 LINE / Claude API keys
```

### 2. 本地開發（Docker Compose）

```bash
docker compose up -d
```

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

前端開發（hot reload）：

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173（自動 proxy /api → :8000）
```

### 3. 部署到 Railway

1. 到 [Railway](https://railway.app/) → New Project → Deploy from GitHub
2. 選擇 `qqoqto/scamradar` repo
3. 新增 **PostgreSQL** 和 **Redis** Add-on
4. 設定環境變數：

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | Railway 自動注入（改 scheme 為 `postgresql+asyncpg://`）|
| `REDIS_URL` | Railway 自動注入 |
| `LINE_CHANNEL_SECRET` | LINE Developers Console |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers Console |
| `CLAUDE_API_KEY` | Anthropic Console |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Cloud Console（可選）|

5. 部署完成後，設定 LINE Webhook URL:
   ```
   https://scamradar-production.up.railway.app/api/v1/webhook
   ```

---

## Public API

Base URL: `https://scamradar-production.up.railway.app/api/v1/public`

### 檢測 API

所有檢測 endpoint 回傳相同格式：

```json
{
  "risk_level": "high",
  "risk_score": 78,
  "summary": "偵測到投資詐騙特徵",
  "details": { ... },
  "cached": false,
  "timestamp": "2026-03-25T10:30:00"
}
```

| Endpoint | Method | Body |
|----------|--------|------|
| `/check/phone` | POST | `{ "phone": "+886912345678" }` |
| `/check/url` | POST | `{ "url": "https://example.com" }` |
| `/check/username` | POST | `{ "username": "@scammer123" }` |
| `/check/content` | POST | `{ "content": "恭喜中獎..." }` |

### 統計 & 黑名單

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/stats` | GET | 總覽統計（查詢數、使用者、回報數、趨勢） |
| `/blacklist/top?limit=20&type=phone` | GET | 黑名單排行榜 |
| `/queries/recent?limit=50&type=url&risk_level=high` | GET | 歷史查詢紀錄 |

### Rate Limiting

每個 IP 每分鐘最多 20 次請求，超過回傳 `429 Too Many Requests`。

### 範例

```bash
# 檢查電話
curl -X POST https://scamradar-production.up.railway.app/api/v1/public/check/phone \
  -H "Content-Type: application/json" \
  -d '{"phone": "0912345678"}'

# 取得統計
curl https://scamradar-production.up.railway.app/api/v1/public/stats

# 黑名單 Top 10
curl "https://scamradar-production.up.railway.app/api/v1/public/blacklist/top?limit=10"
```

---

## 專案結構

```
scamradar/
├── app/
│   ├── main.py                  # FastAPI 入口 + React SPA serving
│   ├── config.py                # 環境變數
│   ├── models/
│   │   ├── database.py          # SQLAlchemy 模型
│   │   └── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── webhook.py           # LINE Bot webhook
│   │   └── public_api.py        # Phase 2 Public API
│   ├── services/
│   │   ├── message_router.py    # 訊息分類
│   │   ├── content_analyzer.py  # 內容分析（規則 + Claude AI）
│   │   ├── account_analyzer.py  # 帳號風險評分
│   │   ├── url_analyzer.py      # 網址安全檢查
│   │   ├── phone_analyzer.py    # 電話號碼分析
│   │   ├── image_analyzer.py    # 截圖 OCR (Claude Vision)
│   │   ├── report_service.py    # 回報 + 黑名單
│   │   └── reply_builder.py     # LINE Flex Message
│   └── utils/
│       ├── cache.py             # Redis 快取
│       └── logger.py            # 日誌
├── frontend/                    # React Dashboard
│   ├── src/
│   │   ├── App.jsx              # Router + Sidebar
│   │   ├── api.js               # API client
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # 統計儀表板
│   │   │   ├── Checker.jsx      # 查詢工具
│   │   │   ├── History.jsx      # 歷史紀錄
│   │   │   └── Blacklist.jsx    # 黑名單排行
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── tests/
│   └── test_public_api.py       # Phase 2 API 測試
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # 本地開發
├── railway.json                 # Railway 部署設定
├── nixpacks.toml                # Railway Nixpacks 備用
├── requirements.txt
└── .env.example
```

---

## 測試

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## 開發路線圖

- [x] Phase 1: LINE Bot + 內容分析 + 帳號分析 + 網址檢查 + 電話查詢 + 截圖辨識 + 群組防護 + 回報機制
- [x] Phase 2: Web Dashboard + Public API + 同服務部署
- [ ] Phase 3: 進階分析（Playwright 社群爬蟲、IP/WHOIS 深度分析）
- [ ] Phase 4: 社群互動（用戶貢獻評分、信任等級、成就系統）

## 授權

MIT License
