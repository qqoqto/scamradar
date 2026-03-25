# 🛡️ ScamRadar 獵詐雷達

LINE Bot 防詐分析系統 — 社群帳號風險評估 / 詐騙內容偵測 / 網址安全檢查

## 功能特色

- **帳號查詢**：輸入 `@帳號名稱`，跨平台分析帳號可信度
- **內容分析**：轉傳可疑訊息，AI + 規則引擎雙層偵測詐騙話術
- **網址檢查**：貼上連結，自動偵測釣魚、偽冒官方、惡意網站
- **社群回報**：使用者回報詐騙帳號，累積共享黑名單資料庫

## 技術棧

| 元件 | 技術 |
|------|------|
| Bot 介面 | LINE Messaging API |
| 後端 | Python 3.12 + FastAPI |
| AI 分析 | Claude API (Sonnet) |
| 資料庫 | PostgreSQL + Redis |
| 部署 | Docker / Render / Railway |

## 快速開始

### 1. 環境準備

```bash
git clone https://github.com/你的帳號/scamradar.git
cd scamradar
cp .env.example .env
```

### 2. 設定環境變數

編輯 `.env`，填入以下資訊：

```env
# 從 LINE Developers Console 取得
LINE_CHANNEL_SECRET=your_secret
LINE_CHANNEL_ACCESS_TOKEN=your_token

# 從 Anthropic Console 取得
CLAUDE_API_KEY=your_key
```

### 3. 本地開發（Docker Compose）

```bash
docker compose up -d
```

服務會啟動在 `http://localhost:8000`。

### 4. LINE Bot 設定

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 建立 Provider 和 Messaging API Channel
2. 取得 Channel Secret 和 Channel Access Token
3. 設定 Webhook URL: `https://你的域名/api/v1/webhook`
4. 開啟 Webhook 功能，關閉自動回應

### 5. 本地開發搭配 ngrok

LINE Webhook 需要 HTTPS，本地開發可用 ngrok：

```bash
ngrok http 8000
```

把 ngrok 給的 HTTPS URL 設定到 LINE Developers Console 的 Webhook URL。

## 部署到 Render

1. Fork 這個 repo 到你的 GitHub
2. 到 [Render Dashboard](https://dashboard.render.com/) → New → Blueprint
3. 連結你的 GitHub repo，Render 會自動讀取 `render.yaml`
4. 在 Environment 設定 LINE 和 Claude API 的 key
5. 部署完成後，把 Render 給的 URL 設定到 LINE Webhook

## 部署到 Railway

1. 到 [Railway](https://railway.app/) → New Project → Deploy from GitHub
2. 選擇你的 repo
3. 加入 PostgreSQL 和 Redis 的 Add-on
4. 設定環境變數
5. 部署完成後，把 Railway 給的 URL + `/api/v1/webhook` 設定到 LINE

## 專案結構

```
scamradar/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 環境變數設定
│   ├── models/
│   │   ├── database.py         # SQLAlchemy 資料庫模型
│   │   └── schemas.py          # Pydantic 資料格式
│   ├── routers/
│   │   └── webhook.py          # LINE Webhook 路由
│   ├── services/
│   │   ├── message_router.py   # 訊息分類路由
│   │   ├── content_analyzer.py # 內容分析（規則引擎 + Claude AI）
│   │   ├── account_analyzer.py # 帳號風險評分
│   │   ├── url_analyzer.py     # 網址安全檢查
│   │   └── reply_builder.py    # LINE Flex Message 回覆組裝
│   ├── scrapers/               # 社群平台爬蟲（Phase 2）
│   └── utils/
│       ├── cache.py            # Redis 快取
│       └── logger.py           # 日誌
├── tests/                      # 單元測試
├── docker-compose.yml          # 本地開發用
├── Dockerfile                  # 容器化部署
├── render.yaml                 # Render 部署設定
├── railway.json                # Railway 部署設定
└── requirements.txt            # Python 依賴
```

## 使用方式

加入 LINE Bot 好友後：

| 操作 | 說明 |
|------|------|
| 傳文字訊息 | 自動分析是否包含詐騙特徵 |
| 輸入 `@帳號名稱` | 分析該帳號的可信度 |
| 貼上網址 | 檢查連結是否安全 |
| 傳截圖 | OCR 辨識後分析（開發中） |

## 測試

```bash
pip install -r requirements.txt
pytest -v
```

## 開發路線圖

- [x] Phase 1: LINE Bot + 內容分析 + 帳號分析 + 網址檢查
- [ ] Phase 2: Playwright 社群帳號爬蟲
- [ ] Phase 3: 截圖 OCR 辨識
- [ ] Phase 4: 社群回報黑名單資料庫
- [ ] Phase 5: Web 儀表板

## 授權

MIT License
