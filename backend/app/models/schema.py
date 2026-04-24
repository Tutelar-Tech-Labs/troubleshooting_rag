from pydantic import BaseModel
from typing import List

class KBArticle(BaseModel):
    title: str
    url: str
    content: str

class AnalysisResponse(BaseModel):
    status: str = "active"
    detected_issue: str
    correlated_issue: str = ""
    root_cause: str
    user_impact: str
    troubleshooting_steps: str
    summary: str
    related_kbs: List[KBArticle]
    domain: str
    previous_errors: List[str] = []
    logs_used: List[str] = []
    logs_detected: List[str] = []
    confidence_score: float = 0.0

class IssueRequest(BaseModel):
    issue: str
