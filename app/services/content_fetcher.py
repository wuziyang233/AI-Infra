from __future__ import annotations

import logging
import httpx
from readability import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIInfraIntel/1.0; +https://github.com)"
}


def fetch_content(url: str) -> str | None:
    """Extract main text from a URL using readability."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        doc = Document(resp.text)
        html = doc.summary()
        text = BeautifulSoup(html, "lxml").get_text(separator="\n", strip=True)
        return text[:8000]  # cap at 8K chars
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def fill_article_contents(limit: int = 20):
    """Fetch full content for articles that don't have it yet."""
    from app.models.database import get_db

    db = get_db()
    rows = db.execute(
        "SELECT id, url FROM articles WHERE content IS NULL OR content = '' ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    db.close()

    for row in rows:
        text = fetch_content(row["url"])
        if text:
            conn = get_db()
            conn.execute("UPDATE articles SET content=? WHERE id=?", (text, row["id"]))
            conn.commit()
            conn.close()
            logger.info(f"Fetched content for article {row['id']}")
