from fastapi import APIRouter
from app.models.database import get_db
from app.models.schemas import QuestionRequest, QAAnswer, QAHistoryOut
from app.services.qa_service import answer_question

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("", response_model=QAAnswer)
def ask(body: QuestionRequest):
    return answer_question(body.question)


@router.get("/history", response_model=list[QAHistoryOut])
def history(limit: int = 50):
    db = get_db()
    rows = db.execute("SELECT * FROM qa_history ORDER BY id DESC LIMIT ?", (min(limit, 100),)).fetchall()
    db.close()
    return [dict(r) for r in rows]
