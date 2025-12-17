"""Gemini LLM client using LangChain for minimal abstraction."""

from typing import AsyncIterator, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.llm.base import BaseLLMClient
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("llm.gemini")


class GeminiClient(BaseLLMClient):
    """
    Gemini Flash 2.5 client using LangChain.
    
    This is the ONLY place where LangChain is used - as a thin wrapper
    around the Gemini API. All other logic (memory, history, etc.) is
    implemented manually.
    """
    
    def __init__(self):
        """Initialize the Gemini client with configuration."""
        self.model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.gemini_temperature,
            max_tokens=settings.gemini_max_tokens,
            streaming=True
        )
        logger.info(f"Initialized Gemini client with model: {settings.gemini_model}")
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List:
        """
        Convert generic message format to LangChain message objects.
        
        Args:
            messages: List of dicts with 'role' and 'content' keys
            
        Returns:
            List of LangChain message objects
        """
        langchain_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # user or any other role defaults to HumanMessage
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from Gemini.
        
        Args:
            messages: Conversation history in generic format
            **kwargs: Additional parameters (unused for now)
            
        Yields:
            str: Token chunks from Gemini
        """
        try:
            # Convert to LangChain message format
            langchain_messages = self._convert_messages(messages)
            
            logger.info(f"Generating streaming response with {len(messages)} messages")
            
            # Stream response using LangChain's astream
            async for chunk in self.model.astream(langchain_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
            
            logger.info("Streaming response completed")
            
        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            raise
