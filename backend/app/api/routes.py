from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.rag_service import RAGService
from app.models.schema import AnalysisResponse, KBArticle, IssueRequest
import os

router = APIRouter()

# Initialize RAG service which coordinates LLM and FAISS
rag_service = RAGService()


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_log(file: UploadFile = File(...)):
    if not file.filename.endswith(('.log', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .log and .txt are supported.")
    
    try:
        content = await file.read()
        log_text = content.decode('utf-8')
        
        # Perform full analysis using the RAG pipeline
        result = await rag_service.analyze_log(log_text)
        
        return AnalysisResponse(
            detected_issue=result["detected_issue"],
            root_cause=result["root_cause"],
            user_impact=result["user_impact"],
            troubleshooting_steps=result["troubleshooting_steps"],
            summary=result["summary"],
            related_kbs=[KBArticle(**kb) for kb in result["related_kbs"]],
            domain=result["domain"],
        )
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-issue", response_model=AnalysisResponse)
async def analyze_direct_issue(request: IssueRequest):
    try:
        # Perform analysis starting directly from the issue
        result = await rag_service.analyze_issue(request.issue)
        
        return AnalysisResponse(
            detected_issue=result["detected_issue"],
            root_cause=result["root_cause"],
            user_impact=result["user_impact"],
            troubleshooting_steps=result["troubleshooting_steps"],
            summary=result["summary"],
            related_kbs=[KBArticle(**kb) for kb in result["related_kbs"]],
            domain=result["domain"],
        )
    except Exception as e:
        print(f"Error during direct issue analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
