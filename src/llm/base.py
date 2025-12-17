"""Base LLM client abstraction for provider-agnostic interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM providers.
    
    This abstraction allows easy swapping between different LLM providers
    (Gemini, OpenAI, Claude, etc.) without changing the rest of the application.
    """
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Format: [{"role": "user", "content": "Hello"}, ...]
            **kwargs: Additional provider-specific parameters
            
        Yields:
            str: Token/chunk from the LLM response
            
        Raises:
            Exception: If the LLM request fails
        """
        pass
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """
        Generate complete (non-streaming) response from the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional provider-specific parameters
            
        Returns:
            str: Complete LLM response
            
        Raises:
            Exception: If the LLM request fails
        """
        # Default implementation: collect all streamed tokens
        chunks = []
        async for chunk in self.generate_stream(messages, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)
