# E-commerce Chatbot Backend

A sophisticated LangGraph-powered backend for semantic product search and recommendations.

## Features

- **LangGraph Workflow**: Multi-agent conversation flow
- **Semantic Search**: Pinecone vector database with Cohere embeddings
- **Query Classification**: Gemini-powered query understanding
- **Session Memory**: Redis-backed conversation memory
- **Product Reranking**: LLM-enhanced result optimization
- **ASIN Fallback**: JSON data enrichment when vector data is incomplete
- **PostgreSQL Integration**: Neon database for product details

## Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
GEMINI_API_KEY=your_gemini_key
PINECONE_API_KEY=your_pinecone_key
COHERE_API_KEY=your_cohere_key
NEON_HOST=your_neon_host
NEON_DB=your_neon_db
NEON_USER=your_neon_user
NEON_PASSWORD=your_neon_password
PINECONE_INDEX=your_pinecone_index
REDIS_URL=your_redis_url (optional)
```

3. Run the server:
```bash
python app.py
```

## API Endpoints

- `POST /chat` - Main chat endpoint
- `GET /session/{session_id}/history` - Get conversation history
- `DELETE /session/{session_id}` - Clear session
- `GET /health` - Health check

## Architecture

1. **Query Classification** - Understands user intent (vague/specific/clarification)
2. **Semantic Search** - Pinecone vector search with Cohere embeddings
3. **Data Enrichment** - Combines vector, DB, and JSON fallback data
4. **LLM Reranking** - Gemini-powered result optimization
5. **Response Generation** - Context-aware response with products
6. **Session Memory** - Persistent conversation context