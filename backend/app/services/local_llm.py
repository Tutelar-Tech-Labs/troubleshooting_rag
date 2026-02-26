import requests
from typing import List, Dict, Any, Optional, Callable, Awaitable
from app.core.llm_base import LLMBase


class LocalLLMService(LLMBase):
    def __init__(self, model_name: str = "phi3"):
        self.base_url = "http://localhost:11434/api/generate"
        self.primary_model = "phi3"
        self.fallback_model = "mistral"
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
        if not self.available:
            return ""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 300,
                "num_ctx": 2048,
            },
        }
        try:
            msg = f"Using {model}..."
            print(f"[LLM] {msg}")
            if on_status: await on_status(msg)
            
            r = requests.post(self.base_url, json=payload, timeout=120)
            if r.status_code != 200:
                err_msg = f"LLM ERROR: HTTP {r.status_code}"
                print(f"[LLM ERROR] {r.text}")
                if on_status: await on_status(err_msg)
                return ""
            data = r.json()
            text = (data.get("response") or "").strip()
            return text
        except Exception as e:
            err_msg = f"LLM ERROR: {str(e)}"
            print(f"[LLM ERROR] {err_msg}")
            if on_status: await on_status(err_msg)
            return ""

    async def extract_issue(self, filtered_log: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        chunk_size_chars = 4000
        max_chunks = 10

        system_instruction = (
            "Identify the SPECIFIC technical issue. "
            "Avoid generic phrases like 'general connection failure'. "
            "Mention exact cause such as enforcement blocking, authentication failure, certificate issue, or portal connectivity."
        )

        llm_issue = ""
        if len(filtered_log) <= chunk_size_chars:
            prompt = (
                f"{system_instruction}\n\n"
                "Log Content:\n" + filtered_log + "\n\n"
                "Specific Issue (one sentence):"
            )
            primary = await self._generate(prompt, self.primary_model, max_tokens=120, on_status=on_status)
            if primary and len(primary.strip()) >= 20:
                llm_issue = primary
            else:
                msg = f"Fallback to {self.fallback_model}..."
                print(f"[LLM] {msg}")
                if on_status: await on_status(msg)
                fallback = await self._generate(prompt, self.fallback_model, max_tokens=120, on_status=on_status)
                llm_issue = fallback or ""
        else:
            if on_status: await on_status(f"Processing large log ({len(filtered_log)} chars) in chunks...")
            print(f"--- DEBUG: Log length {len(filtered_log)} exceeds single chunk. Processing in chunks... ---")
            chunks = [
                filtered_log[i : i + chunk_size_chars]
                for i in range(0, len(filtered_log), chunk_size_chars)
            ]

            chunk_issues = []
            for i, chunk in enumerate(chunks[:max_chunks]):
                if on_status: await on_status(f"Analyzing log chunk {i+1}/{min(len(chunks), max_chunks)}...")
                prompt = (
                    f"{system_instruction}\n\n"
                    f"Log Snippet ({i+1}/{len(chunks)}):\n"
                    f"{chunk}\n\n"
                    "Issue detected in this snippet (one sentence):"
                )
                primary = await self._generate(prompt, self.primary_model, max_tokens=120, on_status=on_status)
                issue = primary
                if not primary or len(primary.strip()) < 20:
                    msg = f"Fallback to {self.fallback_model}..."
                    print(f"[LLM] {msg}")
                    if on_status: await on_status(msg)
                    issue = await self._generate(
                        prompt, self.fallback_model, max_tokens=120, on_status=on_status
                    )
                if issue and len(issue) > 5 and not issue.lower().startswith("no error") and "generic" not in issue.lower():
                    chunk_issues.append(issue)
            
            if not chunk_issues:
                llm_issue = "Specific GlobalProtect connection or authentication failure detected in logs."
            else:
                combined_issues = "\n".join(list(set(chunk_issues)))
                final_prompt = (
                    "Summarize these detected errors into one final precise technical sentence:\n"
                    f"{combined_issues}\n\n"
                    "Final Specific Root Issue:"
                )
                if on_status: await on_status("Summarizing chunk findings...")
                primary = await self._generate(final_prompt, self.primary_model, max_tokens=120, on_status=on_status)
                if primary and len(primary.strip()) >= 20:
                    llm_issue = primary
                else:
                    msg = f"Fallback to {self.fallback_model}..."
                    print(f"[LLM] {msg}")
                    if on_status: await on_status(msg)
                    fallback = await self._generate(
                        final_prompt, self.fallback_model, max_tokens=120, on_status=on_status
                    )
                    llm_issue = fallback or ""

        # Rule-based override (Part 3 - Specificity)
        log_lower = filtered_log.lower()
        is_generic = any(word in llm_issue.lower() for word in ["general", "failure", "detected", "connection"])
        
        if is_generic:
            if "enforcer" in log_lower and "block" in log_lower:
                return "GlobalProtect endpoint enforcement is blocking network traffic"
            elif "authentication failed" in log_lower or "auth failed" in log_lower:
                return "GlobalProtect authentication failure"
            elif "portal unreachable" in log_lower or "cannot connect to portal" in log_lower:
                return "GlobalProtect portal connectivity failure"

        return llm_issue

    async def generate_troubleshooting_steps(self, issue: str, kb_context_text: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        kb_context_text = kb_context_text[:6000]
        prompt = (
            "You are a Palo Alto GlobalProtect support engineer.\n\n"
            "Issue:\n"
            f"{issue}\n\n"
            "Relevant Knowledge Base Information:\n"
            f"{kb_context_text}\n\n"
            "Provide a detailed response with these exact sections:\n\n"
            "**1. Root Cause:**\n"
            "(Provide a specific technical explanation based on the log and KB)\n\n"
            "**2. Troubleshooting Steps:**\n"
            "(Provide 3-5 clear, numbered, actionable steps)\n\n"
            "**3. Summary:**\n"
            "(One concise technical takeaway)\n\n"
            "If KB content is generic, infer practical troubleshooting from experience. Use bold headers as shown above."
        )

        primary = await self._generate(prompt, self.primary_model, max_tokens=600, on_status=on_status)
        if primary and len(primary.strip()) >= 20:
            return primary
        
        msg = f"Fallback to {self.fallback_model}..."
        print(f"[LLM] {msg}")
        if on_status: await on_status(msg)
        fallback = await self._generate(prompt, self.fallback_model, max_tokens=600, on_status=on_status)
        return fallback or ""

