import json
import redis
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from models.schemas import ConversationMessage, MessageRole, SessionData
import os
import re

# Global in-memory storage (persists across instance creations)
# This ensures context is maintained even if Redis fails and new instances are created
_GLOBAL_SESSION_MEMORY = {}

class SessionManager:
    """Manages conversation sessions and memory using Redis or in-memory fallback"""

    def __init__(self, redis_url: str = None):
        self.use_redis = False
        self.memory = _GLOBAL_SESSION_MEMORY  # Use global memory (persists across instances)
        
        if redis_url:
            try:
                # Check if using Redis Cloud (SSL required)
                use_ssl = redis_url.startswith('rediss://') or 'redis-cloud.com' in redis_url or 'redns.redis-cloud.com' in redis_url
                
                if use_ssl:
                    # SSL configuration for Redis Cloud
                    # Modern redis-py handles SSL automatically, no ssl_cert_reqs needed
                    self.redis = redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True
                    )
                else:
                    # Regular Redis without SSL
                    self.redis = redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5
                    )
                
                # Test connection
                self.redis.ping()
                self.use_redis = True
                print(f"✅ Connected to Redis for session management")
                
            except redis.ConnectionError as e:
                print(f"⚠️ Redis connection failed, using in-memory storage: {e}")
                self.redis = None
                self.use_redis = False
            except Exception as e:
                print(f"⚠️ Redis setup failed, using in-memory storage: {e}")
                self.redis = None
                self.use_redis = False
        else:
            print("💾 Using in-memory session storage (no Redis URL provided)")
    
    def get_session(self, session_id: str) -> SessionData:
        """Get or create session data"""
        try:
            if self.use_redis and self.redis:
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
            
            if self.use_redis and self.redis:
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
            # Fallback to in-memory if Redis fails
            if self.use_redis:
                print("⚠️ Falling back to in-memory storage for this session")
                self.memory[session.session_id] = session
    
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
    
    def get_conversation_context(self, session_id: str, limit: int = 10) -> str:
        """Get formatted conversation history for context"""
        session = self.get_session(session_id)
        if not session.messages:
            return "No previous conversation."

        recent_messages = session.messages[-limit:] if len(session.messages) > limit else session.messages

        context_parts = []
        for i, msg in enumerate(recent_messages):
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            # Truncate long messages for context
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            context_parts.append(f"{role}: {content}")

        return "\n".join(context_parts)
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the conversation for analytics"""
        session = self.get_session(session_id)
        
        user_messages = [msg for msg in session.messages if msg.role == MessageRole.USER]
        assistant_messages = [msg for msg in session.messages if msg.role == MessageRole.ASSISTANT]
        
        # Extract common topics/keywords from user messages
        topics = []
        common_keywords = ['shoes', 'shirt', 'pants', 'electronics', 'phone', 'laptop', 'nike', 'adidas']
        
        for msg in user_messages:
            content_lower = msg.content.lower()
            for keyword in common_keywords:
                if keyword in content_lower and keyword not in topics:
                    topics.append(keyword)
        
        return {
            "total_messages": len(session.messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "topics_discussed": topics,
            "session_duration": (session.updated_at - session.created_at).total_seconds() if session.updated_at else 0,
            "last_activity": session.updated_at.isoformat() if session.updated_at else None
        }
    
    def get_user_preferences(self, session_id: str) -> Dict[str, Any]:
        """Extract user preferences from conversation history"""
        session = self.get_session(session_id)
        preferences = {
            "categories": [],
            "brands": [],
            "price_range": None,
            "gender": None,
            "size": None
        }
        
        # Analyze user messages for preferences
        user_messages = [msg.content.lower() for msg in session.messages if msg.role == MessageRole.USER]
        all_text = " ".join(user_messages)
        
        # Extract categories
        categories = ['shoes', 'clothing', 'electronics', 'sports', 'home', 'books', 'toys']
        preferences["categories"] = [cat for cat in categories if cat in all_text]
        
        # Extract brands
        brands = ['nike', 'adidas', 'apple', 'samsung', 'puma', 'reebok', 'amazon']
        preferences["brands"] = [brand for brand in brands if brand in all_text]
        
        # Extract gender preferences - ENHANCED with family relationships
        # FIX: Use word boundaries to prevent "he" matching in "her", "men" in "recommend", etc.
        male_keywords = ['men', 'man', 'male', 'boys', 'husband', 'father', 'dad', 'brother', 'son', 'boyfriend', 'him', 'his']
        female_keywords = ['women', 'woman', 'female', 'girls', 'ladies', 'wife', 'mother', 'mom', 'sister', 'daughter', 'girlfriend', 'her']

        # Count matches with word boundaries to avoid false positives
        male_matches = sum(1 for word in male_keywords if re.search(r'\b' + re.escape(word) + r'\b', all_text))
        female_matches = sum(1 for word in female_keywords if re.search(r'\b' + re.escape(word) + r'\b', all_text))

        # Prioritize whichever gender has MORE matches (more confident detection)
        if female_matches > male_matches:
            preferences["gender"] = "female"
        elif male_matches > 0:
            preferences["gender"] = "male"
        
        # Extract price preferences
        if any(word in all_text for word in ['cheap', 'budget', 'affordable', 'low price']):
            preferences["price_range"] = "budget"
        elif any(word in all_text for word in ['premium', 'expensive', 'high quality', 'luxury']):
            preferences["price_range"] = "premium"
        elif any(word in all_text for word in ['mid', 'medium', 'moderate']):
            preferences["price_range"] = "mid"
        
        return preferences
    
    def update_context(self, session_id: str, key: str, value: Any):
        """Update session context"""
        session = self.get_session(session_id)
        session.context[key] = value
        self.save_session(session)
    
    def get_context_value(self, session_id: str, key: str, default: Any = None) -> Any:
        """Get a specific value from session context"""
        session = self.get_session(session_id)
        return session.context.get(key, default)

    def get_last_search_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get context from the last successful product search.
        Returns category, gender, price_range from last search.
        """
        session = self.get_session(session_id)

        # Get from session.context (updated after each search)
        return {
            "last_category": session.context.get("last_category"),
            "last_gender": session.context.get("last_gender"),
            "last_min_price": session.context.get("last_min_price"),
            "last_max_price": session.context.get("last_max_price"),
            "last_product_count": session.context.get("last_product_count", 5),
            "shown_asins": session.context.get("shown_asins", [])
        }

    def update_search_context(self, session_id: str, category: Optional[str], gender: Optional[str],
                            min_price: Optional[float], max_price: Optional[float],
                            product_count: int, shown_asins: List[str]):
        """Update session context after a successful search"""
        session = self.get_session(session_id)

        if category:
            session.context["last_category"] = category
        if gender:
            session.context["last_gender"] = gender
        if min_price is not None:
            session.context["last_min_price"] = min_price
        if max_price is not None:
            session.context["last_max_price"] = max_price

        session.context["last_product_count"] = product_count
        session.context["shown_asins"] = shown_asins

        self.save_session(session)
    
    def clear_session(self, session_id: str):
        """Clear session data"""
        try:
            if self.use_redis and self.redis:
                self.redis.delete(f"session:{session_id}")
            else:
                self.memory.pop(session_id, None)
        except Exception as e:
            print(f"Session clear error: {e}")
    
    def cleanup_old_sessions(self, days: int = 7):
        """Clean up old sessions (for in-memory storage)"""
        if not self.use_redis:  # Redis handles expiration automatically
            try:
                cutoff_date = datetime.now() - timedelta(days=days)
                sessions_to_remove = []
                
                for session_id, session in self.memory.items():
                    if session.updated_at < cutoff_date:
                        sessions_to_remove.append(session_id)
                
                for session_id in sessions_to_remove:
                    del self.memory[session_id]
                    
                if sessions_to_remove:
                    print(f"Cleaned up {len(sessions_to_remove)} old sessions")
                    
            except Exception as e:
                print(f"Session cleanup error: {e}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session manager statistics"""
        try:
            if self.use_redis and self.redis:
                # Get Redis stats
                info = self.redis.info('memory')
                return {
                    "storage_type": "redis",
                    "connected": True,
                    "memory_usage": info.get('used_memory_human', 'unknown'),
                    "total_keys": self.redis.dbsize()
                }
            else:
                return {
                    "storage_type": "in_memory",
                    "connected": True,
                    "active_sessions": len(self.memory),
                    "total_messages": sum(len(session.messages) for session in self.memory.values())
                }
        except Exception as e:
            return {
                "storage_type": "redis" if self.use_redis else "in_memory",
                "connected": False,
                "error": str(e)
            }