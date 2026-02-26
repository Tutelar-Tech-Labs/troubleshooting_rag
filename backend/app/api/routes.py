from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from app.services.rag_service import RAGService
from app.models.schema import AnalysisResponse, KBArticle, IssueRequest
import os
import json
import asyncio

router = APIRouter()

# Initialize RAG service which coordinates LLM and FAISS
rag_service = RAGService()


@router.post("/analyze")
async def analyze_log(file: UploadFile = File(...)):
    if not file.filename.endswith(('.log', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .log and .txt are supported.")
    
    content = await file.read()
    log_text = content.decode('utf-8')

    async def event_generator():
        status_queue = asyncio.Queue()

        async def on_status(status: str):
            await status_queue.put(status)

        async def run_analysis():
            try:
                result = await rag_service.analyze_log(log_text, on_status=on_status)
                await status_queue.put({"result": result})
            except asyncio.CancelledError:
                print("Analysis task cancelled.")
                raise
            except Exception as e:
                print(f"Error during analysis: {e}")
                await status_queue.put({"error": str(e)})
            finally:
                await status_queue.put(None) # Sentinel to end

        analysis_task = asyncio.create_task(run_analysis())

        try:
            while True:
                item = await status_queue.get()
                if item is None:
                    break
                
                if isinstance(item, str):
                    yield f"data: {json.dumps({'status': item})}\n\n"
                elif isinstance(item, dict):
                    if "result" in item:
                        result = item["result"]
                        final_response = AnalysisResponse(
                            detected_issue=result["detected_issue"],
                            root_cause=result["root_cause"],
                            user_impact=result["user_impact"],
                            troubleshooting_steps=result["troubleshooting_steps"],
                            summary=result["summary"],
                            related_kbs=[KBArticle(**kb) for kb in result["related_kbs"]],
                            domain=result["domain"],
                        )
                        yield f"data: {json.dumps({'result': final_response.dict()})}\n\n"
                    elif "error" in item:
                        yield f"data: {json.dumps({'error': item['error']})}\n\n"
        except asyncio.CancelledError:
            print("Client disconnected, cancelling analysis task.")
            analysis_task.cancel()
            try:
                await analysis_task
            except asyncio.CancelledError:
                pass
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/analyze-issue")
async def analyze_direct_issue(request: IssueRequest):
    async def event_generator():
        status_queue = asyncio.Queue()

        async def on_status(status: str):
            await status_queue.put(status)

        async def run_analysis():
            try:
                result = await rag_service.analyze_issue(request.issue, on_status=on_status)
                await status_queue.put({"result": result})
            except asyncio.CancelledError:
                print("Direct issue analysis task cancelled.")
                raise
            except Exception as e:
                print(f"Error during direct issue analysis: {e}")
                await status_queue.put({"error": str(e)})
            finally:
                await status_queue.put(None)

        analysis_task = asyncio.create_task(run_analysis())

        try:
            while True:
                item = await status_queue.get()
                if item is None:
                    break
                
                if isinstance(item, str):
                    yield f"data: {json.dumps({'status': item})}\n\n"
                elif isinstance(item, dict):
                    if "result" in item:
                        result = item["result"]
                        final_response = AnalysisResponse(
                            detected_issue=result["detected_issue"],
                            root_cause=result["root_cause"],
                            user_impact=result["user_impact"],
                            troubleshooting_steps=result["troubleshooting_steps"],
                            summary=result["summary"],
                            related_kbs=[KBArticle(**kb) for kb in result["related_kbs"]],
                            domain=result["domain"],
                        )
                        yield f"data: {json.dumps({'result': final_response.dict()})}\n\n"
                    elif "error" in item:
                        yield f"data: {json.dumps({'error': item['error']})}\n\n"
        except asyncio.CancelledError:
            print("Client disconnected, cancelling direct issue analysis task.")
            analysis_task.cancel()
            try:
                await analysis_task
            except asyncio.CancelledError:
                pass
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")

