from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable, Awaitable

class LLMBase(ABC):
    """
    Abstract base class for LLM services to ensure modularity.
    """
    
    @abstractmethod
    async def extract_issue(self, log_text: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        """
        Extract the main issue from the log file in one sentence.
        """
        pass

    @abstractmethod
    async def generate_troubleshooting_steps(self, issue: str, kb_context_text: str, on_status: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        """
        Generate troubleshooting steps based on the issue and retrieved KB context text.
        """
        pass

