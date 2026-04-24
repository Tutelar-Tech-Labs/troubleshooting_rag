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


import zipfile
import tempfile
import shutil
from typing import Optional
from fastapi import Form

@router.post("/analyze")
async def analyze_log(
    file: UploadFile = File(...),
    start_time: str = Form(None),
    end_time: str = Form(None)
):
    if not file.filename.endswith(('.log', '.txt', '.zip')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .log, .txt, and .zip are supported.")
    
    content = await file.read()
    logs_dict = {}

    import os
    EXTRACT_PATH = os.path.abspath("backend/data/extracted_logs/")
    os.makedirs(EXTRACT_PATH, exist_ok=True)
    
    if file.filename.endswith('.zip'):
        # Clean previous extraction
        for old_file in os.listdir(EXTRACT_PATH):
            old_path = os.path.join(EXTRACT_PATH, old_file)
            try:
                if os.path.isfile(old_path):
                    os.remove(old_path)
            except:
                pass
        
        zip_path = os.path.join(EXTRACT_PATH, "upload.zip")
        with open(zip_path, "wb") as f:
            f.write(content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_PATH)
            
        print("[ZIP] Extracted files:", os.listdir(EXTRACT_PATH))
                
        for root, dirs, files in os.walk(EXTRACT_PATH):
            for f in files:
                if f.endswith(('.log', '.txt')):
                    file_path = os.path.join(root, f)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as log_f:
                            txt = log_f.read()
                            f_lower = f.lower()
                            line_count = len(txt.splitlines())
                            
                            if "pangps" in f_lower:
                                if "pangps" not in logs_dict or line_count > len(logs_dict["pangps"].splitlines()):
                                    logs_dict["pangps"] = txt
                                    print(f"[ZIP] Mapped {f} -> pangps ({line_count} lines)")
                            elif "pangpa" in f_lower and "event" not in f_lower:
                                if "pangpa" not in logs_dict or line_count > len(logs_dict["pangpa"].splitlines()):
                                    logs_dict["pangpa"] = txt
                                    print(f"[ZIP] Mapped {f} -> pangpa ({line_count} lines)")
                            elif "event" in f_lower:
                                logs_dict["event"] = txt
                                print(f"[ZIP] Mapped {f} -> event ({line_count} lines)")
                            elif "hip" in f_lower:
                                logs_dict["hip"] = txt
                            elif "msi" in f_lower:
                                logs_dict["msi"] = txt
                            elif "system" in f_lower:
                                logs_dict["system"] = txt
                            elif "route" in f_lower:
                                logs_dict["route"] = txt
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
        
        print("[ZIP] Detected logs:", {k: len(v.splitlines()) for k, v in logs_dict.items()})
        
    else:
        # Single file upload
        txt = content.decode('utf-8', errors="ignore")
        line_count = len(txt.splitlines())
        print(f"[SINGLE FILE] {file.filename}: {line_count} lines, {len(txt)} chars")
        print(f"[SINGLE FILE] First 200 chars: {txt[:200]}")
        
        fname = file.filename.lower()
        
        # First try filename-based detection
        if "pangps" in fname:
            logs_dict["pangps"] = txt
        elif "pangpa" in fname and "event" not in fname:
            logs_dict["pangpa"] = txt
        elif "event" in fname:
            logs_dict["event"] = txt
        elif "hip" in fname:
            logs_dict["hip"] = txt
        elif "msi" in fname:
            logs_dict["msi"] = txt
        else:
            # Content-based detection: scan first 500 chars for GP indicators
            sample = txt[:2000].lower()
            if any(k in sample for k in ["pangps", "pangpa", "gpagent", "globalprotect", "portal", "gateway", "enforcer", "tunnel"]):
                # It's GP log content — detect which type
                if "pangpa" in sample or "gpagent" in sample:
                    logs_dict["pangpa"] = txt
                    print(f"[SINGLE FILE] Content-detected as pangpa log")
                else:
                    logs_dict["pangps"] = txt
                    print(f"[SINGLE FILE] Content-detected as pangps log")
            else:
                # Fallback: treat as pangps (primary)
                logs_dict["pangps"] = txt
                print(f"[SINGLE FILE] No GP keywords in content, using as pangps fallback")
        
    async def event_generator():
        status_queue = asyncio.Queue()

        async def on_status(status: str):
            await status_queue.put(status)

        async def run_analysis():
            try:
                result = await rag_service.analyze_logs(logs_dict, start_time=start_time, end_time=end_time, on_status=on_status)
                await status_queue.put({"result": result})
            except asyncio.CancelledError:
                print("Analysis task cancelled.")
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error during analysis: {e}")
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
                            status=result.get("status", "active"),
                            detected_issue=result["detected_issue"],
                            correlated_issue=result.get("correlated_issue", ""),
                            root_cause=result["root_cause"],
                            user_impact=result["user_impact"],
                            troubleshooting_steps=result["troubleshooting_steps"],
                            summary=result["summary"],
                            related_kbs=[KBArticle(**kb) for kb in result["related_kbs"]],
                            domain=result["domain"],
                            previous_errors=result.get("previous_errors", []),
                            logs_used=result.get("logs_used", []),
                            logs_detected=result.get("logs_detected", []),
                            confidence_score=result.get("confidence_score", 0.0)
                        )
                        yield f"data: {json.dumps({'result': final_response.model_dump() if hasattr(final_response, 'model_dump') else final_response.dict()})}\n\n"
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

