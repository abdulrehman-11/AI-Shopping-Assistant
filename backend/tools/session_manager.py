import json
import redis
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from models.schemas import ConversationMessage, MessageRole, SessionData

class SessionManager:
    """Manages conversation sessions and memory using Redis or in-memory fallback"""
    
    def __init__(self, redis_url: str = None):
        self.use_redis = False
        self.memory = {}  # In-memory fallback
        
        if redis_url:
            try:
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()  # Test connection
                self.use_redis = True
                print(f"✅ Connected to Redis for session management")
            except Exception as e:
                print(f"⚠️ Redis connection failed, using in-memory storage: {e}")
                self.redis = None
        else:
            print("📝 Using in-memory session storage")
    
    def get_session(self, session_id: str) -> SessionData:
        """Get or create session data"""
        try:
            if self.use_redis:
                data = self.redis.get(f"session:{session_id}")
                if data:
                    session_dict = json.loads(data)
                    # Convert message dicts back to ConversationMessage objects
                    messages = [
                        ConversationMessage(**msg) for msg in session_dict.get("messages", [])
                    ]
                    session_dict["messages"] = messages
                    return SessionData(**session_dict)
            else:
                if session_id in self.memory:
                    return self.memory[session_id]
        except Exception as e:
            print(f"Session retrieval error: {e}")
        
        # Create new session
        new_session = SessionData(
            session_id=session_id,
            user_id=None,
            messages=[],
            context={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.save_session(new_session)
        return new_session
    
    def save_session(self, session: SessionData):
        """Save session data"""
        try:
            session.updated_at = datetime.now()
            
            if self.use_redis:
                # Convert to dict for JSON serialization
                session_dict = session.dict()
                # Convert datetime objects to ISO strings
                session_dict["created_at"] = session.created_at.isoformat()
                session_dict["updated_at"] = session.updated_at.isoformat()
                # Convert ConversationMessage objects to dicts
                session_dict["messages"] = [msg.dict() for msg in session.messages]
                
                data = json.dumps(session_dict, default=str)
                self.redis.setex(f"session:{session.session_id}", timedelta(days=7), data)
            else:
                self.memory[session.session_id] = session
                
        except Exception as e:
            print(f"Session save error: {e}")
    
    def add_message(self, session_id: str, role: MessageRole, content: str, metadata: Dict[str, Any] = None):
        """Add a message to the session"""
        session = self.get_session(session_id)
        
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        session.messages.append(message)
        
        # Keep only last 20 messages to manage memory
        if len(session.messages) > 20:
            session.messages = session.messages[-20:]
        
        self.save_session(session)
        return session
    
    def get_conversation_context(self, session_id: str, limit: int = 6) -> str:
        """Get recent conversation context as a formatted string"""
        session = self.get_session(session_id)
        
        if not session.messages:
            return ""
        
        # Get recent messages
        recent_messages = session.messages[-limit:]
        
        context_parts = []
        for msg in recent_messages:
            role_label = "User" if msg.role == MessageRole.USER else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def update_context(self, session_id: str, key: str, value: Any):
        """Update session context"""
        session = self.get_session(session_id)
        session.context[key] = value
        self.save_session(session)
    
    def clear_session(self, session_id: str):
        """Clear session data"""
        try:
            if self.use_redis:
                self.redis.delete(f"session:{session_id}")
            else:
                self.memory.pop(session_id, None)
        except Exception as e:
            print(f"Session clear error: {e}")