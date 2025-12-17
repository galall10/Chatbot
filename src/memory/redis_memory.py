"""Redis-based conversation memory with manual token management."""

import json
import asyncio
from typing import List, Dict, Optional
import redis.asyncio as redis
import tiktoken

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("memory.redis")


class RedisConversationMemory:
    """
    Manual conversation memory using Redis.
    
    This implementation does NOT use LangChain's memory abstractions.
    Instead, it directly manages conversation history with token-based
    pruning to prevent context overflow.
    """
    
    def __init__(self):
        """Initialize Redis connection and token encoder."""
        self.redis_client: Optional[redis.Redis] = None
        
        # Use tiktoken for approximate token counting
        # Gemini uses similar tokenization to GPT models
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to approximate counting if tiktoken fails
            self.encoder = None
            logger.warning("Failed to load tiktoken encoder, using approximate token counting")
    
    async def connect(self):
        """Establish Redis connection."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {settings.redis_url}")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken or approximation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            int: Approximate token count
        """
        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            # Rough approximation: 1 token ≈ 4 characters
            return len(text) // 4
    
    def _get_messages_token_count(self, messages: List[Dict[str, str]]) -> int:
        """
        Calculate total token count for a list of messages.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            int: Total token count
        """
        total_tokens = 0
        for msg in messages:
            # Count tokens for role and content
            total_tokens += self._count_tokens(msg.get("role", ""))
            total_tokens += self._count_tokens(msg.get("content", ""))
            # Add overhead for message structure (~4 tokens per message)
            total_tokens += 4
        
        return total_tokens
    
    def _prune_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        max_turns: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Prune messages to fit within token and turn limits.
        
        Strategy: Keep the most recent messages, preserving system messages.
        
        Args:
            messages: List of messages
            max_tokens: Maximum total tokens (None = no limit)
            max_turns: Maximum number of turns (None = no limit)
            
        Returns:
            List[Dict[str, str]]: Pruned messages
        """
        if not messages:
            return messages
        
        # Separate system messages from conversation
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        conversation_messages = [msg for msg in messages if msg.get("role") != "system"]
        
        # Apply turn limit if specified
        if max_turns and len(conversation_messages) > max_turns * 2:
            # Each turn = 1 user + 1 assistant message
            conversation_messages = conversation_messages[-(max_turns * 2):]
        
        # Apply token limit if specified
        if max_tokens:
            current_tokens = self._get_messages_token_count(system_messages + conversation_messages)
            
            while current_tokens > max_tokens and conversation_messages:
                # Remove oldest conversation message
                removed = conversation_messages.pop(0)
                current_tokens -= self._count_tokens(removed.get("content", ""))
                current_tokens -= self._count_tokens(removed.get("role", ""))
                current_tokens -= 4  # Message overhead
        
        # Reconstruct with system messages first
        return system_messages + conversation_messages
    
    def _get_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"chat:session:{session_id}:history"
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to conversation history.
        
        Args:
            session_id: Unique session identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
        """
        if not self.redis_client:
            await self.connect()
        
        message = {
            "role": role,
            "content": content
        }
        
        key = self._get_key(session_id)
        
        # Append message to list
        await self.redis_client.rpush(key, json.dumps(message))
        
        # Set TTL on the key
        await self.redis_client.expire(key, settings.redis_ttl_seconds)
        
        logger.debug(f"Added {role} message to session {session_id}")
    
    async def get_history(
        self,
        session_id: str,
        max_tokens: Optional[int] = None,
        max_turns: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Unique session identifier
            max_tokens: Maximum tokens to return (uses config default if None)
            max_turns: Maximum turns to return (uses config default if None)
            
        Returns:
            List[Dict[str, str]]: Conversation history
        """
        if not self.redis_client:
            await self.connect()
        
        key = self._get_key(session_id)
        
        # Get all messages from Redis
        raw_messages = await self.redis_client.lrange(key, 0, -1)
        
        if not raw_messages:
            return []
        
        # Parse JSON messages
        messages = [json.loads(msg) for msg in raw_messages]
        
        # Apply pruning
        max_tokens = max_tokens or settings.max_history_tokens
        max_turns = max_turns or settings.max_history_turns
        
        pruned_messages = self._prune_messages(messages, max_tokens, max_turns)
        
        logger.debug(
            f"Retrieved {len(pruned_messages)} messages for session {session_id} "
            f"(original: {len(messages)}, tokens: {self._get_messages_token_count(pruned_messages)})"
        )
        
        return pruned_messages
    
    async def clear_history(self, session_id: str) -> None:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Unique session identifier
        """
        if not self.redis_client:
            await self.connect()
        
        key = self._get_key(session_id)
        await self.redis_client.delete(key)
        
        logger.info(f"Cleared history for session {session_id}")


# Global memory instance
memory = RedisConversationMemory()
