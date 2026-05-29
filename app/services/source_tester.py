from __future__ import annotations

import time
from typing import Any

import feedparser
import httpx

from app.services.collector import HEADERS


def test_source(url: str, source_type: str = "rss") -> dict[str, Any]:
    start = time.perf_counter()
    try:
        if source_type == "rss":
            result = _test_rss(url)
        else:
            result = _test_url(url)
        result["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return result
    except Exception as e:
        return {
            "ok": False,
            "status_code": None,
            "entry_count": 0,
            "latest_title": None,
            "latest_url": None,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            "message": str(e)[:300],
        }


def _test_rss(url: str) -> dict[str, Any]:
    resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
    feed = feedparser.parse(resp.text)
    entry_count = len(feed.entries)
    latest = feed.entries[0] if entry_count else {}
    ok = resp.status_code < 400 and entry_count > 0
    message = "ok" if ok else f"HTTP {resp.status_code}, entries={entry_count}"
    if feed.bozo:
        message += f", parse_warning={str(feed.bozo_exception)[:120]}"
    return {
        "ok": ok,
        "status_code": resp.status_code,
        "entry_count": entry_count,
        "latest_title": latest.get("title"),
        "latest_url": latest.get("link") or latest.get("id"),
        "message": message,
    }


def _test_url(url: str) -> dict[str, Any]:
    resp = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
    ok = resp.status_code < 400
    return {
        "ok": ok,
        "status_code": resp.status_code,
        "entry_count": 1 if ok else 0,
        "latest_title": None,
        "latest_url": url if ok else None,
        "message": "ok" if ok else f"HTTP {resp.status_code}",
    }
