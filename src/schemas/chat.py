"""Chat API request and response schemas."""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""
    
    session_id: str = Field(
        ...,
        description="Unique session identifier for conversation tracking",
        min_length=1,
        max_length=100,
        examples=["user-123-session-abc"]
    )
    
    message: str = Field(
        ...,
        description="User message to send to the chatbot",
        min_length=1,
        max_length=4000,
        examples=["Hello! Can you help me understand FastAPI?"]
    )
    
    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session ID format."""
        # Basic validation - alphanumeric, hyphens, underscores only
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError("session_id must contain only alphanumeric characters, hyphens, and underscores")
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "user-123-session-abc",
                    "message": "What is FastAPI and why should I use it?"
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """Response schema for non-streaming chat responses."""
    
    session_id: str = Field(..., description="Session identifier")
    response: str = Field(..., description="Chatbot response")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "user-123-session-abc",
                    "response": "FastAPI is a modern, fast web framework for building APIs with Python..."
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(default="healthy", description="Service health status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Current environment")
