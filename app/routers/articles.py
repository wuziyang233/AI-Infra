from fastapi import APIRouter, HTTPException, Query
from app.models.database import get_db
from app.models.schemas import ArticleOut, ArticleDetail

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleOut])
def list_articles(
    date: str = None,
    source_id: int = None,
    relevance_min: float = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    db = get_db()
    q = "SELECT * FROM articles WHERE 1=1"
    params = []
    if date:
        q += " AND date(collected_at)=?"
        params.append(date)
    if source_id:
        q += " AND source_id=?"
        params.append(source_id)
    if relevance_min is not None:
        q += " AND relevance >= ?"
        params.append(relevance_min)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([size, (page - 1) * size])
    rows = db.execute(q, params).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Article not found")
    insights = db.execute(
        "SELECT * FROM article_insights WHERE article_id=? ORDER BY id", (article_id,)
    ).fetchall()
    db.close()
    result = dict(row)
    result["insights"] = [dict(i) for i in insights]
    return result
