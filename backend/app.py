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

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )