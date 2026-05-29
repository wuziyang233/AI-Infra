# AI Infra 决策情报助手

一个面向 AI 基础设施领域的轻量级决策情报系统。它可以定时采集 RSS/网页信源，生成中文日报，并通过飞书机器人推送到群聊。

## 功能

- RSS/URL 信源管理
- 信源连通性测试
- 自动采集 AI Infra 相关文章
- DeepSeek 生成中文决策情报日报
- SQLite 存储文章、日报、问答历史
- ChromaDB 支持基础 RAG 问答
- 纯 HTML/CSS/JS 前端页面
- 飞书自定义机器人卡片推送
- APScheduler 每日定时任务
- 可选 HTTP Basic 登录保护

## 技术栈

- Python 3.9+
- FastAPI
- SQLite
- ChromaDB
- DeepSeek API
- APScheduler
- httpx / feedparser / readability-lxml
- 原生 HTML/CSS/JS 前端

## 本地运行

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

DATABASE_PATH=data/sqlite/ai_infra.db
CHROMA_PATH=data/chroma
REPORT_DIR=data/reports

COLLECT_CRON_HOUR=8
COLLECT_CRON_MINUTE=0
REPORT_CRON_HOUR=9
REPORT_CRON_MINUTE=0
TIMEZONE=Asia/Shanghai
```

### 3. 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

## 飞书机器人接入

### 1. 创建飞书自定义机器人

在飞书群里添加「自定义机器人」，复制：

- Webhook URL
- 签名校验 Secret

### 2. 写入 `.env`

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的机器人ID
FEISHU_SECRET=你的签名校验密钥
```

如果机器人安全设置里开启了「关键词」，建议加入：

```text
AI Infra
```

### 3. 手动测试推送

先确保已经生成过日报，然后执行：

```bash
curl -X POST http://127.0.0.1:8000/api/reports/push-feishu
```

如果开启了网页登录密码：

```bash
curl -u 用户名:密码 -X POST http://127.0.0.1:8000/api/reports/push-feishu
```

## 定时任务

服务启动后会自动注册定时任务。

默认北京时间：

- 08:00 自动采集文章
- 08:10 自动抓取正文并分析
- 09:00 自动生成日报，并推送到飞书

修改 `.env` 后重启服务生效：

```env
COLLECT_CRON_HOUR=8
COLLECT_CRON_MINUTE=0
REPORT_CRON_HOUR=9
REPORT_CRON_MINUTE=0
TIMEZONE=Asia/Shanghai
```

## Web 登录保护

如果服务暴露到公网，建议开启 HTTP Basic 登录保护。

在 `.env` 中设置：

```env
WEB_AUTH_USERNAME=admin
WEB_AUTH_PASSWORD=你的强密码
```

设置后，访问网页和大部分 API 都需要输入用户名和密码。`/api/health` 保持开放，便于健康检查。

## 常用 API

```text
GET  /api/health
GET  /api/sources
POST /api/sources/init-defaults
POST /api/sources/{id}/test
POST /api/collect
GET  /api/articles
POST /api/reports/generate
GET  /api/reports/latest
POST /api/reports/push-feishu
POST /api/qa
```

## 云服务器部署

推荐使用 systemd 常驻运行。

示例服务文件：

```ini
[Unit]
Description=AI Infra Intel FastAPI Service
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/ai-infra-intel
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/admin/ai-infra-intel/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-infra-intel
sudo systemctl start ai-infra-intel
```

查看状态：

```bash
sudo systemctl status ai-infra-intel --no-pager
```

查看日志：

```bash
journalctl -u ai-infra-intel -f
```

更多部署说明见 [DEPLOYMENT.md](DEPLOYMENT.md)。


## 获取RSS
https://wechat2rss.xlab.app/

## 数据和安全

以下内容不会提交到 Git：

- `.env`
- SQLite 数据库
- ChromaDB 向量库
- 生成的日报 Markdown
- Python 虚拟环境

不要把真实的 API Key、飞书 Webhook、飞书 Secret 提交到公开仓库。

## 许可证

当前未指定许可证。公开使用前建议补充 LICENSE。
