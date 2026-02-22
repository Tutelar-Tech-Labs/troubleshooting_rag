from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMBase(ABC):
    """
    Abstract base class for LLM services to ensure modularity.
    """
    
    @abstractmethod
    def extract_issue(self, log_text: str) -> str:
        """
        Extract the main issue from the log file in one sentence.
        """
        pass

    @abstractmethod
    def generate_troubleshooting_steps(self, issue: str, kb_context_text: str) -> str:
        """
        Generate troubleshooting steps based on the issue and retrieved KB context text.
        """
        pass
