from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv() 

# Initialize FastAPI
app = FastAPI(
    title="E-commerce Chatbot API",
    description="Intelligent shopping assistant powered by Gemini",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
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

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "simple-chatbot", "version": "2.0"}

# Main chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatMessage):
    try:
        from agents.simple_chatbot import SimpleChatbot
        
        # Initialize chatbot
        chatbot = SimpleChatbot()
        
        # Run chat
        result = chatbot.run_chat(
            message=request.message,
            session_id=request.session_id,
            user_context={"user_id": request.user_id} if request.user_id else {}
        )
        
        return ChatResponse(**result)
        
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        
        return ChatResponse(
            response="I'm having trouble right now. Could you try asking in a different way? For example: 'show me men's shoes' or 'I need Nike sneakers'.",
            products=[],
            ui_products=[],
            needs_clarification=False,
            clarification_questions=[],
            search_metadata={"error": str(e)},
            session_id=request.session_id
        )

# Session management
@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    try:
        from tools.session_manager import SessionManager
        from config import Config
        
        session_manager = SessionManager(Config.REDIS_URL)
        session = session_manager.get_session(session_id)
        
        return {
            "session_id": session_id,
            "messages": [msg.dict() if hasattr(msg, 'dict') else msg for msg in session.messages],
            "context": session.context
        }
    except Exception as e:
        print(f"Session error: {e}")
        return {"session_id": session_id, "messages": [], "context": {}}

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    try:
        from tools.session_manager import SessionManager
        from config import Config
        
        session_manager = SessionManager(Config.REDIS_URL)
        session_manager.clear_session(session_id)
        return {"message": f"Session {session_id} cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Direct product search (optional)
@app.post("/search")
async def search_products(body: Dict[str, Any]):
    try:
        from tools.pinecone_tool import PineconeTool

        tool = PineconeTool()
        products = tool.search_similar_products(
            query=body.get("query", ""),
            filters=body.get("filters", {}),
            top_k=body.get("limit", 5)
        )

        return {"products": products, "total_count": len(products)}
    except Exception as e:
        return {"products": [], "total_count": 0}

# DEBUG ENDPOINTS FOR CONSISTENCY MONITORING

@app.post("/debug/parse-query")
async def debug_parse_query(body: Dict[str, Any]):
    """
    Parse a query and return extracted parameters.
    Useful for testing parameter extraction consistency.
    """
    try:
        from utils.query_parser import parse_query

        query = body.get("query", "")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        parsed = parse_query(query)
        return {
            "query": query,
            "parsed_parameters": parsed,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/consistency-report")
async def debug_consistency_report(query: Optional[str] = None):
    """
    Get consistency report for all queries or a specific query.
    Shows statistics about parameter extraction consistency.
    """
    try:
        from utils.consistency_logger import get_consistency_report

        report = get_consistency_report(query)
        return {
            "report": report,
            "query_filter": query,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/query-history/{query}")
async def debug_query_history(query: str, limit: int = 10):
    """
    Get extraction history for a specific query.
    Shows how parameters were extracted across multiple calls.
    """
    try:
        from utils.consistency_logger import get_query_history

        history = get_query_history(query, limit)
        return {
            "query": query,
            "history": history,
            "count": len(history),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/debug/test-consistency")
async def debug_test_consistency(body: Dict[str, Any]):
    """
    Test query consistency by running the same query multiple times.
    Returns statistics about result consistency.
    """
    try:
        from agents.simple_chatbot import SimpleChatbot
        import uuid

        query = body.get("query", "")
        runs = body.get("runs", 5)

        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        if runs < 2 or runs > 20:
            raise HTTPException(status_code=400, detail="Runs must be between 2 and 20")

        chatbot = SimpleChatbot()
        results = []

        for i in range(runs):
            session_id = f"test_{uuid.uuid4()}"
            result = chatbot.run_chat(query, session_id)
            results.append({
                "run": i + 1,
                "products_shown": len(result.get("ui_products", [])),
                "total_found": result.get("search_metadata", {}).get("total_found", 0),
                "parsed_params": result.get("search_metadata", {}).get("parsed_params", {}),
                "llm_params": result.get("search_metadata", {}).get("llm_params", {}),
            })

        # Calculate consistency statistics
        product_counts = [r["products_shown"] for r in results]
        all_same = len(set(product_counts)) == 1
        min_count = min(product_counts)
        max_count = max(product_counts)
        avg_count = sum(product_counts) / len(product_counts)

        # Check parameter consistency
        parsed_consistent = all(
            r["parsed_params"].get("min_price") == results[0]["parsed_params"].get("min_price") and
            r["parsed_params"].get("max_price") == results[0]["parsed_params"].get("max_price")
            for r in results
        )

        return {
            "query": query,
            "runs": runs,
            "results": results,
            "consistency": {
                "all_same_count": all_same,
                "min_products": min_count,
                "max_products": max_count,
                "avg_products": round(avg_count, 2),
                "variance": max_count - min_count,
                "parsed_params_consistent": parsed_consistent,
                "consistency_rate": f"{(1 - (max_count - min_count) / max(max_count, 1)) * 100:.1f}%"
            },
            "status": "success"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )