from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
from app.models.database import get_db, get_chroma

logger = logging.getLogger(__name__)
client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
BJT = timezone(timedelta(hours=8))

QA_SYSTEM = """你是一个AI基础设施领域的决策情报助手。请根据提供的参考信息回答用户问题。

规则：
1. 优先使用参考信息，如果参考信息不足以回答，可以使用你的知识补充但要注明
2. 回答中引用的每条关键信息末尾用方括号标注来源编号，如 [1]、[2]
3. 回答简洁，不超过500字
4. 在回答末尾列出参考来源"""


def answer_question(question: str) -> dict:
    """RAG-based Q&A: retrieve from ChromaDB, then answer with DeepSeek."""
    # Retrieve from both collections
    context_chunks = []
    sources_map = {}

    try:
        chroma = get_chroma()
    except Exception as e:
        logger.error(f"ChromaDB unavailable: {e}")
        return _direct_answer(question)

    try:
        article_coll = chroma.get_collection("article_chunks")
        results = article_coll.query(query_texts=[question], n_results=5)
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            ref_id = len(context_chunks) + 1
            context_chunks.append(doc)
            sources_map[ref_id] = {"title": meta.get("title", ""), "url": meta.get("url", "")}
    except Exception as e:
        logger.warning(f"Article retrieval failed: {e}")

    try:
        report_coll = chroma.get_collection("report_chunks")
        results = report_coll.query(query_texts=[question], n_results=3)
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            ref_id = len(context_chunks) + 1
            context_chunks.append(doc)
            sources_map[ref_id] = {
                "title": f"日报 {meta.get('report_date', '')} - {meta.get('section_type', '')}",
                "url": "",
            }
    except Exception as e:
        logger.warning(f"Report retrieval failed: {e}")

    if not context_chunks:
        return _direct_answer(question)

    context_text = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context_chunks))

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": QA_SYSTEM},
                {"role": "user", "content": f"参考信息：\n{context_text}\n\n问题：{question}"},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"QA LLM call failed: {e}")
        answer = "抱歉，模型调用失败，请稍后重试。"

    # Save to history
    db = get_db()
    db.execute(
        "INSERT INTO qa_history (question, answer, sources, created_at) VALUES (?,?,?,?)",
        (question, answer, json.dumps(list(sources_map.values()), ensure_ascii=False),
         datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")),
    )
    db.commit()
    db.close()

    return {"answer": answer, "sources": list(sources_map.values())}


def _direct_answer(question: str) -> dict:
    """Fallback: answer without retrieval."""
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个AI基础设施领域的决策情报助手。回答简洁专业，不超过500字。"},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        answer = resp.choices[0].message.content.strip()
    except Exception as e:
        answer = "抱歉，模型调用失败，请稍后重试。"
    return {"answer": answer, "sources": []}
