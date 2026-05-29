from fastapi import APIRouter, Query
from app.models.database import get_db
from app.models.schemas import CollectLogOut, CollectResult
from app.services.collector import run_collection

router = APIRouter(prefix="/api/collect", tags=["collect"])


@router.post("", response_model=CollectResult)
def trigger_collect(source_id: int = Query(None)):
    results = run_collection(source_id=source_id)
    total_new = sum(r["new_articles"] for r in results)
    errors = [r for r in results if r["status"] != "success"]
    msg = f"采集完成：共 {total_new} 篇新文章"
    if errors:
        msg += " | " + "; ".join(f"{e['source']}: {e['status']}" for e in errors)
    return CollectResult(total_new=total_new, results=results, message=msg)


@router.get("/status", response_model=list[CollectLogOut])
def collect_status(limit: int = Query(10, ge=1, le=100)):
    db = get_db()
    rows = db.execute("SELECT * FROM collect_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    db.close()
    return [dict(r) for r in rows]
