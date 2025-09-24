from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from dotenv import load_dotenv
import os
from agents.query_classifier import QueryClassifierAgent
from tools.pinecone_tool import PineconeTool

# Load environment variables
load_dotenv() 

# Initialize FastAPI
app = FastAPI(
    title="E-commerce Chatbot API",
    description="LangGraph-powered chatbot for product search and recommendations",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:8080",  # Vite dev server
        "https://*.lovableproject.com",  # Lovable production
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class ChatMessage(BaseModel):
    message: str
    session_id: str
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    products: Optional[List[Dict[str, Any]]] = None
    ui_products: Optional[List[Dict[str, Any]]] = None
    needs_clarification: bool = False
    clarification_questions: Optional[List[str]] = None
    search_metadata: Optional[Dict[str, Any]] = None
    session_id: str

class ProductSearchRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 5

class ProductResponse(BaseModel):
    products: List[Dict[str, Any]]
    total_count: int

# Basic health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ecommerce-chatbot"}

# Main chat endpoint
# In app.py, find this function and replace:

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatMessage):
    try:
        from agents.chatbot_workflow import ChatbotWorkflow
        
        # Initialize workflow
        workflow = ChatbotWorkflow()
        
        # Run chat with session memory
        result = workflow.run_chat(
            message=request.message,
            session_id=request.session_id,
            user_context={"user_id": request.user_id} if request.user_id else {}
        )
        
        return ChatResponse(**result)
        
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

# Product search endpoint
@app.post("/search", response_model=ProductResponse)
async def search_products(request: ProductSearchRequest):
    """
    Direct product search endpoint using vector similarity
    """
    try:
        # TODO: Implement Pinecone + Neon search here
        
        return ProductResponse(
            products=[],
            total_count=0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product search failed: {str(e)}")

# Get product by ID
@app.get("/products/{product_id}")
async def get_product(product_id: str):
    """
    Get detailed product information by ASIN
    """
    try:
        # TODO: Implement database lookup
        
        return {"message": f"Product {product_id} details will be here"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Product lookup failed: {str(e)}")

# Session management endpoints
@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Get conversation history for a session
    """
    try:
        from tools.session_manager import SessionManager
        session_manager = SessionManager()
        session = session_manager.get_session(session_id)
        
        return {
            "session_id": session_id, 
            "messages": [msg.dict() for msg in session.messages],
            "context": session.context
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session retrieval failed: {str(e)}")

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear conversation history for a session
    """
    try:
        from tools.session_manager import SessionManager
        session_manager = SessionManager()
        session_manager.clear_session(session_id)
        
        return {"message": f"Session {session_id} cleared successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session clearing failed: {str(e)}")

# --- Debug endpoints ---
@app.post("/debug/classify")
async def debug_classify(body: Dict[str, Any]):
    try:
        qc = QueryClassifierAgent()
        res = qc.classify_query(body.get("message", ""), body.get("context", {}))
        return res.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classifier failed: {str(e)}")

@app.post("/debug/search")
async def debug_search(body: Dict[str, Any]):
    try:
        tool = PineconeTool()
        products = tool.search_similar_products(
            query=body.get("query", ""),
            filters=body.get("filters", {}),
            top_k=body.get("top_k", 5)
        )
        return {"products": products, "count": len(products)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/debug/pinecone-stats")
async def debug_pinecone_stats():
    try:
        # Lightweight stats via the client
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv("PINECONE_INDEX"))
        raw = index.describe_index_stats()
        # Force to plain dict (handle both dict-like and object-like)
        if hasattr(raw, 'to_dict'):
            stats = raw.to_dict()
        elif isinstance(raw, dict):
            stats = raw
        else:
            # Fallback conversion
            stats = {
                key: value for key, value in getattr(raw, '__dict__', {}).items()
                if isinstance(key, (str, int, float))
            }
        # Keep only JSON-serializable primitives
        def prune(obj):
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            if isinstance(obj, list):
                return [prune(x) for x in obj]
            if isinstance(obj, dict):
                return {str(k): prune(v) for k, v in obj.items()}
            return str(obj)
        return prune(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

@app.post("/debug/embed")
async def debug_embed(body: Dict[str, Any]):
    """Generate an embedding for a test text and return its length and model."""
    try:
        tool = PineconeTool()
        text = body.get("text", "test query")
        resp = tool.co.embed(texts=[text], model="embed-english-light-v3.0", input_type="search_query")
        vec = resp.embeddings[0]
        return {
            "model": "embed-english-light-v3.0",
            "dimension": len(vec),
            "sample": vec[:5]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embed failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )