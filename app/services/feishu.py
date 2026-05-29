from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from app.config import FEISHU_SECRET, FEISHU_WEBHOOK_URL
from app.models.database import get_db

logger = logging.getLogger(__name__)
BJT = timezone(timedelta(hours=8))


class FeishuConfigError(RuntimeError):
    pass


def push_latest_report_to_feishu() -> dict[str, Any]:
    db = get_db()
    row = db.execute("SELECT * FROM daily_reports ORDER BY id DESC LIMIT 1").fetchone()
    db.close()
    if not row:
        raise RuntimeError("No reports found")
    return push_report_to_feishu(row["report_date"])


def push_report_to_feishu(report_date: str) -> dict[str, Any]:
    if not FEISHU_WEBHOOK_URL:
        _log_push(report_date, "error", "FEISHU_WEBHOOK_URL 未配置")
        raise FeishuConfigError("FEISHU_WEBHOOK_URL 未配置")

    report = _load_report(report_date)
    card = _build_report_card(report)
    payload: dict[str, Any] = {
        "msg_type": "interactive",
        "card": card,
    }
    if FEISHU_SECRET:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _sign(timestamp, FEISHU_SECRET)

    try:
        resp = httpx.post(FEISHU_WEBHOOK_URL, json=payload, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        _log_push(report_date, "error", f"飞书 webhook 请求失败: {e}")
        raise RuntimeError(f"飞书 webhook 请求失败: {e}") from e

    data = resp.json()
    if data.get("code", 0) != 0:
        _log_push(report_date, "error", str(data)[:500], data.get("code"))
        raise RuntimeError(f"飞书返回错误: {data}")

    _log_push(report_date, "success", data.get("msg") or "success", data.get("code"))
    logger.info("Feishu report pushed: %s", report_date)
    return {"ok": True, "report_date": report_date, "response": data}


def list_push_logs(limit: int = 20) -> list[dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM feishu_push_log ORDER BY id DESC LIMIT ?",
        (min(max(limit, 1), 100),),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def _load_report(report_date: str) -> dict[str, Any]:
    db = get_db()
    row = db.execute("SELECT * FROM daily_reports WHERE report_date=?", (report_date,)).fetchone()
    if not row:
        db.close()
        raise RuntimeError(f"No report for {report_date}")
    sections = db.execute(
        "SELECT * FROM report_sections WHERE report_id=? ORDER BY sort_order", (row["id"],)
    ).fetchall()
    db.close()

    with open(row["file_path"], "r", encoding="utf-8") as f:
        markdown = f.read()

    return {
        "report_date": row["report_date"],
        "title": row["title"],
        "summary": row["summary"] or "",
        "article_count": row["article_count"],
        "sections": [dict(s) for s in sections],
        "markdown": markdown,
    }


def _sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _log_push(report_date: str, status: str, message: str, response_code: int | None = None):
    try:
        db = get_db()
        db.execute(
            """INSERT INTO feishu_push_log
               (report_date, status, message, response_code, created_at)
               VALUES (?,?,?,?,?)""",
            (
                report_date,
                status,
                message[:1000] if message else "",
                response_code,
                datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        db.commit()
        db.close()
    except Exception as e:
        logger.warning("Failed to write Feishu push log: %s", e)


def _build_report_card(report: dict[str, Any]) -> dict[str, Any]:
    markdown = report["markdown"]
    conclusion = _extract_section(markdown, "一句话结论") or report["summary"]
    top_items = _extract_top_items(markdown)
    domestic = _extract_section(markdown, "国内动态")
    overseas = _extract_section(markdown, "海外动态")
    opportunities = _extract_section(markdown, "产品机会")
    risks = _extract_section(markdown, "风险与不确定")

    elements: list[dict[str, Any]] = [
        _markdown_element(f"**一句话结论**\n{_clean_text(conclusion, 700)}"),
        {"tag": "hr"},
    ]

    if top_items:
        elements.append(_markdown_element("**今日重点**\n" + "\n".join(top_items[:5])))
        elements.append({"tag": "hr"})

    if domestic:
        elements.append(_markdown_element(_format_section("国内动态", domestic, max_items=4, max_chars=1200)))
        elements.append({"tag": "hr"})

    if overseas:
        elements.append(_markdown_element(_format_section("海外动态", overseas, max_items=4, max_chars=1200)))
        elements.append({"tag": "hr"})

    if opportunities:
        elements.append(_markdown_element(_format_section("产品机会", opportunities, max_items=4, max_chars=1400)))

    if risks:
        elements.append(_markdown_element(_format_section("风险与不确定性", risks, max_items=4, max_chars=1200)))

    elements.append(
        _note_element(
            f"{report['report_date']} | 文章数 {report['article_count']} | 完整 Markdown 已保存在本地日报目录"
        )
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": report["title"]},
            "subtitle": {"tag": "plain_text", "content": "AI Infra 决策情报日报"},
        },
        "elements": elements,
    }


def _markdown_element(content: str) -> dict[str, Any]:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _note_element(content: str) -> dict[str, Any]:
    return {"tag": "note", "elements": [{"tag": "plain_text", "content": content}]}


def _extract_section(markdown: str, heading_keyword: str) -> str:
    pattern = re.compile(rf"^##\s+.*{re.escape(heading_keyword)}.*$", re.MULTILINE)
    match = pattern.search(markdown)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", markdown[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(markdown)
    return markdown[start:end].strip()


def _extract_top_items(markdown: str) -> list[str]:
    section = _extract_section(markdown, "今日最重要")
    if not section:
        return []

    blocks = re.split(r"(?=^###\s+)", section, flags=re.MULTILINE)
    items = []
    for block in blocks:
        heading = re.search(r"^###\s+\d*\.?\s*(.+)$", block, flags=re.MULTILINE)
        if not heading:
            continue

        title = _clean_text(heading.group(1), 140)
        links = _extract_links(block)
        item = f"{len(items) + 1}. {title}"
        if links:
            item += "\n   来源：" + "、".join(links[:3])
        items.append(item)

    if items:
        return items

    lines = [line for line in section.splitlines() if line.strip().startswith(("-", "*"))]
    return [_clean_text(line, 160) for line in lines[:5]]


def _extract_links(markdown: str) -> list[str]:
    seen = set()
    links = []
    for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", markdown):
        if url in seen:
            continue
        seen.add(url)
        links.append(f"[{_clean_text(title, 70)}]({url})")
    return links


def _format_section(title: str, section: str, max_items: int, max_chars: int) -> str:
    items = _extract_heading_items(section, max_items=max_items)
    if items:
        content = f"**{title}**\n" + "\n\n".join(items)
    else:
        content = f"**{title}**\n{_clean_text(section, max_chars)}"
    return _clean_text(content, max_chars)


def _extract_heading_items(section: str, max_items: int) -> list[str]:
    blocks = re.split(r"(?=^###\s+)", section, flags=re.MULTILINE)
    items = []
    for block in blocks:
        heading = re.search(r"^###\s+\d*\.?\s*(.+)$", block, flags=re.MULTILINE)
        if not heading:
            continue

        body = re.sub(r"^###\s+.*$", "", block, count=1, flags=re.MULTILINE).strip()
        body = re.sub(r"-\s*\*\*来源\*\*[:：]?.*", "", body, flags=re.IGNORECASE)
        body = re.sub(r"^\s*-\s*来源[:：]?.*$", "", body, flags=re.MULTILINE)
        body = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", body)
        body = re.sub(r"\n{2,}", "\n", body).strip()

        line = f"{len(items) + 1}. {_clean_text(heading.group(1), 120)}"
        if body:
            line += f"\n   {_clean_text(body, 260)}"

        links = _extract_links(block)
        if links:
            line += "\n   来源：" + "、".join(links[:3])

        items.append(line)
        if len(items) >= max_items:
            break
    return items


def _clean_text(text: str, limit: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
