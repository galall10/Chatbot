"""Chat API endpoint with Server-Sent Events streaming."""

import uuid
from typing import AsyncIterator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.schemas.chat import ChatRequest
from src.llm.gemini_client import GeminiClient
from src.memory.redis_memory import memory
from src.core.logging import get_logger, set_request_id, clear_request_id

logger = get_logger("api.chat")

router = APIRouter()

# Initialize LLM client (singleton-like for this module)
llm_client = GeminiClient()


async def generate_sse_stream(
    session_id: str,
    message: str
) -> AsyncIterator[str]:
    """
    Generate Server-Sent Events stream for chat response.
    
    Args:
        session_id: Unique session identifier
        message: User message
        
    Yields:
        str: SSE-formatted data chunks
    """
    try:
        # 1. Load conversation history from Redis
        history = await memory.get_history(session_id)
        logger.info(f"Loaded {len(history)} messages from history for session {session_id}")
        
        # 2. Append user message to history
        await memory.add_message(session_id, "user", message)
        
        # 3. Prepare messages for LLM (history + new user message)
        messages = history + [{"role": "user", "content": message}]
        
        # 4. Stream response from LLM
        full_response_chunks = []
        
        async for chunk in llm_client.generate_stream(messages):
            # Collect chunks for saving later
            full_response_chunks.append(chunk)
            
            # Format as SSE and yield
            # SSE format: "data: <content>\n\n"
            sse_chunk = f"data: {chunk}\n\n"
            yield sse_chunk
        
        # 5. Save complete assistant response to memory
        full_response = "".join(full_response_chunks)
        await memory.add_message(session_id, "assistant", full_response)
        
        logger.info(f"Completed streaming response for session {session_id} ({len(full_response)} chars)")
        
        # Send final SSE message to indicate completion
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"Error in SSE stream generation: {str(e)}", exc_info=True)
        # Send error in SSE format
        error_msg = f"data: {{\"error\": \"An error occurred: {str(e)}\"}}\n\n"
        yield error_msg


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> StreamingResponse:
    """
    Stream chat responses using Server-Sent Events.
    
    This endpoint:
    1. Validates the incoming request
    2. Loads conversation history from Redis
    3. Sends the conversation to Gemini via LangChain
    4. Streams the response token-by-token via SSE
    5. Saves the conversation back to Redis
    
    Args:
        request: ChatRequest with session_id and message
        
    Returns:
        StreamingResponse: SSE stream of chat response
        
    Example:
        ```bash
        curl -N -X POST http://localhost:8000/chat \\
          -H "Content-Type: application/json" \\
          -d '{"session_id": "test-123", "message": "Hello!"}'
        ```
    """
    # Set request ID for logging context
    request_id = str(uuid.uuid4())
    set_request_id(request_id)
    
    try:
        logger.info(
            f"Chat request - session: {request.session_id}, "
            f"message_length: {len(request.message)}"
        )
        
        # Create streaming response
        return StreamingResponse(
            generate_sse_stream(request.session_id, request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat request: {str(e)}"
        )
    finally:
        clear_request_id()
