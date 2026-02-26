from app.services.local_llm import LocalLLMService
from app.services.faiss_service import FAISSService
from app.services.scenario_detector import detect_scenario
from app.services.domain_detector import detect_domain
from app.services.panorama_scenarios import detect_panorama_scenario
from app.utils.log_processor import extract_key_lines
from typing import Dict, Any, List, Optional, Callable, Awaitable


class RAGService:
    def __init__(self):
        self.llm = LocalLLMService()
        self.faiss = FAISSService()

    async def analyze_log(self, log_text: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        """
        Full RAG flow: preprocess -> extract issue -> scenario/domain check -> FAISS search -> solution generation.
        """
        # 1. Preprocess log: Extract key lines
        if on_status: await on_status("Log preprocessing and noise reduction...")
        filtered_log = extract_key_lines(log_text)

        # 2. Extract issue (LLM): strictly one sentence
        if on_status: await on_status("Neural issue extraction...")
        detected_issue = await self.llm.extract_issue(filtered_log, on_status=on_status)

        # 3. Domain detection based on full raw log text
        domain = detect_domain(log_text)

        return await self.analyze_issue(detected_issue, filtered_log, domain=domain, on_status=on_status)

    async def analyze_issue(self, detected_issue: str, filtered_log: str = "", domain: Optional[str] = None, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        """
        RAG flow starting from a detected or provided issue.
        """
        # Context used for domain and scenario detection
        scenario_context = filtered_log if filtered_log else detected_issue

        # 1. Domain Detection Layer
        if domain is None:
            if on_status: await on_status("Detecting operation domain...")
            domain = detect_domain(scenario_context)

        # 2. Scenario Intelligence
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

        query_suffix = " PAN-OS GlobalProtect Panorama Prisma troubleshooting"
        if domain == "panorama_config":
            faiss_query = base_query + " panorama commit configuration dependency" + query_suffix
        elif domain == "prisma":
            faiss_query = base_query + " prisma remote network cloud services" + query_suffix
        elif domain == "ipsec":
            faiss_query = base_query + " ipsec ike vpn tunnel configuration" + query_suffix
        else:
            faiss_query = base_query + query_suffix

        # DEBUG: Extracted issue, domain & Scenario
        print(f"--- DEBUG: ISSUE EXTRACTION ---")
        print(f"Extracted issue: {detected_issue}")
        print(f"Detected domain: {domain}")
        if panorama_scenario:
            print(f"Detected Panorama Scenario: {panorama_scenario['scenario']}")
        if scenario:
            print(f"Detected Scenario: {scenario['scenario']}")
        print("=" * 50)

        # 3. Domain-aware FAISS Search
        if on_status: await on_status("KB vector retrieval and ranking...")
        print(f"--- DEBUG: FAISS SEARCH ---")
        print(f"FAISS Query Text: {faiss_query}")
        top_chunks = self.faiss.search(faiss_query, domain=domain, top_k=5)
        print(f"Number of chunks retrieved: {len(top_chunks)}")
        print(f"[DEBUG] Retrieved chunks: {len(top_chunks)}")
        if len(top_chunks) == 0:
            print("WARNING: FAISS returned no results")
        
        # 4. KB Context Handling: combine chunks and deduplicate articles
        unique_articles = []
        seen_urls = set()
        combined_context_parts = []
        current_context_len = 0
        max_context_len = 800
        
        for chunk in top_chunks:
            # DEBUG: Retrieved KB preview (Part 8)
            print(f"\nRetrieved KB: {chunk['article_title']}")
            print(f"Content preview: {chunk['chunk_text'][:200]}...")
            
            # Context format (Part 5)
            context_entry = f"Source: {chunk['article_title']}\nURL: {chunk['article_url']}\nContent: {chunk['chunk_text']}"
            
            if current_context_len + len(context_entry) < max_context_len:
                combined_context_parts.append(context_entry)
                current_context_len += len(context_entry)
            
            # Identify unique articles for the frontend
            if chunk['article_url'] not in seen_urls:
                unique_articles.append({
                    "title": chunk['article_title'],
                    "url": chunk['article_url'],
                    "content": chunk['chunk_text'][:200] + "..."
                })
                seen_urls.add(chunk['article_url'])
        
        kb_context_text = "\n\n---\n\n".join(combined_context_parts)
        print(f"[DEBUG] Context length: {len(kb_context_text)}")
        print(f"\nFinal context length: {len(kb_context_text)} characters")
        print("="*50 + "\n")
        
        # 4. Final Solution Generation: Panorama override or LLM flow
        if on_status: await on_status("Neural remediation synthesis...")
        if panorama_scenario:
            root_cause = panorama_scenario["root_cause"]
            user_impact = panorama_scenario["user_impact"]
            troubleshooting_steps = "\n".join([f"{i + 1}. {step}" for i, step in enumerate(panorama_scenario["steps"])])
            summary = f"{panorama_scenario['detected_issue']} {root_cause}"
            detected_issue = panorama_scenario["detected_issue"]
        else:
            # Continue normal LLM RAG flow
            solution = await self.llm.generate_troubleshooting_steps(detected_issue, kb_context_text, on_status=on_status)

            if not solution or "Root Cause" not in solution:
                solution = (
                    "**1. Root Cause:**\n"
                    "Technical connection or policy restriction detected in logs.\n\n"
                    "**2. Troubleshooting Steps:**\n"
                    "1. Verify GlobalProtect agent status and logs.\n"
                    "2. Check firewall policy and security rules.\n"
                    "3. Ensure correct portal and gateway addresses.\n"
                    "4. Verify user credentials.\n"
                    "5. Restart GlobalProtect service.\n\n"
                    "**3. Summary:**\n"
                    "General troubleshooting required based on log patterns."
                )

            import re

            root_cause_match = re.search(
                r"\*\*1\. Root Cause:\*\*\s*(.*?)(?=\*\*2\.|$)", solution, re.DOTALL | re.IGNORECASE
            )
            steps_match = re.search(
                r"\*\*2\. Troubleshooting Steps:\*\*\s*(.*?)(?=\*\*3\.|$)", solution, re.DOTALL | re.IGNORECASE
            )
            summary_match = re.search(r"\*\*3\. Summary:\*\*\s*(.*)", solution, re.DOTALL | re.IGNORECASE)

            root_cause = root_cause_match.group(1).strip() if root_cause_match else "Technical issue detected in logs."
            troubleshooting_steps = (
                steps_match.group(1).strip() if steps_match else "Follow standard PAN-OS troubleshooting procedures."
            )
            summary = (
                summary_match.group(1).strip()
                if summary_match
                else f"{detected_issue} Root cause requires manual verification."
            )

            if domain == "panorama_config":
                user_impact = "Configuration changes cannot be committed successfully."
            elif domain in ("prisma", "ipsec"):
                user_impact = "Remote network or tunnel connectivity may be impacted."
            else:
                user_impact = "User may experience connection or resource access failures."

        # DEBUG: Final result components
        print(f"--- DEBUG: FINAL ANALYSIS ---")
        print(f"Issue: {detected_issue}")
        print(f"Root Cause: {root_cause}")
        print(f"Domain: {domain}")
        print("=" * 50 + "\n")

        return {
            "detected_issue": detected_issue,
            "root_cause": root_cause,
            "user_impact": user_impact,
            "troubleshooting_steps": troubleshooting_steps,
            "summary": summary,
            "related_kbs": unique_articles[:3],
            "domain": domain,
        }
