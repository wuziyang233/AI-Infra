from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone, timedelta

from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, REPORT_DIR
from app.models.database import get_db, get_chroma

logger = logging.getLogger(__name__)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
BJT = timezone(timedelta(hours=8))

REPORT_PROMPT = """你是"AI Infra 决策情报"日报的主编。请根据下面提供的当日文章，生成一份中文日报。

## 日报结构要求

日报必须严格按以下格式，使用 Markdown：

# 今日 AI Infra 决策情报 - {date}

## 一句话结论

用一句话概括今天最重要的 AI Infra 趋势。

## 今日最重要的 3-5 件事

逐条列出，每条包含：
- **标题**
- **发生了什么**：事实描述
- **为什么重要**：背景和影响分析
- **对算力平台 / AI Infra 的影响**：对基础设施的具体影响
- **对 B 端产品经理的启示**：产品层面的 actionable 洞察
- **来源**：
  - [文章标题](文章URL)

## 国内动态

国内 AI Infra 相关动态，格式同上（如无内容写"本日暂无相关情报"）。

## 海外动态

海外 AI Infra 相关动态，格式同上（如无内容写"本日暂无相关情报"）。

## 产品机会

基于当日报文提炼的产品机会点，每条必须有来源支撑。

## 风险与不确定性

风险提示，每条必须有来源支撑。

## 规则
1. 严格使用 Markdown，每个信息点后必须有 `来源` 节，列出支撑的链接
2. 多个文章支撑同一结论时，列多个来源
3. 没有来源的信息不要写进日报
4. 直接输出 Markdown，不要包含代码块标记
5. 全文使用中文"""


def _today() -> str:
    return datetime.now(BJT).strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")


def vectorize_article(article_id: int, title: str, summary: str, content: str):
    """Add article to ChromaDB for Q&A retrieval."""
    chroma = get_chroma()
    try:
        coll = chroma.get_collection("article_chunks")
    except Exception:
        return

    text = f"{title}\n{summary}\n{content}"[:2000]
    try:
        coll.add(
            documents=[text],
            metadatas=[{"article_id": article_id, "title": title, "url": ""}],
            ids=[f"article_{article_id}"],
        )
    except Exception as e:
        logger.warning(f"Chroma add failed for article {article_id}: {e}")


def vectorize_report_section(report_id: int, report_date: str, section_type: str, title: str, content: str):
    """Add report section to ChromaDB."""
    chroma = get_chroma()
    try:
        coll = chroma.get_collection("report_chunks")
    except Exception:
        return

    text = f"{title}\n{content}"[:2000]
    try:
        coll.add(
            documents=[text],
            metadatas=[{"report_id": report_id, "report_date": report_date, "section_type": section_type}],
            ids=[f"report_{report_id}_{section_type}"],
        )
    except Exception as e:
        logger.warning(f"Chroma add failed for report section {report_id}/{section_type}: {e}")


def generate_report(date: str | None = None) -> int | None:
    """Generate a daily report for the given date (default today). Returns report_id or None."""
    report_date = date or _today()
    db = get_db()

    # Check for existing report
    existing = db.execute("SELECT id FROM daily_reports WHERE report_date=?", (report_date,)).fetchone()
    if existing:
        db.close()
        logger.info(f"Report for {report_date} already exists (id={existing[0]})")
        return None

    # Collect today's articles (use content as fallback when summary is null)
    rows = db.execute(
        """SELECT a.id, a.title, a.url,
                  COALESCE(a.summary, SUBSTR(a.content, 1, 300)) as summary,
                  a.content, a.relevance
           FROM articles a
           WHERE date(a.collected_at) = ?
             AND (a.summary IS NOT NULL OR a.content IS NOT NULL)
           ORDER BY a.relevance DESC""",
        (report_date,),
    ).fetchall()

    if not rows:
        # fallback: take most recent 20 articles
        rows = db.execute(
            """SELECT id, title, url,
                      COALESCE(summary, SUBSTR(content, 1, 300)) as summary,
                      content, relevance
               FROM articles
               WHERE summary IS NOT NULL OR content IS NOT NULL
               ORDER BY id DESC LIMIT 20"""
        ).fetchall()

    if not rows:
        db.close()
        logger.warning(f"No articles available for report {report_date}")
        return None

    # Build article context for LLM
    articles_text = []
    for r in rows:
        ins_rows = db.execute(
            "SELECT category, content FROM article_insights WHERE article_id=?", (r["id"],)
        ).fetchall()
        ins_text = "; ".join(f"[{i['category']}] {i['content']}" for i in ins_rows)
        body = (r["summary"] or "")[:500]
        articles_text.append(
            f"**{r['title']}** (相关度:{r['relevance']:.2f})\n{body}\n洞察:{ins_text}\n链接:{r['url']}\n"
        )

    article_count = len(rows)
    context = "\n---\n".join(articles_text)

    # Call DeepSeek
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": REPORT_PROMPT},
                {"role": "user", "content": f"日期：{report_date}\n今日文章数量：{article_count}\n\n{context}"},
            ],
            temperature=0.5,
            max_tokens=4000,
        )
        markdown = resp.choices[0].message.content.strip()
        if markdown.startswith("```"):
            markdown = markdown.split("\n", 1)[1]
            if markdown.endswith("```"):
                markdown = markdown[:-3]
    except Exception as e:
        db.close()
        logger.error(f"LLM call failed for report: {e}")
        msg = str(e)
        if "401" in msg or "authentication" in msg.lower():
            raise RuntimeError("DeepSeek API Key 无效，请检查 .env 中的 DEEPSEEK_API_KEY")
        elif "429" in msg or "rate" in msg.lower():
            raise RuntimeError("DeepSeek API 频率限制，请稍后重试")
        else:
            raise RuntimeError(f"大模型调用失败: {msg[:200]}")

    # Save markdown file
    os.makedirs(REPORT_DIR, exist_ok=True)
    file_path = os.path.join(REPORT_DIR, f"report_{report_date}.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    # Parse sections from markdown for DB storage
    sections = _parse_sections(markdown)

    # Extract title and summary
    lines = markdown.split("\n")
    title = next((l.strip("# ").strip() for l in lines if l.startswith("# ")), f"今日 AI Infra 决策情报 - {report_date}")
    summary_text = sections[0]["content"][:300] if sections else ""

    # Save to DB
    cur = db.execute(
        "INSERT INTO daily_reports (report_date, title, summary, file_path, article_count, created_at) VALUES (?,?,?,?,?,?)",
        (report_date, title, summary_text, file_path, article_count, _now()),
    )
    report_id = cur.lastrowid
    for i, sec in enumerate(sections):
        db.execute(
            "INSERT INTO report_sections (report_id, section_type, title, content, sort_order) VALUES (?,?,?,?,?)",
            (report_id, sec["type"], sec["title"], sec["content"], i),
        )
        vectorize_report_section(report_id, report_date, sec["type"], sec["title"], sec["content"])
    db.commit()
    db.close()

    logger.info(f"Report generated: {file_path} ({article_count} articles)")
    return report_id


def _parse_sections(markdown: str) -> list[dict]:
    """Parse ## headings into sections. Supports new report structure."""
    sections = []
    current_type_map = {
        "一句话结论": "headlines",
        "今日最重要的": "headlines",
        "国内动态": "trends",
        "海外动态": "decisions",
        "产品机会": "events",
        "风险与不确定": "risks",
    }
    # Fallback section type
    fallback_type = "headlines"
    lines = markdown.split("\n")
    current = None
    buf = []
    for line in lines:
        if line.startswith("## "):
            if current:
                current["content"] = "\n".join(buf).strip()
                sections.append(current)
            heading = line[3:].strip()
            sec_type = fallback_type
            for key, val in current_type_map.items():
                if key in heading:
                    sec_type = val
                    break
            current = {"type": sec_type, "title": heading, "content": ""}
            buf = []
        elif current is not None:
            buf.append(line)
    if current:
        current["content"] = "\n".join(buf).strip()
        sections.append(current)
    # if no h2 sections found, treat whole doc as headlines
    if not sections:
        sections = [{"type": "headlines", "title": "今日情报", "content": markdown}]
    return sections
