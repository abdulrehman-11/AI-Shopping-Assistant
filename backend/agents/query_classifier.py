from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from typing import Dict, Any
from config import Config
from models.schemas import QueryClassification, QueryType
import json
import re

class QueryClassifierAgent:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1
        )
        
        self.classification_prompt = PromptTemplate.from_template("""
You are a strict query classifier for an e-commerce shopping assistant. Decide routing.

User Message: "{query}"
Conversation Context: {context}

Classify into exactly one of:
- VAGUE: shopping intent but lacks specifics (gender, category, brand, size, budget)
- SPECIFIC: clear product intent with sufficient details to search
- CLARIFICATION: user is answering previous clarification questions
- OFF_TOPIC: not about shopping or our products (e.g., general knowledge like China history)

Extract fields when available: gender (men/women/unisex), category, brand, price_range (budget/mid/premium), size, usage (running, hiking, office, gift), and key features.

List what is missing to search effectively (e.g., gender, category, budget, size, usage).

Output STRICT JSON only with these keys:
{
  "query_type": "VAGUE|SPECIFIC|CLARIFICATION|OFF_TOPIC",
  "confidence": 0.0-1.0,
  "extracted_info": {
    "gender": "men|women|unisex|null",
    "category": "string|null",
    "brand": "string|null",
    "price_range": "budget|mid|premium|null",
    "size": "string|null",
    "usage": "string|null",
    "specific_features": ["feature1", "feature2"]
  },
  "missing_info": ["field1", "field2"],
  "off_topic_reason": "string|null"
}
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
            except Exception:
                # Fallback if JSON parsing fails
                return QueryClassification(
                    query_type=QueryType.VAGUE,
                    confidence=0.5,
                    extracted_info={},
                    missing_info=["gender", "category"]
                )
            
            query_type_value = str(result.get("query_type", "vague")).lower()
            if query_type_value not in {"vague", "specific", "clarification", "off_topic"}:
                query_type_value = "vague"

            # Start with LLM extraction
            extracted = result.get("extracted_info", {}) or {}
            missing = set((result.get("missing_info", []) or []))

            # Deterministic heuristics to patch common cases (e.g., "nike shoes for men")
            q_lower = (query or "").lower()
            # Gender
            gender = extracted.get("gender")
            if not gender:
                if re.search(r"\b(men|man's|male|boys)\b", q_lower):
                    gender = "men"
                elif re.search(r"\b(women|woman|female|girls|ladies)\b", q_lower):
                    gender = "women"
                if gender:
                    extracted["gender"] = gender
                    if "gender" in missing:
                        missing.discard("gender")
            # Category
            category = extracted.get("category")
            if not category:
                if re.search(r"\b(sneaker|sneakers|shoe|shoes|trainers|running shoes)\b", q_lower):
                    category = "shoes"
                elif re.search(r"\b(sandal|sandals|flip flops)\b", q_lower):
                    category = "sandals"
                elif re.search(r"\b(boot|boots)\b", q_lower):
                    category = "boots"
                if category:
                    extracted["category"] = category
                    if "category" in missing:
                        missing.discard("category")
            # Brand (minimal list; can be extended)
            brand = extracted.get("brand")
            if not brand:
                if re.search(r"\bnike\b", q_lower):
                    brand = "Nike"
                elif re.search(r"\badidas\b", q_lower):
                    brand = "Adidas"
                elif re.search(r"\bpuma\b", q_lower):
                    brand = "Puma"
                if brand:
                    extracted["brand"] = brand
                    if "brand" in missing:
                        missing.discard("brand")

            # If we clearly see shopping signals (gender/category/brand), treat as SPECIFIC unless off-topic
            if query_type_value != "off_topic" and (extracted.get("category") or extracted.get("brand") or extracted.get("gender")):
                query_type_value = "specific"

            return QueryClassification(
                query_type=QueryType(query_type_value),
                confidence=float(result.get("confidence", 0.7)),
                extracted_info=extracted,
                missing_info=sorted(list(missing))
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