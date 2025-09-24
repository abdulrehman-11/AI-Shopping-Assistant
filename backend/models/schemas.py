from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class SessionData(BaseModel):
    session_id: str
    user_id: Optional[str]
    messages: List[ConversationMessage]
    context: Dict[str, Any]  # Store user preferences, current search state, etc.
    created_at: datetime
    updated_at: datetime

class QueryType(str, Enum):
    VAGUE = "vague"
    SPECIFIC = "specific"
    CLARIFICATION = "clarification"

class QueryClassification(BaseModel):
    query_type: QueryType
    confidence: float
    extracted_info: Dict[str, Any]  # gender, category, brand, etc.
    missing_info: List[str]  # What info is needed

class Product(BaseModel):
    asin: str
    title: str
    category: Optional[str]
    brand: Optional[str]
    stars: Optional[float]
    reviews_count: Optional[int]
    price_value: Optional[float]
    similarity_score: Optional[float] = None

class SearchResult(BaseModel):
    products: List[Product]
    total_found: int
    search_query: str
    filters_applied: Dict[str, Any]

class AgentState(BaseModel):
    """State shared between LangGraph agents"""
    messages: List[ConversationMessage]
    current_query: str
    session_id: str
    user_context: Dict[str, Any]
    query_classification: Optional[QueryClassification] = None
    search_results: Optional[Dict[str, Any]] = None  # Changed from SearchResult to Dict
    needs_clarification: bool = False
    clarification_questions: List[str] = []
    final_response: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True