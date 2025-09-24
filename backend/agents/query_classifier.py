from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from typing import Dict, Any
from config import Config
from models.schemas import QueryClassification, QueryType
import json

class QueryClassifierAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1
        )
        
        self.classification_prompt = PromptTemplate.from_template("""
You are a query classifier for an e-commerce chatbot. Analyze the user's message and classify it.

User Message: "{query}"
Previous Context: {context}

Classify the query as:
1. VAGUE - User wants something but lacks specifics (gender, exact category, etc.)
2. SPECIFIC - User has clear requirements  
3. CLARIFICATION - User is responding to clarification questions

Extract information if available:
- gender (men/women/unisex)
- category (shoes, clothing, electronics, etc.)
- brand preference
- price range preference
- specific features

Identify missing information needed to search effectively.

Return response in this exact JSON format:
{{
    "query_type": "VAGUE|SPECIFIC|CLARIFICATION",
    "confidence": 0.8,
    "extracted_info": {{
        "gender": "men|women|unisex|null",
        "category": "category_name|null",
        "brand": "brand_name|null",
        "price_range": "budget|mid|premium|null",
        "specific_features": ["feature1", "feature2"]
    }},
    "missing_info": ["gender", "specific_category"]
}}
""")
    
    def classify_query(self, query: str, context: Dict[str, Any] = None) -> QueryClassification:
        """Classify user query and extract information"""
        try:
            context_str = json.dumps(context or {})
            
            prompt = self.classification_prompt.format(
                query=query,
                context=context_str
            )
            
            response = self.llm.invoke(prompt)

            # Clean and parse JSON response
            content = response.content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '')

            try:
                result = json.loads(content)
            except:
    # Fallback if JSON parsing fails
                return QueryClassification(
                query_type=QueryType.VAGUE,
                confidence=0.5,
                extracted_info={},
                missing_info=["gender", "category"]
    )
        
            
            return QueryClassification(
                query_type=QueryType(result["query_type"].lower()),
                confidence=result["confidence"],
                extracted_info=result["extracted_info"],
                missing_info=result["missing_info"]
            )
            
        except Exception as e:
            print(f"Query classification error: {e}")
            # Default to VAGUE if classification fails
            return QueryClassification(
                query_type=QueryType.VAGUE,
                confidence=0.5,
                extracted_info={},
                missing_info=["gender", "category"]
            )