from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from app.core.llm_base import LLMBase
from typing import Any
import torch


class LocalLLMService(LLMBase):
    def __init__(self, model_name: str = "google/flan-t5-large"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.tokenizer: Any = None
        self.model: Any = None
        self._load_model(self.model_name)

    def _load_model(self, model_name: str) -> None:
        print(f"Loading model: {model_name}...")
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            tie_word_embeddings=False,
        ).to(self.device)
        print(f"Model loaded on {self.device}")

    def _generate(self, prompt: str, max_new_tokens: int = 512, truncation: bool = True) -> str:
        # Tokenize with truncation to avoid the 512 token error
        inputs = self.tokenizer(
            prompt, 
            return_tensors="pt", 
            truncation=truncation, 
            max_length=512
        ).to(self.device)
        
        print(f"--- DEBUG: Generating with {self.model_name} (max tokens: {max_new_tokens}) ---")
        
        try:
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    num_beams=2,
                    early_stopping=True,
                    do_sample=False,
                )

            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
            print(f"--- DEBUG: Generated {len(result)} characters ---")
            return result
        except Exception as e:
            print(f"--- ERROR: Generation failed: {e} ---")
            return ""

    def extract_issue(self, filtered_log: str) -> str:
        """
        Extract the main issue from the log. 
        If the log is too long, it chunks the log and identifies issues in each chunk.
        """
        # Roughly estimate tokens (1 word ~ 1.3 tokens for T5)
        # T5 context is 512 tokens. Let's use 400 for log content to leave room for prompt.
        chunk_size_chars = 1200 # Reduced to ensure we stay well within 512 tokens
        
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
            llm_issue = self._generate(prompt, max_new_tokens=60)
        else:
            # If log is long, chunk it
            print(f"--- DEBUG: Log length {len(filtered_log)} exceeds single chunk. Processing in chunks... ---")
            chunks = [filtered_log[i:i + chunk_size_chars] for i in range(0, len(filtered_log), chunk_size_chars)]
            
            chunk_issues = []
            for i, chunk in enumerate(chunks[:8]): # Process up to 8 chunks for "full log" analysis
                prompt = (
                    f"{system_instruction}\n\n"
                    f"Log Snippet ({i+1}/{len(chunks)}):\n"
                    f"{chunk}\n\n"
                    "Issue detected in this snippet (one sentence):"
                )
                issue = self._generate(prompt, max_new_tokens=60)
                # Filter out generic or empty responses
                if issue and len(issue) > 5 and not issue.lower().startswith("no error") and "generic" not in issue.lower():
                    chunk_issues.append(issue)
            
            if not chunk_issues:
                llm_issue = "Specific GlobalProtect connection or authentication failure detected in logs."
            else:
                # Combine chunk issues and summarize
                combined_issues = "\n".join(list(set(chunk_issues))) # Deduplicate
                final_prompt = (
                    "Summarize these detected errors into one final precise technical sentence:\n"
                    f"{combined_issues}\n\n"
                    "Final Specific Root Issue:"
                )
                llm_issue = self._generate(final_prompt, max_new_tokens=60)

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

    def generate_troubleshooting_steps(self, issue: str, kb_context_text: str) -> str:
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

        output = self._generate(prompt, max_new_tokens=512)
        if (not output or len(output.strip()) < 20) and self.model_name == "google/flan-t5-large":
            print("[INFO] LLM output too short, falling back to google/flan-t5-base")
            self._load_model("google/flan-t5-base")
            output = self._generate(prompt, max_new_tokens=200)
        return output
