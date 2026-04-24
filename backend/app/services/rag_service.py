from app.services.local_llm import LocalLLMService
from app.services.faiss_service import FAISSService
from app.services.scenario_detector import detect_scenario
from app.services.domain_detector import detect_domain
from app.services.panorama_scenarios import detect_panorama_scenario
from app.utils.log_processor import (
    filter_logs_by_time, correlate_logs, detect_resolution, 
    extract_error_history, create_time_chunks, create_additional_chunks,
    smart_prioritize_chunks, intelligent_fallback, detect_gp_stages
)
from typing import Dict, Any, List, Optional, Callable, Awaitable
import json
import asyncio
import os

LOG_PATH = "backend/logs/llm_trace.log"
os.makedirs("backend/logs", exist_ok=True)

def log_trace(message):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")

class RAGService:
    def __init__(self):
        self.llm = LocalLLMService()
        self.faiss = FAISSService()

    async def analyze_logs(
        self, logs_dict: Dict[str, str], 
        start_time: str = None, 
        end_time: str = None, 
        on_status: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Multi-Log RAG flow: 
        Time filtering -> Log chunking -> Cross-log correlation -> FAISS relevance search -> LLM synthesis
        """
        analysis_status = {
            "stage": "Log received",
            "progress": "Initializing analysis pipeline",
            "total_chunks": 0,
            "current_chunk": 0,
            "messages": ["Log received"]
        }
        
        async def broadcast_status(update_dict: dict):
            if on_status:
                analysis_status.update(update_dict)
                if "stage" in update_dict and update_dict["stage"] not in analysis_status["messages"]:
                    analysis_status["messages"].append(update_dict["stage"])
                await on_status(json.dumps(analysis_status))
                
        async def internal_on_status(msg: str):
            try:
                data = json.loads(msg)
                await broadcast_status(data)
            except:
                analysis_status["messages"].append(msg)
                await broadcast_status({})

        # Stage 7 Initial Clear
        open(LOG_PATH, "w").close()

        # 1. Time Filtering (Part 2)
        from_time = start_time
        to_time = end_time

        # Log pre-filter sizes for chunk reduction verification
        pre_filter_sizes = {k: len(v.splitlines()) for k, v in logs_dict.items()}
        print("[CHUNK REDUCTION] BEFORE time filter:", pre_filter_sizes)
        log_trace(f"[CHUNK REDUCTION] BEFORE time filter: {pre_filter_sizes}")

        if from_time and to_time:
            await broadcast_status({"stage": "Applying time filter", "progress": f"Filtering logs between {from_time} and {to_time}"})
            log_trace("[TIME FILTER]")
            log_trace(f"Range: {from_time} to {to_time}")
            for key in logs_dict.keys():
                if key in ["pangps", "pangpa", "event"]:
                    logs_dict[key] = await asyncio.to_thread(filter_logs_by_time, logs_dict[key], from_time, to_time)
            await asyncio.sleep(0.1)

        post_filter_sizes = {k: len(v.splitlines()) for k, v in logs_dict.items()}
        print("[CHUNK REDUCTION] AFTER time filter:", post_filter_sizes)
        log_trace(f"[CHUNK REDUCTION] AFTER time filter: {post_filter_sizes}")

        # Broadcast time filter results to frontend
        if from_time and to_time:
            total_before = sum(pre_filter_sizes.get(k, 0) for k in ["pangps", "pangpa", "event"])
            total_after = sum(post_filter_sizes.get(k, 0) for k in ["pangps", "pangpa", "event"])
            if total_before == total_after:
                await broadcast_status({"stage": "⚠ Time filter did not reduce logs", "progress": f"Check format: MM/DD HH:MM or MM/DD HH:MM:SS"})
                log_trace("[TIME FILTER WARNING] No reduction — before == after")
            else:
                reduction_pct = round((1 - total_after / max(total_before, 1)) * 100)
                await broadcast_status({"stage": f"Time filter applied: {reduction_pct}% reduction", "progress": f"{total_before} → {total_after} lines"})
            await asyncio.sleep(0.1)

        pangps_log = logs_dict.get("pangps", "")
        pangpa_log = logs_dict.get("pangpa", "")
        event_log = logs_dict.get("event", "")

        # 2. Extract Error History (Stage 6)
        previous_errors = extract_error_history(pangps_log, pangpa_log, event_log)
        previous_errors = previous_errors[-20:]
        print("[ERROR HISTORY] Count:", len(previous_errors))
        log_trace("[ERROR HISTORY]")
        for err in previous_errors:
            log_trace(err)

        # 3. GP Stage Detection (NEW - Stage-Based Reasoning)
        if on_status: await on_status(json.dumps({"stage": "Detecting GP connection stages...", "progress": "Scanning for portal, gateway, tunnel markers"}))
        stage_analysis = detect_gp_stages(pangps_log, pangpa_log)
        log_trace("[GP STAGES]")
        log_trace(stage_analysis["stage_flow"])
        if stage_analysis["failure_stage"]:
            log_trace(f"Failure at: {stage_analysis['failure_stage']}")
            log_trace(f"Category: {stage_analysis['failure_category']}")
        await broadcast_status({
            "stage": f"GP Stages: {len(stage_analysis['stages_found'])} detected" + (f" | Failure at: {stage_analysis['failure_stage']}" if stage_analysis['failure_stage'] else " | All stages OK"),
            "progress": stage_analysis['stage_flow'][:100]
        })
        await asyncio.sleep(0.1)

        # 4. Contextual Chunking & Cross-Log Detection (Part 3, 4, 16)
        if on_status: await on_status(json.dumps({"stage": "Correlating with pangpa...", "progress": "Detecting cross log issues"}))
        
        correlated_issue = await asyncio.to_thread(correlate_logs, pangps_log, pangpa_log)
        print("[CORRELATION] Issue:", correlated_issue)
        log_trace("[CORRELATION]")
        log_trace(correlated_issue)
        
        if on_status: await on_status(json.dumps({"stage": "Categorizing logs...", "progress": "Checking domain applicability"}))
        full_log_text = "\n".join(logs_dict.values())
        domain = detect_domain(full_log_text)

        if domain != "globalprotect":
            await asyncio.sleep(0.1)
            if on_status: await on_status(json.dumps({"stage": "Completed", "progress": "Analysis complete"}))
            return {
                "status": "not_relevant",
                "detected_issue": "Non-GlobalProtect issue detected",
                "correlated_issue": "Non-GlobalProtect issue detected",
                "root_cause": "Logs indicate endpoint/application issue (e.g., Zoom, Teams, local app errors).",
                "user_impact": "No VPN or GlobalProtect impact.",
                "troubleshooting_steps": "1. Check application permissions.\n2. Reinstall application.\n3. Verify OS-level access.",
                "summary": "This issue is unrelated to GlobalProtect or PAN-OS.",
                "related_kbs": [],
                "domain": "endpoint",
                "previous_errors": previous_errors,
                "logs_used": list(logs_dict.keys()),
                "logs_detected": list(logs_dict.keys()),
                "confidence_score": 1.0
            }

        # 4. Multi-Log Aware Chunking (Part 5 + Stage 4)
        chunks = []
        chunks += create_time_chunks(pangps_log, pangpa_log)
        chunks += create_additional_chunks(logs_dict.get("event", ""), logs_dict.get("system", ""))
        
        # Filter strictly
        chunks = [c for c in chunks if c and c.strip()]
        
        for i, chunk in enumerate(chunks):
            log_trace(f"[CHUNK {i+1}]")
            log_trace(chunk[:200])
        
        print("[CHUNKING] Total chunks:", len(chunks))
        print("[CHUNKING] Sample chunk:", chunks[0][:200] if chunks else "")

        # Smart chunk prioritization: error-heavy chunks first for LLM
        # Level 1: Top smart chunks → FAISS retrieval (focused, not all 800+)
        # Level 2: Top smart chunks → LLM input
        llm_chunks = smart_prioritize_chunks(chunks, max_for_llm=10)
        print(f"[SMART CHUNKS] {len(llm_chunks)} prioritized for LLM out of {len(chunks)} total")
        log_trace(f"[SMART CHUNKS] {len(llm_chunks)} prioritized for LLM out of {len(chunks)} total")

        # Broadcast chunk stats to frontend live terminal
        await broadcast_status({
            "stage": f"Chunking complete: {len(chunks)} total → {len(llm_chunks)} focused",
            "progress": f"Using top {len(llm_chunks)} error-heavy chunks for analysis"
        })
        await asyncio.sleep(0.1)

        # Combine top prioritized chunk for neural extraction
        combined_logs_preview = llm_chunks[0] if llm_chunks else ""

        # Use LLM to extract primary issue from the first contextual chunk
        if on_status: await on_status(json.dumps({"stage": "Analyzing pangps...", "progress": "Extracting neural issue"}))
        neural_detected_issue = await self.llm.extract_issue(combined_logs_preview, on_status=internal_on_status)
        
        final_detected_issue = correlated_issue

        # Intelligent fallback: if correlation returned nothing useful, use error history
        if final_detected_issue == "No major correlated issue detected":
            final_detected_issue = intelligent_fallback(previous_errors)
            print("[FALLBACK] Using intelligent fallback:", final_detected_issue)
            log_trace("[FALLBACK]")
            log_trace(final_detected_issue)

        # Create LLM Trace Log (Part 11) - Modified cleanly now by Stage 7.
        log_trace(f"\n[ANALYSIS RUN]\nIssue: {final_detected_issue}\nDomain: {domain}\n")

        # 6. Resolution Detection (Stage 5)
        if on_status: await on_status(json.dumps({"stage": "Checking resolution...", "progress": "Checking last log chunks for resolution status"}))
        resolution_status = detect_resolution(pangps_log, pangpa_log)
        print("[RESOLUTION] Status:", resolution_status)

        return await self.analyze_issue(
            detected_issue=final_detected_issue, 
            filtered_log=combined_logs_preview, 
            domain=domain,
            previous_errors=previous_errors,
            logs_used=list(logs_dict.keys()),
            resolution_status=resolution_status,
            chunks=chunks,
            stage_analysis=stage_analysis,
            on_status=internal_on_status
        )

    async def analyze_issue(
        self, detected_issue: str, filtered_log: str = "", domain: Optional[str] = None, 
        previous_errors: List[str] = None, logs_used: List[str] = None,
        resolution_status: str = "active",
        chunks: List[str] = None,
        stage_analysis: Dict[str, Any] = None,
        on_status: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        
        if previous_errors is None: previous_errors = []
        if logs_used is None: logs_used = []
        if chunks is None: chunks = []
        if stage_analysis is None: stage_analysis = {"stages_found": [], "stage_flow": "", "failure_stage": None, "failure_category": "unknown", "failure_lines": []}

        try:
            scenario_context = filtered_log if filtered_log else detected_issue
    
            if domain is None:
                if on_status: await on_status("Detecting operation domain...")
                domain = detect_domain(scenario_context)
    
            await asyncio.sleep(0)
            
            if on_status: await on_status("Scenario intelligence and pattern mapping...")
            panorama_scenario = None
            scenario = None
    
            if domain == "panorama_config":
                panorama_scenario = detect_panorama_scenario(scenario_context)
            elif domain == "globalprotect":
                scenario = detect_scenario(scenario_context, detected_issue)
    
            base_query = detected_issue
            if panorama_scenario:
                base_query = panorama_scenario["detected_issue"]
            elif scenario and "faiss_query" in scenario:
                base_query = scenario["faiss_query"]
    
            # Enhanced FAISS Query (Part 9) — Aligned with GP Stage Failure
            failure_cat = stage_analysis.get("failure_category", "unknown")
            if domain == "globalprotect":
                # Align FAISS search with detected failure stage
                category_focus = {
                    "portal_connectivity": "portal connectivity prelogin",
                    "authentication": "authentication gateway login credentials",
                    "network_ssl": "tunnel SSL socket network connection",
                    "network_discovery": "network discovery gateway selection",
                    "unknown": "VPN tunnel auth service failure"
                }
                focus = category_focus.get(failure_cat, "VPN tunnel auth service failure")
                faiss_query = f"Issue: {base_query} Focus: {focus} PAN-OS GlobalProtect troubleshooting"
            elif domain == "panorama_config":
                faiss_query = f"Issue: {base_query} panorama commit configuration dependency PAN-OS troubleshooting"
            elif domain == "prisma":
                faiss_query = f"Issue: {base_query} prisma remote network cloud services PAN-OS troubleshooting"
            elif domain == "endpoint":
                faiss_query = f"Issue: {base_query} Zoom Teams endpoint connection PAN-OS troubleshooting"
            else:
                faiss_query = f"Issue: {base_query} PAN-OS troubleshooting"

            log_trace(f"[FAISS QUERY]\n{faiss_query}\n")
    
            # 7. Domain-aware FAISS Search (Enhanced with Relevance Filter - Part 10)
            top_chunks = []
            if domain == "globalprotect":
                if on_status: await on_status(json.dumps({"stage": "Searching KB...", "progress": "KB vector retrieval and ranking"}))
                await asyncio.sleep(0)
    
                # Use ONLY smart prioritized chunks for FAISS (not all 800+)
                results = []
                for chunk in chunks[:10]:  # Safety cap: max 10 chunks for FAISS
                    results += self.faiss.search(chunk, domain=domain, top_k=3)
                
                # Also search with the correlated issue directly (primary vector)
                results += self.faiss.search(faiss_query, domain=domain, top_k=5)
                
                top_chunks = results
                
                # Basic Relevance Filter (Part 10): Ensure keywords math
                relevant_chunks = []
                for chunk in top_chunks:
                    lower_chunk = chunk['chunk_text'].lower()
                    relevant = True
                    
                    if any(k in faiss_query.lower() for k in ["fail", "error", "timeout", "issue", "crash"]):
                        if not any(k in lower_chunk for k in ["fail", "error", "timeout", "issue", "crash", "fix", "resolution", "cause"]):
                            relevant = False
                    
                    if relevant:
                        relevant_chunks.append(chunk)
    
                top_chunks = relevant_chunks[:5]
            
            unique_articles = []
            seen_urls = set()
            combined_context_parts = []
            current_context_len = 0
            max_context_len = 900
            
            for chunk in top_chunks:
                context_entry = f"Source: {chunk['article_title']}\nURL: {chunk['article_url']}\nContent: {chunk['chunk_text']}"
                if current_context_len + len(context_entry) < max_context_len:
                    combined_context_parts.append(context_entry)
                    current_context_len += len(context_entry)
                
                if chunk['article_title'] not in seen_urls:
                    unique_articles.append({
                        "title": chunk['article_title'],
                        "url": chunk['article_url'],
                        "content": chunk['chunk_text'][:200] + "..."
                    })
                    seen_urls.add(chunk['article_title'])
            
            kb_context_text = "\n\n---\n\n".join(combined_context_parts)
            
            # Final Solution Generation
            if on_status: await on_status(json.dumps({"stage": "Generating solution", "progress": "Neural remediation synthesis"}))
            await asyncio.sleep(0)
            
            if resolution_status == "resolved":
                # Even when resolved, explain WHAT failed and HOW it recovered
                root_cause = f"Transient issue detected: {detected_issue}. The system auto-recovered."
                user_impact = "User experienced a temporary disconnection or delay, but service has resumed."
                troubleshooting_steps = (
                    "1. No immediate action required — issue is resolved.\n"
                    "2. Monitor logs for recurring transient errors.\n"
                    "3. If issue recurs frequently, investigate underlying cause."
                )
                summary = f"Issue occurred earlier ({detected_issue}) but has been resolved automatically."
                confidence_score = 0.95
            elif panorama_scenario:
                root_cause = panorama_scenario["root_cause"]
                user_impact = panorama_scenario["user_impact"]
                troubleshooting_steps = "\n".join([f"{i + 1}. {step}" for i, step in enumerate(panorama_scenario["steps"])])
                summary = f"{panorama_scenario['detected_issue']} {root_cause}"
                confidence_score = 0.88
            else:
                log_trace("[LLM INPUT]")
                log_trace(f"Query: {detected_issue}")
                log_trace(f"Stage Flow: {stage_analysis.get('stage_flow', 'N/A')}")
                
                # Build failure evidence string from stage analysis
                failure_evidence = "\n".join(stage_analysis.get("failure_lines", [])[:10])
                
                solution = await self.llm.generate_troubleshooting_steps(
                    detected_issue, 
                    kb_context_text, 
                    stage_flow=stage_analysis.get("stage_flow", ""),
                    failure_evidence=failure_evidence,
                    on_status=on_status
                )
                
                log_trace("[LLM OUTPUT]")
                log_trace(solution[:500] if solution else "No output")
    
                if not solution or "root cause" not in solution.lower():
                    solution = (
                        "**1. Root Cause:**\nTechnical restriction detected in logs.\n\n"
                        "**2. Troubleshooting Steps:**\n1. Verify agent status and logs.\n2. Restart the GP service.\n\n"
                        "**3. Summary:**\nGeneral troubleshooting required."
                    )
    
                import re
                rc_match = re.search(r'\*\*1\. Root Cause:\*\*(.+?)(?=\*\*2\. Troubleshooting Steps:\*\*|\Z)', solution, re.DOTALL)
                ts_match = re.search(r'\*\*2\. Troubleshooting Steps:\*\*(.+?)(?=\*\*3\. Summary:\*\*|\Z)', solution, re.DOTALL)
                
                root_cause = rc_match.group(1).strip() if rc_match else "Could not isolate root cause."
                troubleshooting_steps = ts_match.group(1).strip() if ts_match else "1. Review logs.\n2. Review network connectivity."
                
                confidence_score = 0.85
    
                if domain == "panorama_config":
                    user_impact = "Configuration changes cannot be committed."
                elif domain in ("prisma", "ipsec"):
                    user_impact = "Remote network connectivity impacted."
                elif domain == "endpoint":
                    user_impact = "Third party endpoint or application is restricted or impacted."
                else:
                    user_impact = "User may experience connection failures."
                
                if resolution_status == "active":
                    summary = "Issue is currently active and requires attention."
                elif resolution_status == "unknown":
                    summary = "Unable to determine issue status."
                else:
                    summary = "Issue occurred earlier but has been resolved automatically."
    
            log_trace("[FINAL RESULT]")
            log_trace(f"Status: {resolution_status}")
            log_trace(summary)
            print("[TRACE] LLM trace written to", LOG_PATH)

            if on_status: await on_status(json.dumps({"stage": "Completed", "progress": "Analysis complete"}))
            return {
                "status": resolution_status,
                "detected_issue": detected_issue,
                "correlated_issue": detected_issue if detected_issue else "None detected",
                "root_cause": root_cause,
                "user_impact": user_impact,
                "troubleshooting_steps": troubleshooting_steps,
                "summary": summary,
                "related_kbs": unique_articles[:3],
                "domain": domain,
                "previous_errors": previous_errors,
                "logs_used": logs_used,
                "confidence_score": confidence_score,
                "stage_flow": stage_analysis.get("stage_flow", ""),
                "failure_stage": stage_analysis.get("failure_stage", None),
                "failure_category": stage_analysis.get("failure_category", "unknown"),
                "stages_found": stage_analysis.get("stages_found", [])
            }
        
        except asyncio.CancelledError:
            import os
            for file in ["backend/logs/extracted_issues.txt", "backend/logs/final_issue.txt", "backend/logs/last_llm_prompt.txt"]:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except: pass
            if on_status: await on_status(json.dumps({"stage": "Cancelled by user", "progress": "Returning partial results"}))
            return {
                "status": "active",
                "detected_issue": detected_issue if 'detected_issue' in locals() else "Analysis aborted",
                "correlated_issue": "",
                "root_cause": "Partial analysis aborted early.",
                "user_impact": "Unknown, processing stopped.",
                "troubleshooting_steps": "Partial: Analysis was stopped by user.",
                "summary": "Analysis manually terminated.",
                "related_kbs": [],
                "domain": domain if 'domain' in locals() else "Unknown",
                "previous_errors": previous_errors,
                "logs_used": logs_used,
                "confidence_score": 0.0
            }
