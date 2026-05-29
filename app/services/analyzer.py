from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from app.models.database import get_db

logger = logging.getLogger(__name__)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
BJT = timezone(timedelta(hours=8))

ANALYZE_PROMPT = """你是一个AI基础设施领域的分析师。请分析以下文章，严格返回一个JSON对象（不要有markdown代码块）：

{
  "summary": "中文摘要，不超过150字",
  "relevance": 0.0-1.0,  // 与AI Infra的相关度
  "insights": [
    {"category": "trend/decision/risk/event", "content": "洞察内容，不超过80字"}
  ]
}

分类标准：
- trend: 技术趋势、市场方向
- decision: 企业战略决策、投资并购
- risk: 安全风险、合规风险、供应链风险
- event: 重要事件、产品发布

如果没有明显洞察，insights 可以是空数组。"""


def analyze_article(article_id: int, title: str, content: str | None) -> dict | None:
    """Analyze a single article with DeepSeek V4. Returns parsed result or None on failure."""
    text = content or title  # fallback to title if no content
    # truncate to ~3000 chars to manage token cost
    text = text[:3000]

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": ANALYZE_PROMPT},
                {"role": "user", "content": f"标题：{title}\n\n正文：{text}"},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        # defensive strip of code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        result = json.loads(raw)
        return result
    except Exception as e:
        logger.error(f"Analyze failed for article {article_id}: {e}")
        return None


def run_analysis(limit: int = 50):
    """Analyze unanalyzed articles, store summaries + insights + vectorize."""
    from app.services.reporter import vectorize_article

    db = get_db()
    rows = db.execute(
        "SELECT id, title, content FROM articles WHERE summary IS NULL ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    db.close()

    for row in rows:
        result = analyze_article(row["id"], row["title"], row["content"])
        if not result:
            continue

        summary = result.get("summary", "")
        relevance = result.get("relevance", 0.5)
        insights = result.get("insights", [])

        conn = get_db()
        conn.execute(
            "UPDATE articles SET summary=?, relevance=? WHERE id=?",
            (summary, relevance, row["id"]),
        )
        for ins in insights:
            conn.execute(
                "INSERT INTO article_insights (article_id, category, content, created_at) VALUES (?,?,?,?)",
                (row["id"], ins["category"], ins["content"],
                 datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
        conn.close()

        # vectorize article for Q&A retrieval
        vectorize_article(row["id"], row["title"], summary, row["content"] or "")
        time.sleep(0.5)  # rate limit cushion

    logger.info(f"Analyzed {len(rows)} articles")
