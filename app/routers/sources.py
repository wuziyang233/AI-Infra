from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
from app.models.database import get_db
from app.models.schemas import SourceCreate, SourceUpdate, SourceOut, InitDefaultsResult
from app.services.default_sources import DEFAULT_SOURCES

BJT = timezone(timedelta(hours=8))

def _now() -> str:
    return datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(type: str = None, enabled: int = None, category: str = None, status: str = None):
    db = get_db()
    q = "SELECT * FROM sources WHERE 1=1"
    params = []
    if type:
        q += " AND type=?"
        params.append(type)
    if enabled is not None:
        q += " AND enabled=?"
        params.append(enabled)
    if category:
        q += " AND category=?"
        params.append(category)
    if status:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY priority DESC, id"
    rows = db.execute(q, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("", response_model=SourceOut)
def create_source(body: SourceCreate):
    if body.type not in ("rss", "url"):
        raise HTTPException(400, "type must be rss or url")
    db = get_db()
    try:
        now = _now()
        cur = db.execute(
            """INSERT INTO sources (name, url, type, category, language, priority, description, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                body.name,
                body.url,
                body.type,
                body.category or "overseas_ai",
                body.language or "en",
                body.priority or 3,
                body.description or "",
                now, now,
            ),
        )
    except Exception:
        db.close()
        raise HTTPException(409, "该 URL 已存在")
    db.commit()
    row = db.execute("SELECT * FROM sources WHERE id=?", (cur.lastrowid,)).fetchone()
    db.close()
    return dict(row)


@router.put("/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourceUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Source not found")
    updates = {
        "name": body.name if body.name is not None else row["name"],
        "url": body.url if body.url is not None else row["url"],
        "enabled": body.enabled if body.enabled is not None else row["enabled"],
        "category": body.category if body.category is not None else row["category"],
        "language": body.language if body.language is not None else row["language"],
        "priority": body.priority if body.priority is not None else row["priority"],
        "status": body.status if body.status is not None else row["status"],
        "description": body.description if body.description is not None else row["description"],
    }
    db.execute(
        """UPDATE sources SET name=?, url=?, enabled=?, category=?, language=?,
           priority=?, status=?, description=?, updated_at=datetime('now','localtime') WHERE id=?""",
        (updates["name"], updates["url"], updates["enabled"], updates["category"],
         updates["language"], updates["priority"], updates["status"], updates["description"],
         source_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    db.close()
    return dict(row)


@router.delete("/{source_id}")
def delete_source(source_id: int):
    db = get_db()
    db.execute("DELETE FROM articles WHERE source_id=?", (source_id,))
    db.execute("DELETE FROM sources WHERE id=?", (source_id,))
    db.commit()
    db.close()
    return {"ok": True}


@router.post("/init-defaults", response_model=InitDefaultsResult)
def init_default_sources():
    """Initialize default sources. Skips URLs that already exist."""
    db = get_db()
    created = 0
    skipped = 0
    created_rows = []
    now = _now()
    for name, url, typ, category, lang, priority, status, desc in DEFAULT_SOURCES:
        try:
            cur = db.execute(
                """INSERT INTO sources (name, url, type, category, language, priority, status, description, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (name, url, typ, category, lang, priority, status, desc, now, now),
            )
            if cur.lastrowid:
                created += 1
                created_rows.append(dict(db.execute("SELECT * FROM sources WHERE id=?", (cur.lastrowid,)).fetchone()))
        except Exception:
            skipped += 1
    db.commit()
    db.close()
    return InitDefaultsResult(created=created, skipped=skipped, sources=created_rows)
