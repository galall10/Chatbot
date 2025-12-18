# Production-Grade LLM Chatbot Service

A production-ready chatbot service built with **FastAPI**, **Google Gemini Flash 2.5**, **Redis**, and **Server-Sent Events (SSE)** streaming. This service demonstrates clean architecture with minimal framework dependencies and maximum extensibility.

## 🏗️ Architecture Overview

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /chat (SSE)
       │
┌──────▼──────────────────────────────────────┐
│           FastAPI Application                │
│  ┌────────────────────────────────────────┐ │
│  │       Chat API (api/chat.py)           │ │
│  └───────┬────────────────────┬───────────┘ │
│          │                    │              │
│  ┌───────▼────────┐  ┌────────▼──────────┐  │
│  │  LLM Client    │  │  Redis Memory     │  │
│  │  (Gemini)      │  │  (Conversation    │  │
│  │                │  │   History)        │  │
│  └────────┬───────┘  └────────┬──────────┘  │
└───────────┼──────────────────┼──────────────┘
            │                  │
    ┌───────▼────────┐  ┌──────▼────────┐
    │  Google Gemini │  │  Redis Server │
    │  Flash 2.5     │  │               │
    └────────────────┘  └───────────────┘
```

### Key Design Principles

#### 1. **Minimal LangChain Usage**
LangChain is used **ONLY** as a thin abstraction layer for the Gemini API (`langchain-google-genai`). We deliberately avoid:
- ❌ LangChain's memory classes
- ❌ LangChain's agents and tools
- ❌ LangChain's RAG abstractions
- ✅ Only using LangChain for LLM provider integration

This keeps the codebase simple, maintainable, and easy to understand.

#### 2. **Manual Memory Management**
Conversation history is managed **directly with Redis**:
- Custom token counting using `tiktoken`
- Intelligent message pruning (token-based and turn-based limits)
- Per-session conversation storage
- TTL-based cleanup

#### 3. **Provider Abstraction**
The `BaseLLMClient` abstract class allows easy swapping between LLM providers:
```python
# Current: Gemini
from src.llm.gemini_client import GeminiClient

# Future: Easily swap to OpenAI, Claude, etc.
# from src.llm.openai_client import OpenAIClient
```

#### 4. **Streaming First**
All responses stream via Server-Sent Events (SSE) for:
- Lower perceived latency
- Better user experience
- Token-by-token delivery

## 📁 Project Structure

```
chatbot/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry
│   ├── api/
│   │   ├── __init__.py
│   │   └── chat.py            # Chat endpoint with SSE streaming
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract LLM client interface
│   │   └── gemini_client.py   # Gemini implementation
│   ├── memory/
│   │   ├── __init__.py
│   │   └── redis_memory.py    # Manual Redis memory management
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── chat.py            # Pydantic models
│   └── core/
│       ├── __init__.py
│       ├── config.py          # Configuration management
│       └── logging.py         # Structured logging
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Redis (or Docker)
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### Local Development

1. **Clone and navigate to the project:**
```bash
cd chatbot
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

5. **Start Redis (if not using Docker):**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

6. **Run the application:**
```bash
uvicorn src.main:app --reload
```

7. **Access the API:**
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Docker Deployment

**Simplest method - single command:**
```bash
# Copy environment file
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Start everything
docker-compose up --build
```

The API will be available at http://localhost:8000

## 📡 API Usage

### Chat Endpoint (Streaming)

**Request:**
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-123",
    "message": "Explain FastAPI in simple terms"
  }'
```

**Response (SSE Stream):**
```
data: Fast
data: API
data:  is
data:  a
data:  modern
...
data: [DONE]
```

### Using Python

```python
import httpx

def stream_chat(session_id: str, message: str):
    with httpx.stream(
        "POST",
        "http://localhost:8000/chat",
        json={"session_id": session_id, "message": message},
        timeout=60.0
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                chunk = line[6:]  # Remove "data: " prefix
                if chunk == "[DONE]":
                    break
                print(chunk, end="", flush=True)

stream_chat("test-session", "Hello! What is FastAPI?")
```

### Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

## ⚙️ Configuration

All configuration is managed via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | **Required** |
| `GEMINI_MODEL` | Model name | `gemini-2.5-flash` |
| `GEMINI_TEMPERATURE` | Sampling temperature | `0.7` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `MAX_HISTORY_TOKENS` | Max tokens in conversation history | `4000` |
| `MAX_HISTORY_TURNS` | Max turns in conversation history | `20` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Environment name | `development` |

## 💾 Memory Strategy

### Conversation Storage
- Each session has a unique conversation history stored in Redis
- Key format: `chat:session:{session_id}:history`
- Messages stored as JSON with `role` and `content`

### Memory Limits
Two-tier limiting strategy:
1. **Token-based**: Keeps history under `MAX_HISTORY_TOKENS` (~4000)
2. **Turn-based**: Keeps history under `MAX_HISTORY_TURNS` (20 turns = 40 messages)

### Pruning Strategy
When limits are exceeded:
- System messages are always preserved
- Oldest conversation messages are removed first
- Token counting uses `tiktoken` (accurate approximation for Gemini)

### TTL
- Conversations expire after `REDIS_TTL_SECONDS` (default: 24 hours)
- Prevents unbounded Redis growth

## 🔮 Future Extensions

This architecture is designed for easy extension:

### 1. **Add RAG (Retrieval-Augmented Generation)**
```python
# src/rag/vector_store.py
class VectorStore:
    async def search(self, query: str) -> list[str]:
        # Search vector DB (Pinecone, Weaviate, etc.)
        pass

# Use in chat.py:
retrieval_context = await vector_store.search(message)
messages = [{"role": "system", "content": retrieval_context}] + history
```

### 2. **Add LangChain Tools/Agents**
```python
# src/agents/tool_executor.py
from langchain.agents import AgentExecutor

# Only use LangChain's agent capabilities when needed
agent = AgentExecutor(tools=[...], llm=llm_client)
```

### 3. **Multi-Provider Support**
```python
# src/llm/openai_client.py
class OpenAIClient(BaseLLMClient):
    async def generate_stream(self, messages, **kwargs):
        # OpenAI implementation
        pass

# Switch providers via config
llm_client = get_llm_client(settings.llm_provider)
```

### 4. **WebSocket Alternative**
```python
# src/api/chat_ws.py
@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    # Bi-directional streaming
    pass
```

### 5. **Observability**
- Add Prometheus metrics
- Integrate with OpenTelemetry
- Add request tracing

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📝 Logging

Structured logging with request ID tracking:
```
2024-01-15 10:30:45 - INFO - [abc-123-def] - chatbot.api.chat - Chat request - session: user-123
2024-01-15 10:30:46 - INFO - [abc-123-def] - chatbot.llm.gemini - Generating streaming response
```

Production mode outputs JSON for log aggregation:
```json
{"timestamp": "2024-01-15 10:30:45", "level": "INFO", "request_id": "abc-123", "name": "chatbot.api.chat", "message": "Chat request"}
```

## 🛡️ Security Notes

- Non-root Docker user
- Health checks configured
- CORS configurable per environment
- API key loaded from environment (never committed)
- Redis with persistence enabled

## 🤝 Contributing

This is a production template. Customize as needed:
1. Add authentication/authorization
2. Add rate limiting
3. Add input sanitization
4. Add monitoring and alerting
5. Add CI/CD pipelines

## 📄 License

MIT License - feel free to use in your projects!

---

**Built with ❤️ using minimal dependencies and maximum clarity**
