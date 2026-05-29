from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# ── Request Schemas ──

class SourceCreate(BaseModel):
    name: str
    url: str
    type: str  # "rss" | "url"
    category: Optional[str] = None
    language: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[int] = None
    category: Optional[str] = None
    language: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None

class QuestionRequest(BaseModel):
    question: str

class CollectRequest(BaseModel):
    source_id: Optional[int] = None

class ReportGenerateRequest(BaseModel):
    date: Optional[str] = None  # "2026-04-25", 默认今天


# ── Response Schemas ──

class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    type: str
    enabled: int
    category: Optional[str] = None
    language: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    updated_at: str

class InitDefaultsResult(BaseModel):
    created: int
    skipped: int
    sources: list[SourceOut]

class CollectSourceResult(BaseModel):
    source: str
    source_id: int
    new_articles: int
    status: str  # "success" | "error"

class CollectResult(BaseModel):
    total_new: int
    results: list[CollectSourceResult]
    message: str

class ArticleOut(BaseModel):
    id: int
    source_id: int
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[str] = None
    collected_at: str
    relevance: float

class ArticleDetail(ArticleOut):
    content: Optional[str] = None
    insights: list["ArticleInsightOut"] = []

class ArticleInsightOut(BaseModel):
    id: int
    category: str
    content: str
    confidence: float

class ReportSectionOut(BaseModel):
    section_type: str
    title: str
    content: str
    sort_order: int

class ReportOut(BaseModel):
    id: int
    report_date: str
    title: str
    summary: Optional[str] = None
    article_count: int
    created_at: str
    sections: list[ReportSectionOut] = []

class ReportLatest(BaseModel):
    report_date: str
    title: str
    summary: Optional[str] = None
    markdown: str

class QAHistoryOut(BaseModel):
    id: int
    question: str
    answer: str
    sources: Optional[str] = None
    created_at: str

class QAAnswer(BaseModel):
    answer: str
    sources: list[dict] = []

class CollectLogOut(BaseModel):
    id: int
    source_id: Optional[int] = None
    status: str
    message: Optional[str] = None
    articles_new: int
    created_at: str

class FeishuPushLogOut(BaseModel):
    id: int
    report_date: Optional[str] = None
    status: str
    message: Optional[str] = None
    response_code: Optional[int] = None
    created_at: str

class HealthOut(BaseModel):
    status: str
    chroma: str
    llm: str
