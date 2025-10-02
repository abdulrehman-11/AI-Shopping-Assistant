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
    OFF_TOPIC = "off_topic"
    PRODUCT_QUESTION = "product_question"
    UNAVAILABLE = "unavailable"

class QueryClassification(BaseModel):
    query_type: QueryType
    confidence: float
    extracted_info: Dict[str, Any]  # gender, category, brand, product_name, etc.
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
    processed_query: Optional[str] = None
    search_results: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False
    clarification_questions: List[str] = []
    final_response: Optional[str] = None
    is_off_topic: bool = False
    off_topic_reason: Optional[str] = None
    original_simple_response: Optional[str] = None
    shown_product_asins: List[str] = [] 
    
    # New fields for improvements
    conversation_context: Optional[str] = None  # Cached context to avoid multiple fetches
    unavailable_category: Optional[str] = None  # For unavailable category handling
    relevance_status: Optional[str] = None  # highly_relevant, partially_relevant, not_relevant
    relevance_reasoning: Optional[str] = None  # Why products are/aren't relevant
    
    class Config:
        arbitrary_types_allowed = True