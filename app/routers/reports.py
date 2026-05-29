from fastapi import APIRouter, HTTPException, Query
from app.models.database import get_db
from app.models.schemas import FeishuPushLogOut, ReportOut, ReportLatest, ReportGenerateRequest
from app.services.reporter import generate_report
from app.services.feishu import FeishuConfigError, list_push_logs, push_latest_report_to_feishu, push_report_to_feishu

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
def trigger_report(body: ReportGenerateRequest = None):
    date = body.date if body else None
    try:
        report_id = generate_report(date)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    if report_id is None:
        raise HTTPException(400, "Report already exists or no articles available")
    return {"report_id": report_id}


@router.post("/push-feishu")
def push_latest_to_feishu():
    try:
        return push_latest_report_to_feishu()
    except FeishuConfigError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.post("/{date}/push-feishu")
def push_date_to_feishu(date: str):
    try:
        return push_report_to_feishu(date)
    except FeishuConfigError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@router.get("/push-feishu/status", response_model=list[FeishuPushLogOut])
def feishu_push_status(limit: int = Query(10, ge=1, le=100)):
    return list_push_logs(limit)


@router.get("", response_model=list[ReportOut])
def list_reports(page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=50)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM daily_reports ORDER BY id DESC LIMIT ? OFFSET ?",
        (size, (page - 1) * size),
    ).fetchall()
    result = []
    for r in rows:
        secs = db.execute(
            "SELECT * FROM report_sections WHERE report_id=? ORDER BY sort_order", (r["id"],)
        ).fetchall()
        item = dict(r)
        item["sections"] = [dict(s) for s in secs]
        result.append(item)
    db.close()
    return result


@router.get("/latest", response_model=ReportLatest)
def latest_report():
    db = get_db()
    row = db.execute("SELECT * FROM daily_reports ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "No reports found")
    db.close()

    with open(row["file_path"], "r", encoding="utf-8") as f:
        markdown = f.read()

    return ReportLatest(
        report_date=row["report_date"],
        title=row["title"],
        summary=row["summary"],
        markdown=markdown,
    )


@router.get("/{date}", response_model=ReportOut)
def get_report_by_date(date: str):
    db = get_db()
    row = db.execute("SELECT * FROM daily_reports WHERE report_date=?", (date,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, f"No report for {date}")
    secs = db.execute(
        "SELECT * FROM report_sections WHERE report_id=? ORDER BY sort_order", (row["id"],)
    ).fetchall()
    db.close()
    result = dict(row)
    result["sections"] = [dict(s) for s in secs]
    return result
