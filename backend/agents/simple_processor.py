from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any, List
from config import Config
import json

class SimpleProcessor:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.3
        )
    
    def process_query(self, query: str, context: str = "") -> Dict[str, Any]:
        """Process user query and extract search intent with conversation awareness"""
        
        print(f"🤖 SimpleProcessor - Processing: '{query}'")
        print(f"📚 SimpleProcessor - Context: {context[:100]}...")
        
        prompt = f"""
You are an intelligent shopping assistant that understands conversation context and follow-up queries.

Current User Query: "{query}"
Conversation Context: {context}

Analyze this query considering the conversation history. Determine if this is:
1. A new product search
2. A follow-up query (price filter, brand preference, size, etc.)
3. A clarification or modification of previous search

Extract information and create a search-optimized query that incorporates relevant context.

Examples:
- If user first asked "nike shoes for men" then says "more than $100", combine them: "nike shoes for men more than $100"
- If user asked "running shoes" then says "adidas brand", combine: "adidas running shoes"
- If it's a new query, use it as-is but extract all relevant info

Return JSON format:
{{
    "search_terms": "optimized search query for products (combine current query with relevant context)",
    "intent": "specific|vague|off_topic", 
    "query_type": "new_search|follow_up|clarification",
    "response_tone": "helpful|clarifying|redirecting",
    "extracted_info": {{
        "category": "product category if mentioned or inferred from context",
        "gender": "men|women|unisex if specified or inferred",
        "brand": "brand name if mentioned or from context",
        "price_range": "budget|mid|premium if indicated",
        "price_filter": "any specific price constraints (e.g., 'more than $100')",
        "previous_context": "relevant info from conversation history"
    }},
    "natural_response": "DO NOT generate response here - this will be handled by main response generator"
}}

Be smart about context:
- If user says "more expensive ones" or "cheaper options", look at conversation history
- If user mentions just a brand after discussing a category, combine them
- If user asks for "nike" after talking about "shoes for men", combine as "nike shoes for men"
- Extract price filters like "more than $100", "under $50", "between $50-100"

Focus on creating the best possible search query by combining current query with relevant context.
"""
        
        try:
            print("📤 SimpleProcessor - Sending to Gemini...")
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            print(f"📥 SimpleProcessor - Gemini raw response: {content[:200]}...")
            
            # Clean JSON response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(content)
            print(f"✅ SimpleProcessor - Parsed result: {json.dumps(result, indent=2)}")
            
            return result
            
        except Exception as e:
            print(f"❌ SimpleProcessor - Error: {e}")
            return {
                "search_terms": query,
                "intent": "specific",
                "query_type": "new_search",
                "response_tone": "helpful",
                "extracted_info": {},
                "natural_response": ""
            }