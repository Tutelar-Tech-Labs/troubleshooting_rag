from pydantic import BaseModel
from typing import List

class KBArticle(BaseModel):
    title: str
    url: str
    content: str

class AnalysisResponse(BaseModel):
    detected_issue: str
    root_cause: str
    user_impact: str
    troubleshooting_steps: str
    summary: str
    related_kbs: List[KBArticle]
    domain: str

class IssueRequest(BaseModel):
    issue: str
