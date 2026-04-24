from typing import Literal


def is_globalprotect_log(log_text: str) -> bool:
    gp_keywords = [
        "pangps", "pangpa", "globalprotect", "gpagent", "portal", "gateway"
    ]
    log_lower = log_text.lower()
    return any(k in log_lower for k in gp_keywords)

def detect_domain(text: str) -> str:
    """
    Analyzes the text (logs, issue string) and returns the primary domain.
    Used to route FAISS query correctly.
    """
    lower_text = text.lower()
    
    # Prioritized extraction for strict gating
    if is_globalprotect_log(lower_text):
        return "globalprotect"
    
    return "endpoint"
