# AI Infra 决策情报 — CLAUDE.md

更新时间：2026-04-29

## 项目概述

每天自动采集 RSS 文章 → DeepSeek V4 分析 → 生成 Markdown 日报 → 支持基础 RAG 问答的 MVP 系统。

- **状态**: MVP 可用，核心链路（采集→日报→问答）已跑通
- **技术栈**: Python 3.9 / FastAPI / SQLite / ChromaDB / DeepSeek V4 / feedparser / httpx
- **前端**: 纯 HTML/CSS/JS，Tailwind CSS CDN + marked.js，单页 SPA

## 当前项目状态

### 已实现模块
| 模块 | 状态 | 说明 |
|------|------|------|
| 采集 | ✅ 可用 | httpx + feedparser，每源限 20 篇，过滤 `enabled=1 AND status=active` |
| 正文抽取 | ✅ 可用 | readability-lxml，定时任务 08:10 触发 |
| AI 分析 | ⚠️ 未启用 | `analyzer.py` 需 DeepSeek API，当前 summary 全为 NULL |
| 日报生成 | ✅ 可用 | 新格式含来源链接、国内外分节、产品机会、风险，COALESCE fallback |
| Q&A 问答 | ✅ 基础可用 | ChromaDB 双集合检索，仅命中 report_chunks |
| 前端 SPA | ✅ 可用 | 5 Tab（仪表盘/信源/文章/日报/问答）|
| API 接口 | ✅ 13 个端点 | 见下方完整列表 |

### 最近修复（2026-04-29）
| 修复 | 说明 |
|------|------|
| 🐛 日报分节内容为空 | `_parse_sections` 在遍历 Markdown 时遇到新 `##` 标题没保存已累积内容，导致所有 section（除最后一条）存为空字符串。已修复代码并重新解析 5 份历史日报。 |
| 🕐 时间戳全部改用北京时间 | SQLite 的 `datetime('now')` 返回 UTC 慢 8 小时，导致采集时间显示错误、日报按日期查询不匹配。统一改为 `datetime('now','localtime')` + Python `datetime.now(BJT)` 显式传入，并迁移 450 条历史数据。 |

## 已完成内容

### API 接口（13 个端点）

| 分类 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 健康 | GET | `/api/health` | `{status, chroma, llm}` |
| 信源 | GET | `/api/sources?type=&enabled=&category=&status=` | 信源列表（支持分类+状态筛选）|
| | POST | `/api/sources` | 添加信源（重复 URL 返回 409）|
| | PUT | `/api/sources/{id}` | 编辑信源（含 category/language/priority/status/description）|
| | DELETE | `/api/sources/{id}` | 删除信源及关联文章 |
| | POST | `/api/sources/init-defaults` | 一键初始化默认信源（已存在跳过）|
| 采集 | POST | `/api/collect?source_id=` | 触发采集，返回 per-source `{source, new_articles, status}` |
| | GET | `/api/collect/status?limit=` | 采集日志 |
| 文章 | GET | `/api/articles?date=&source_id=&page=&size=` | 文章列表（size≤100）|
| | GET | `/api/articles/{id}` | 文章详情+洞察 |
| 日报 | POST | `/api/reports/generate` | 触发日报生成（新格式，含来源链接）|
| | GET | `/api/reports?page=&size=` | 日报列表 |
| | GET | `/api/reports/latest` | 最新日报 Markdown 全文 |
| | GET | `/api/reports/{date}` | 指定日期日报 |
| 问答 | POST | `/api/qa` | `{"question":"..."}` → `{answer, sources}` |
| | GET | `/api/qa/history?limit=` | 问答历史 |

### 前端页面功能
- **仪表盘**: 快捷操作（采集/生成日报）+ 最近采集日志 + 统计数据
- **信源**: 初始化默认信源按钮 + 表格展示分类/语言/状态/优先级 + 一键启用/禁用
- **文章**: 按日期/信源筛选 + 点击展开详情 + 原文链接
- **日报**: 左侧列表 + 右侧渲染（marked.js），链接可点击新标签页打开
- **问答**: 对话式交互 + 来源链接可点击

### 数据存储

**SQLite（7 张表）**
- `sources` — 信源配置（url UNIQUE，字段含 category/language/priority/status/description）
- `articles` — 文章（url UNIQUE 去重，content 存 RSS 正文，summary 存 AI 摘要）
- `article_insights` — 文章洞察（category: trend/decision/risk/event）
- `daily_reports` — 日报主表（report_date UNIQUE）
- `report_sections` — 日报分节（section_type: headlines/trends/decisions/risks/events）
- `qa_history` — 问答历史
- `collect_log` — 采集日志

**ChromaDB（2 个 Collection）**
- `article_chunks` — 文章向量（当前为空，需先跑 analyzer）
- `report_chunks` — 日报分节向量（含 metadata: report_id, report_date, section_type）

### 历史数据
- 24 个默认信源（8 active + 16 pending）
- 341 篇文章（已采集）
- 5 份日报（2026-04-25 ~ 2026-04-29）

## 运行方式

```bash
cd ai-infra-intel

# 1. 配置
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY（日报生成必需）

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动（data/ 目录自动创建）
uvicorn app.main:app --port 8000

# 4. 浏览器打开 http://localhost:8000/
```

**定时任务**（APScheduler，北京时间）：
- 08:00 自动采集全部 RSS 源（仅 `enabled=1 AND status=active` 的源）
- 08:10 自动抓取正文 + 分析（DeepSeek 摘要/洞察/向量化）
- 09:00 自动生成日报

## 核心接口说明

- **POST /api/sources/init-defaults**: 一键添加 24 个默认信源（分海外/国内/公众号/Infra 四类），已存在的 URL 自动跳过
- **GET /api/sources**: 查看所有信源，支持 `?category=china_ai&status=active` 筛选
- **POST /api/collect**: 触发采集全部活跃信源，返回每条来源的 `{source, source_id, new_articles, status}`
- **GET /api/articles**: 查看文章列表，默认最新 50 条
- **POST /api/reports/generate**: 调用 DeepSeek 生成今日中文日报（一句话结论 + 国内外分节 + 产品机会 + 风险 + 来源链接）
- **GET /api/reports/latest**: 获取最新日报全文 Markdown
- **POST /api/qa**: `{"question":"最近有什么趋势"}` → `{answer, sources}`

## 默认信源（24 个）

| 组 | 数量 | 状态 |
|---|------|------|
| 海外 AI（HN/OpenAI/NVIDIA/Google） | 9 | 8 active, 1 pending |
| 国内中文 AI（机器之心/量子位/36氪 等） | 9 | 全部 pending（依赖 RSSHub） |
| 公众号（AI 科技评论/腾讯云/阿里云） | 3 | 全部 pending（依赖 RSSHub wechat 路由） |
| 基础设施（HF/Modal/Latent Space） | 3 | 2 active, 1 pending |

Pending 信源不会影响采集流程。用户自建 RSSHub 实例后可手动启用。

## 当前存在问题

### DeepSeek API
- API Key 未配置时日报生成、Q&A、分析全部不可用
- 测试用量：一次报告生成约消耗 2000-3000 tokens
- 当前仅日报生成使用 DeepSeek（analyzer 未启用）

### RSS 稳定性
- **Reddit** `.rss` 源偶发 403（当前通过浏览器 UA 缓解，不稳定）
- **OpenAI Blog** RSS 正常
- **NVIDIA Blog** RSS 正常
- **Google AI Blog** RSS 正常
- **The Batch**：无公开 RSS，已标记 pending
- **Anthropic News**：无官方 RSS，通过 OpenRSS 转换，已标记 pending
- **所有 RSSHub 依赖源**：中文源全部 pending，需要可用 RSSHub 实例

### 数据质量
- 文章 summary 全为 NULL（analyzer 未运行），日报 fallback 到 content 前 300 字
- article_chunks 向量库为空，Q&A 仅能检索日报分节
- ChromaDB `posthog` 日志错误（v0.6.x 兼容性，不影响功能）

### 已修复问题
- ~~日报分节内容为空（2026-04-29 修复）~~
- ~~时间戳使用 UTC 而非北京时间（2026-04-29 修复，450 行数据已迁移）~~

## 已验证结果

2026-04-28 — 核心链路验证：

| 测试 | 结果 |
|------|------|
| POST /api/sources/init-defaults | ✅ 22 创建，2 跳过（已存在）|
| GET /api/sources | ✅ 24 个信源，8 active + 16 pending |
| POST /api/collect | ✅ 10 个活跃源，154 篇新文章；2 个失败不中断 |
| GET /api/articles | ✅ 返回文章数据 |
| POST /api/reports/generate | ✅ 新格式（来源链接/国内外/产品机会/风险）|
| GET /api/reports/latest | ✅ 返回完整 Markdown |
| 前端 5 Tab | ✅ 全部可用，链接新标签页打开 |

## 下一步计划（按优先级）

1. **高** 运行 `fill_article_contents()` + `run_analysis()` 填充摘要与向量，提升日报和 Q&A 质量
2. **高** 验证 RSSHub 中文信源可用性，自建 RSSHub 实例，启用国内源
3. **中** 优化日报质量：结构微调 + 去噪 + 增加国内/海外分类判断
4. **中** 前端增加"手动触发分析"和"历史日报查看"按钮
5. **低** 接入飞书/邮件 Webhook 日报推送
6. **低** 提供公网访问（cloudflared / 部署方案）
7. **低** 单元测试 + 集成测试

## 关键设计决策

1. **日报不依赖分析**：`generate_report()` 用 `COALESCE(summary, content)` 查询，即使没跑 analyzer 也能生成日报。分析是增强，不是阻塞项。
2. **采集去重**：articles 表 `url UNIQUE` + `INSERT OR IGNORE`，单篇重复不中断整批入库。
3. **采集限额**：每个 RSS 源每次最多入库 20 篇（`collect_rss(max_articles=20)`）。
4. **httpx 替代 feedparser 直接请求**：通过自定义 UA / Accept 头绕过反爬（Reddit 403 问题）。
5. **日报不可覆盖**：同一天多次触发 `generate_report` 会跳过（report_date UNIQUE）。
6. **ChromaDB 写入串行**：MVP 阶段避免并发锁问题。
7. **Per-source 结果**：采集返回每个信源的 `{source, source_id, new_articles, status}`，单源失败不中断全局。
8. **信源分类 + 状态**：sources 表增加 `category`/`language`/`priority`/`status` 字段，pending 源不参与采集。
9. **所有时间戳使用北京时间**：所有 SQLite `datetime('now')` 统一为 `datetime('now','localtime')`，Python 层统一使用 `datetime.now(BJT)` 显式传入，避免 UTC/BJT 不匹配导致的日期边界问题。
