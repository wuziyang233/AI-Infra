from __future__ import annotations

import time
import logging
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from app.models.database import get_db

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.1",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Cache-Control": "no-cache",
}
BJT = timezone(timedelta(hours=8))


def _now() -> str:
    return datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")


def collect_rss(source_id: int, url: str, max_articles: int = 20) -> int:
    """Collect articles from a RSS feed via httpx. Cap at max_articles per run."""

    # ---- step 1: fetch RSS XML ----
    logger.info(f"[source {source_id}] Fetching {url}")
    resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    logger.info(f"[source {source_id}] HTTP {resp.status_code}, feedparser found {len(feed.entries)} entries")

    if feed.bozo:
        logger.warning(f"[source {source_id}] feedparser bozo: {feed.bozo_exception}")

    # ---- step 2: insert each entry (resilient per-entry) ----
    new_count = 0
    skipped = 0
    db = get_db()

    for entry in feed.entries[:max_articles]:
        title, link = _extract_title_link(entry)
        summary = _extract_summary(entry)
        published = _parse_published(entry)

        if not title and not link:
            skipped += 1
            continue

        if not link:
            # fallback: use entry.id if it looks like a URL
            link = entry.get("id", "").strip()
            if not link.startswith("http"):
                skipped += 1
                continue

        if not title:
            title = link  # last resort

        try:
            cur = db.execute(
                "INSERT OR IGNORE INTO articles (source_id, title, url, content, published_at, collected_at) VALUES (?,?,?,?,?,?)",
                (source_id, title[:500], link[:2000], summary, published, _now()),
            )
            if cur.lastrowid:
                new_count += 1
            else:
                skipped += 1  # duplicate URL
        except Exception as e:
            logger.warning(f"[source {source_id}] DB insert failed for {link}: {e}")
            skipped += 1
            continue

    db.commit()
    db.close()
    logger.info(f"[source {source_id}] new={new_count} skipped={skipped}")
    return new_count


def _extract_title_link(entry) -> tuple[str, str]:
    """Extract title and link from RSS/Atom entry, handling common field variants."""
    title = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()

    # Atom feeds often wrap link in a dict
    if not link:
        links = entry.get("links") or []
        for l in links:
            href = (l.get("href") or "").strip()
            if href:
                link = href
                break

    # Some feeds (e.g. Reddit) put the link in id
    if not link:
        link = (entry.get("id") or "").strip()
        if not link.startswith("http"):
            link = ""

    return title, link


def _extract_summary(entry) -> str | None:
    """Extract summary/content from RSS/Atom entry."""
    content = ""
    for field in ("content", "description", "summary"):
        val = entry.get(field, "")
        if isinstance(val, list):
            val = val[0].get("value", "") if val else ""
        if val:
            content = val
            break
    return content[:5000] if content else None


def collect_url_source(source_id: int, url: str) -> int:
    """Collect a single URL as an article."""
    db = get_db()
    try:
        cur = db.execute(
            "INSERT OR IGNORE INTO articles (source_id, title, url, collected_at) VALUES (?,?,?,?)",
            (source_id, url, url, _now()),
        )
        new_count = 1 if cur.lastrowid else 0
        db.commit()
    except Exception:
        db.rollback()
        new_count = 0
    db.close()
    return new_count


def run_collection(source_id: int | None = None) -> list[dict]:
    """Run full collection cycle. Returns per-source results list."""
    db = get_db()
    if source_id:
        rows = db.execute(
            "SELECT * FROM sources WHERE id=? AND enabled=1 AND status='active'",
            (source_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM sources WHERE enabled=1 AND status='active'"
        ).fetchall()
    db.close()

    logger.info(
        f"Collection starting: {len(rows)} active sources"
        + (f" (filtered to id={source_id})" if source_id else "")
    )
    for src in rows:
        logger.info(f"  Source id={src['id']} name='{src['name']}' type={src['type']} url={src['url'][:80]}")

    results = []
    total_new = 0
    for src in rows:
        try:
            if src["type"] == "rss":
                n = collect_rss(src["id"], src["url"])
            else:
                n = collect_url_source(src["id"], src["url"])
            total_new += n
            _log_collect(src["id"], "success", f"Collected {n} new articles", n)
            results.append({
                "source": src["name"],
                "source_id": src["id"],
                "new_articles": n,
                "status": "success",
            })
        except httpx.HTTPError as e:
            logger.warning(f"[source {src['id']}] HTTP error: {e}")
            _log_collect(src["id"], "error", f"HTTP {e}", 0)
            results.append({
                "source": src["name"],
                "source_id": src["id"],
                "new_articles": 0,
                "status": f"error: HTTP {e}",
            })
        except Exception as e:
            logger.exception(f"[source {src['id']}] Unexpected error: {e}")
            _log_collect(src["id"], "error", str(e)[:200], 0)
            results.append({
                "source": src["name"],
                "source_id": src["id"],
                "new_articles": 0,
                "status": f"error: {e}",
            })

    msg = f"Total new articles: {total_new}"
    errors = [r for r in results if r["status"] != "success"]
    if errors:
        msg += " | Errors: " + "; ".join(f"{e['source']}: {e['status']}" for e in errors)
    logger.info(f"Collection done: {msg}")

    results.sort(key=lambda r: r["source_id"])
    return results


def _log_collect(source_id: int, status: str, message: str, articles_new: int):
    db = get_db()
    db.execute(
        "INSERT INTO collect_log (source_id, status, message, articles_new, created_at) VALUES (?,?,?,?,?)",
        (source_id, status, message, articles_new, _now()),
    )
    db.commit()
    db.close()


def _parse_published(entry) -> str | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        try:
            dt = datetime(*struct[:6], tzinfo=timezone.utc)
            return dt.astimezone(BJT).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return entry.get("published") or entry.get("updated")
