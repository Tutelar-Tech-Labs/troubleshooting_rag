import requests
import json
from typing import List, Dict, Any, Optional, Callable, Awaitable
from app.core.llm_base import LLMBase


class LocalLLMService(LLMBase):
    def __init__(self, model_name: str = "phi3"):
        self.base_url = "http://localhost:11434/api/generate"
        self.primary_model = "mistral"
        self.fallback_model = "phi3"
        self.available = self._check_ollama()

    def _check_ollama(self) -> bool:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=120)
            if r.status_code == 200:
                print("[LLM] Ollama is available")
                return True
        except Exception:
            print("[LLM WARNING] Ollama not reachable")
        return False

    async def _generate(self, prompt: str, model: str, max_tokens: int = 512, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 200,
                "num_ctx": 2048,
            },
        }
        
        import os
        os.makedirs("backend/logs", exist_ok=True)
        # 4) Save Debug Files (Last prompt)
        try:
            with open("backend/logs/last_llm_prompt.txt", "w", encoding="utf-8") as f:
                f.write(prompt)
        except Exception as e:
            print(f"[LLM WARNING] Could not write prompt log: {e}")
            
        try:
            # 11) Performance Logging
            print(f"[LLM] Model: {model} | Prompt size: {len(prompt)}")
            if on_status: await on_status(f"[LLM] Model: {model} | Prompt size: {len(prompt)}")
            
            import asyncio
            r = await asyncio.to_thread(requests.post, self.base_url, json=payload, timeout=180)
            
            if r.status_code != 200:
                err_msg = f"LLM ERROR: HTTP {r.status_code}"
                print(f"[LLM ERROR] {err_msg}")
                if on_status: await on_status(err_msg)
                return ""
                
            data = r.json()
            text = (data.get("response") or "").strip()
            
            # 11) Performance Logging
            print(f"[LLM] Response length: {len(text)}")
            if on_status: await on_status(f"[LLM] Response length: {len(text)}")
            
            return text
        except requests.exceptions.Timeout:
            err_msg = f"LLM ERROR: Timeout"
            print(f"[LLM ERROR] {err_msg}")
            if on_status: await on_status(err_msg)
            return ""
        except Exception as e:
            err_msg = f"LLM ERROR: {str(e)}"
            print(f"[LLM ERROR] {err_msg}")
            if on_status: await on_status(err_msg)
            return ""

    async def extract_issue(self, filtered_log: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        # 2) Accuracy Mode – Process ALL chunks
        chunk_size_chars = 2500

        system_instruction = (
            "You are analyzing GlobalProtect VPN logs. "
            "Identify the SPECIFIC failure point using GP connection stages: "
            "Portal Processing, Portal Login, Network Discover, Gateway Login, Tunnel Creation. "
            "State which stage failed and the exact error from logs. "
            "Do NOT guess — only report what the logs explicitly show. "
            "If no clear GP stages are found, identify the most severe error or warning present."
        )

        import math
        total_chunks = math.ceil(len(filtered_log) / chunk_size_chars)
        
        chunks = [
            filtered_log[i : i + chunk_size_chars]
            for i in range(0, len(filtered_log), chunk_size_chars)
        ]
        
        if on_status: await on_status(json.dumps({"stage": "Splitting log into chunks", "progress": f"Total chunks: {total_chunks}", "total_chunks": total_chunks, "current_chunk": 0}))
        
        print(f"--- DEBUG: Log length {len(filtered_log)}. Processing all {total_chunks} chunks ---")

        chunk_issues = []
        
        import os
        os.makedirs("backend/logs", exist_ok=True)
        # Clear previous extracted issues log
        try:
            with open("backend/logs/extracted_issues.txt", "w", encoding="utf-8") as f:
                f.write(f"=== Extracted Issues (Log Size: {len(filtered_log)} chars, Total Chunks: {total_chunks}) ===\n\n")
        except: pass

        for i, chunk in enumerate(chunks):
            if on_status: await on_status(json.dumps({"stage": f"Processing chunk {i+1}/{total_chunks}", "progress": f"Analyzing chunk {i+1}", "current_chunk": i+1}))
            
            # Check for Stop Analysis (Cancellation)
            import asyncio
            await asyncio.sleep(0)
            
            prompt = (
                f"{system_instruction}\n\n"
                f"Log Snippet ({i+1}/{total_chunks}):\n"
                f"{chunk}\n\n"
                "Issue detected in this snippet (one sentence):"
            )
            
            primary = await self._generate(prompt, self.primary_model, max_tokens=120, on_status=on_status)
            issue = primary
            # Fallback only if failure (empty response)
            if not primary or len(primary.strip()) == 0:
                msg = f"Fallback to {self.fallback_model}..."
                print(f"[LLM] {msg}")
                if on_status: await on_status(msg)
                issue = await self._generate(
                    prompt, self.fallback_model, max_tokens=120, on_status=on_status
                )
                
            if issue and len(issue.strip()) > 0:
                clean_issue = issue.strip()
                chunk_issues.append(clean_issue)
                try:
                    with open("backend/logs/extracted_issues.txt", "a", encoding="utf-8") as f:
                        f.write(f"Chunk {i+1}:\n{clean_issue}\n\n")
                except: pass
        
        # 9) Issue Prioritization Logic
        if not chunk_issues:
            llm_issue = "LLM temporarily unavailable. Please retry analysis."
        else:
            if on_status: await on_status(json.dumps({"stage": "Aggregating issues", "progress": "Prioritizing discovered issues"}))
            
            from collections import Counter
            issue_counts = Counter(chunk_issues)
            
            best_issue = ""
            best_score = -1
            
            severity_keywords = ["authentication", "certificate", "enforcement", "portal", "gateway"]
            
            for issue_text, count in issue_counts.items():
                issue_lower = issue_text.lower()
                
                # Ignore generic issues
                if any(word in issue_lower for word in ["no error", "generic"]):
                    continue
                    
                score = count
                for kw in severity_keywords:
                    if kw in issue_lower:
                        score += 5 # Boost severity
                        
                if score > best_score:
                    best_score = score
                    best_issue = issue_text
                    
            if best_issue:
                llm_issue = best_issue
            else:
                llm_issue = chunk_issues[0]
                
        # Save final issue finding
        try:
            with open("backend/logs/final_issue.txt", "w", encoding="utf-8") as f:
                f.write(llm_issue)
        except: pass

        return llm_issue

    async def generate_troubleshooting_steps(self, issue: str, kb_context_text: str, stage_flow: str = "", failure_evidence: str = "", on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        # 5) Limit KB Context
        kb_context_text = kb_context_text[:4000]
        
        # Build stage context for the prompt
        stage_section = ""
        if stage_flow:
            stage_section = (
                f"\n\nGlobalProtect Connection Stage Flow (from logs):\n{stage_flow}\n"
            )
        
        evidence_section = ""
        if failure_evidence:
            evidence_section = (
                f"\nLog Evidence (actual error lines from logs):\n{failure_evidence}\n"
            )
        
        prompt = (
            "You are a senior Palo Alto GlobalProtect log analyst.\n\n"
            "STRICT RULES:\n"
            "- ONLY use information present in the logs and evidence below\n"
            "- Every root cause MUST be backed by a specific log line or stage result\n"
            "- Do NOT mention certificate issues, DNS issues, or SAML issues unless explicitly shown in the evidence\n"
            "- Do NOT hallucinate or guess — if logs don't show it, don't say it\n"
            "- Explain step-by-step based on the stage flow sequence\n\n"
            f"Issue:\n{issue}\n"
            f"{stage_section}"
            f"{evidence_section}\n"
            f"Relevant Knowledge Base:\n{kb_context_text}\n\n"
            "Provide your analysis with these exact sections:\n\n"
            "**1. Stage Sequence Analysis:**\n"
            "(Walk through the GP connection stages detected. For each stage, state success or failure. "
            "Identify the exact stage where failure occurred.)\n\n"
            "**2. Root Cause:**\n"
            "(Based ONLY on the log evidence and failure stage, explain the technical root cause. "
            "Cite specific log lines as evidence.)\n\n"
            "**3. Troubleshooting Steps:**\n"
            "(3-5 actionable steps specific to the failure stage and root cause)\n\n"
            "**4. Summary:**\n"
            "(One concise sentence: what failed, at which stage, and why)\n\n"
            "Use bold headers as shown above."
        )

        primary = await self._generate(prompt, self.primary_model, max_tokens=700, on_status=on_status)
        if primary and len(primary.strip()) > 0:
            return primary
        
        msg = f"Retrying with {self.fallback_model}"
        print(f"[LLM ERROR] Timeout\n{msg}")
        if on_status: await on_status(msg)
        fallback = await self._generate(prompt, self.fallback_model, max_tokens=700, on_status=on_status)
        if fallback and len(fallback.strip()) > 0:
            return fallback

        return "LLM temporarily unavailable. Please retry analysis."

