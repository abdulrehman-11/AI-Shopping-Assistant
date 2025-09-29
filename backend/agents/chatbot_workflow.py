from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from models.schemas import AgentState, ConversationMessage, MessageRole, QueryClassification, QueryType
from agents.simple_processor import SimpleProcessor
from tools.pinecone_tool import PineconeTool
from tools.database_tool import DatabaseTool
from tools.session_manager import SessionManager
from tools.json_fallback import JsonFallbackTool
from tools.cache_manager import CacheManager
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config
import cohere
import json
import re

class ChatbotWorkflow:
    def __init__(self):
        print("🔧 Initializing ChatbotWorkflow...")
        
        self.simple_processor = SimpleProcessor()
        self.pinecone_tool = PineconeTool()
        self.session_manager = SessionManager(Config.REDIS_URL)
        self.json_fallback = JsonFallbackTool()
        self.cache_manager = CacheManager(self.session_manager.redis if self.session_manager.use_redis else None)
        self.cohere_client = cohere.Client(Config.COHERE_API_KEY)
        
        # Initialize Gemini for response generation and classification
        self.response_llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.3
        )
        
        self.classifier_llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.1
        )
        print("✅ All tools initialized successfully")
    
        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """Build workflow with improved routing"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify_intent", self.classify_intent_node)
        workflow.add_node("handle_off_topic", self.handle_off_topic_node)
        workflow.add_node("handle_unavailable_category", self.handle_unavailable_category_node)
        workflow.add_node("handle_vague", self.handle_vague_node)
        workflow.add_node("answer_product_question", self.answer_product_question_node)
        workflow.add_node("process_query", self.process_query_node)
        workflow.add_node("search_products", self.search_products_node)
        workflow.add_node("validate_relevance", self.validate_relevance_node)
        workflow.add_node("handle_no_relevant_products", self.handle_no_relevant_products_node)
        workflow.add_node("generate_response", self.generate_response_node)
        
        # Set entry point and add conditional edges
        workflow.set_entry_point("classify_intent")
        workflow.add_conditional_edges(
            "classify_intent",
            self.route_after_classification,
            {
                "off_topic": "handle_off_topic",
                "unavailable": "handle_unavailable_category",
                "vague": "handle_vague",
                "product_question": "answer_product_question",
                "specific": "process_query"
            }
        )
        
        # Connect remaining edges
        workflow.add_edge("handle_off_topic", END)
        workflow.add_edge("handle_unavailable_category", END)
        workflow.add_edge("handle_vague", END)
        workflow.add_edge("answer_product_question", END)
        workflow.add_edge("process_query", "search_products")
        workflow.add_edge("search_products", "validate_relevance")
        
        # Conditional edge after validation
        workflow.add_conditional_edges(
            "validate_relevance",
            self.route_after_validation,
            {
                "no_relevant": "handle_no_relevant_products",
                "relevant": "generate_response"
            }
        )
        
        workflow.add_edge("handle_no_relevant_products", END)
        workflow.add_edge("generate_response", END)
        
        return workflow
    
    def classify_intent_node(self, state: AgentState) -> AgentState:
        """Enhanced classification with inventory check and question detection"""
        print(f"\n🎯 STEP 0: Classifying Intent")
        print(f"📝 User Query: '{state.current_query}'")
        
        # Get context once and store in state for reuse
        if not hasattr(state, 'conversation_context') or not state.conversation_context:
            state.conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=10)
        
        conversation_context = state.conversation_context
        
        prompt = f"""
Classify this user query for an e-commerce shopping assistant.

Current Query: "{state.current_query}"
Conversation History: {conversation_context}

Classification Rules:
1. OFF_TOPIC: Not related to shopping, products, or e-commerce
   - Examples: "What is China?", "How to cook pasta?", "What's the weather?"
   
2. PRODUCT_QUESTION: Asking for information about specific product (not browsing/buying)
   - Examples: "What is the price of Nike Air Max?", "Tell me about Adidas Ultraboost", 
               "Is Sony headphone waterproof?", "What colors available for iPhone 14?"
   - Key indicators: "what is", "tell me about", "how much", "what color", "describe"
   
3. VAGUE: Shopping/buying intent but missing critical info (GENDER for clothing/shoes/accessories)
   - Examples: "I want shoes", "looking for clothes", "need a watch"
   - NOTE: Missing brand, size, price is OK - only missing gender makes it vague
   - NOTE: Also note that not everything need to be gendered - e.g. "I want a laptop" is SPECIFIC, Understand the query on your own and decide either it neeed to be gendered or not
   - IMPORTANT: Extract category to check inventory
   
4. SPECIFIC: Clear shopping intent with sufficient details OR follow-up to previous specific query
   - Examples: "shoes for men", "women's dress", "nike shoes", "more expensive", "under $100", or even just 'men or women'
   - Follow-ups are SPECIFIC if previous context has gender 

Consider conversation context - if user previously specified gender, follow-ups are SPECIFIC.

Return JSON:
{{
    "classification": "OFF_TOPIC|PRODUCT_QUESTION|VAGUE|SPECIFIC",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of classification",
    "extracted_info": {{
        "category": "extracted product category (shoes, shirt, laptop, etc.)",
        "brand": "extracted brand if mentioned",
        "product_name": "specific product name if asking about it",
        "has_gender": true/false,
        "is_question": true/false,
        "is_followup": true/false
    }}
}}
"""

        try:
            print("🔤 Sending to Gemini classifier...")
            response = self.classifier_llm.invoke(prompt)
            content = response.content.strip()
            
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(content)
            print(f"📥 Classification Result: {json.dumps(result, indent=2)}")
            
            classification_type = result.get("classification", "SPECIFIC")
            extracted_info = result.get("extracted_info", {})
            
            # Quick inventory check for VAGUE queries
            if classification_type == "VAGUE":
                category = extracted_info.get("category", "")
                if category:
                    print(f"🔍 Checking inventory for category: {category}")
                    inventory_check = self._quick_inventory_check(category)
                    
                    if not inventory_check:
                        print(f"❌ Category '{category}' not available in inventory")
                        classification_type = "UNAVAILABLE"
                        state.unavailable_category = category
            
            query_classification = QueryClassification(
                query_type=QueryType(classification_type.lower()),
                confidence=float(result.get("confidence", 0.8)),
                extracted_info=extracted_info,
                missing_info=["gender"] if classification_type == "VAGUE" else []
            )
            
            state.query_classification = query_classification
            print(f"✅ Intent classified as: {classification_type}")
            
        except Exception as e:
            print(f"❌ Classification error: {e}")
            # Default to SPECIFIC to continue workflow
            state.query_classification = QueryClassification(
                query_type=QueryType.SPECIFIC,
                confidence=0.5,
                extracted_info={},
                missing_info=[]
            )
        
        return state
    
    def _quick_inventory_check(self, category: str) -> bool:
        """Quick check if category exists - using better search strategy"""
        try:
            # Search with category + common descriptors to get better results
            test_queries = [
                category,
                f"{category} products",
                f"buy {category}",
            ]
        
            for query in test_queries:
                products = self.pinecone_tool.search_similar_products(
                    query=query,
                    filters=None,
                    top_k=5  # Get top 5 to verify quality
            )
            
                if products and len(products) > 0:
                    # Verify at least one product has decent similarity
                    # and title/category somewhat matches
                    for p in products:
                        title = (p.get('title', '') or '').lower()
                        cat = (p.get('category', '') or '').lower()
                    
                        # Check if category word appears in title or category field
                        if category.lower() in title or category.lower() in cat:
                            return True
                    
                        # Or if similarity is very high (>0.75), trust it
                        if p.get('similarity_score', 0) > 0.75:
                            return True
        
            return False
        
        except Exception as e:
            print(f"⚠️ Inventory check error: {e}")
            return True  # Default to assuming it exists
    
    def route_after_classification(self, state: AgentState) -> str:
        """Route based on classification"""
        classification = state.query_classification.query_type.value
        
        # Map UNAVAILABLE to unavailable route
        if hasattr(state, 'unavailable_category') and state.unavailable_category:
            return "unavailable"
        
        # Map PRODUCT_QUESTION
        if classification == "product_question":
            return "product_question"
        
        # Standard routing
        route_map = {
            "off_topic": "off_topic",
            "vague": "vague",
            "specific": "specific"
        }
        
        route = route_map.get(classification, "specific")
        print(f"🚦 Routing to: {route}")
        return route
    
    def handle_off_topic_node(self, state: AgentState) -> AgentState:
        """Handle off-topic queries"""
        print(f"\n❌ STEP: Handling Off-Topic Query")
        
        prompt = f"""
The user asked an off-topic question: "{state.current_query}"

Generate a polite response that:
1. Acknowledges their question
2. Explains you're a shopping assistant
3. Offers to help with Men & women fashion products recommendations
4. Be friendly and helpful

Examples:
- For "What is China?": "I'm a shopping assistant focused on helping you find great products. While I can't provide information about countries, I'd be happy to help you find products from China or any other shopping needs you have!"
- For "How to cook?": "I'm specialized in helping you find products to buy rather than cooking instructions. However, I can help you find kitchen appliances, cookware, or ingredients if you're looking to shop for cooking supplies!"

Generate response:"""

        try:
            response = self.response_llm.invoke(prompt)
            state.final_response = response.content.strip()
        except Exception as e:
            print(f"❌ Error generating off-topic response: {e}")
            state.final_response = "I'm a shopping assistant here to help you find great products. What would you like to shop for today?"
        
        print(f"💬 Off-topic Response: {state.final_response}")
        return state
    
    def handle_unavailable_category_node(self, state: AgentState) -> AgentState:
        """Handle queries for unavailable categories"""
        print(f"\n🚫 STEP: Handling Unavailable Category")
        
        category = getattr(state, 'unavailable_category', 'that product')
        
        prompt = f"""
The user asked for: "{state.current_query}"
Category requested: "{category}"

This category is not available in our inventory.

Generate a helpful response that:
1. Politely informs them we don't have this category
2. Suggests they try other product categories we might have
3. Be encouraging and helpful
4. Keep it brief

Example: "I apologize, but we don't currently have {category} in our inventory. However, I can help you find other products like shoes, clothing, or watches etc. What else can I help you shop for?"

Generate response:"""

        try:
            response = self.response_llm.invoke(prompt)
            state.final_response = response.content.strip()
        except Exception as e:
            print(f"❌ Error: {e}")
            state.final_response = f"I apologize, but we don't currently have {category} available. Can I help you find something else?"
        
        print(f"💬 Unavailable Response: {state.final_response}")
        return state
    
    def handle_vague_node(self, state: AgentState) -> AgentState:
        """Handle vague queries that need clarification"""
        print(f"\n❓ STEP: Handling Vague Query")
        
        conversation_context = state.conversation_context
        
        prompt = f"""
User has shopping intent but didn't specify gender: "{state.current_query}"
Conversation History: {conversation_context}

Generate a helpful response that:
1. Acknowledges their interest
2. Asks specifically about gender (men/women/kids)
3. Can suggest popular options
4. Be encouraging and specific to their query

Examples:
- For "I want shoes": "I'd love to help you find the perfect shoes! Are you looking for shoes for men, women, or kids? Once I know that, I can show you some great options."
- For "need a watch": "Great choice! Watches make excellent purchases. Are you shopping for a men's watch, women's watch, or perhaps for a child? Let me know and I'll find some perfect options for you."

Generate a specific response for their query:"""

        try:
            response = self.response_llm.invoke(prompt)
            state.final_response = response.content.strip()
            state.needs_clarification = True
        except Exception as e:
            print(f"❌ Error generating vague response: {e}")
            state.final_response = "I'd be happy to help you find what you're looking for! Could you let me know if you're shopping for men, women, or kids?"
            state.needs_clarification = True
        
        print(f"💬 Vague Query Response: {state.final_response}")
        return state
    
    def answer_product_question_node(self, state: AgentState) -> AgentState:
        """Handle specific product questions (price, features, availability)"""
        print(f"\n❓ STEP: Answering Product Question")
        
        extracted_info = state.query_classification.extracted_info
        product_name = extracted_info.get("product_name", "")
        brand = extracted_info.get("brand", "")
        
        # Build search query for the specific product
        search_query = f"{brand} {product_name}".strip() if brand else product_name
        if not search_query:
            search_query = state.current_query
        
        print(f"🔍 Searching for product: {search_query}")
        
        # Search for the specific product
        try:
            products = self.pinecone_tool.search_similar_products(
                query=search_query,
                filters=None,
                top_k=3
            )
            
            if products:
                products = self.json_fallback.enrich_products(products)
                
                # Get the best match
                best_match = products[0]
                
                # Build detailed product info for answer
                product_details = {
                    "title": best_match.get("title", "Product"),
                    "brand": best_match.get("brand", "Unknown"),
                    "price": f"${best_match.get('price_value', 0):.2f}" if best_match.get('price_value') else "Price not available",
                    "rating": best_match.get("stars", "N/A"),
                    "reviews": best_match.get("reviews_count", 0),
                    "category": best_match.get("category", ""),
                    "description": best_match.get("description", "")
                }
                
                prompt = f"""
User asked a question about a product: "{state.current_query}"

Found Product Information:
- Title: {product_details['title']}
- Brand: {product_details['brand']}
- Price: {product_details['price']}
- Rating: {product_details['rating']} stars ({product_details['reviews']} reviews)
- Category: {product_details['category']}
- Description: {product_details['description'][:200]}

Generate a direct, helpful answer to their question using this information.
Be conversational and specific. Answer what they asked clearly.

If they asked about price, lead with the price.
If they asked about features, focus on features from description.
If they asked "what is" or "tell me about", give a brief overview.

Keep it concise (2-3 sentences max).

Answer:"""

                response = self.response_llm.invoke(prompt)
                state.final_response = response.content.strip()
                
                # Store product for potential display
                ui_product = {
                    "asin": best_match.get("asin"),
                    "image": best_match.get("image_url") or best_match.get("thumbnail_image") or "",
                    "title": product_details["title"],
                    "description": product_details["brand"],
                    "rating": float(product_details["rating"]) if product_details["rating"] != "N/A" else 0,
                    "reviews": product_details["reviews"],
                    "price": product_details["price"],
                    "url": best_match.get("url") or "",
                }
                
                state.search_results = {
                    "products": products,
                    "display_products": products[:1],
                    "ui_products": [ui_product],
                    "total_found": 1,
                    "search_query": search_query,
                    "is_question_answer": True
                }
                
            else:
                state.final_response = f"I couldn't find specific information about {search_query}. Could you provide more details or try rephrasing your question?"
                state.search_results = {"products": [], "ui_products": [], "total_found": 0}
                
        except Exception as e:
            print(f"❌ Product question error: {e}")
            state.final_response = "I'm having trouble finding that product information. Could you try rephrasing your question?"
            state.search_results = {"products": [], "ui_products": [], "total_found": 0}
        
        print(f"💬 Answer: {state.final_response}")
        return state
    
    def process_query_node(self, state: AgentState) -> AgentState:
        """Process specific queries with conversation context"""
        print(f"\n🔍 STEP 1: Processing Specific Query")
        print(f"📝 User Query: '{state.current_query}'")
        
        current_query = state.current_query
        session_id = state.session_id
        
        # Reuse context from state
        conversation_context = state.conversation_context
        print(f"📚 Using Cached Context")
        
        # Get user preferences
        user_preferences = self.session_manager.get_user_preferences(session_id)
        print(f"👤 User Preferences: {user_preferences}")
        
        # Build enhanced query with context
        enhanced_query = self._build_contextual_query(current_query, conversation_context, user_preferences)
        print(f"🔎 Enhanced Query: '{enhanced_query}'")
        
        # Process query naturally
        print("🤖 Sending to SimpleProcessor...")
        processed = self.simple_processor.process_query(enhanced_query, conversation_context)
        print(f"📊 SimpleProcessor Result: {json.dumps(processed, indent=2)}")
        
        # Use the enhanced search terms from SimpleProcessor
        final_search_query = processed.get("search_terms", enhanced_query)
        print(f"🎯 Final Search Query: '{final_search_query}'")
        
        # Store results
        state.processed_query = final_search_query
        state.original_simple_response = processed.get("natural_response", "")
        
        print(f"✅ Query processed successfully")
        print(f"🔎 Will search for: '{final_search_query}'")
        
        return state
    
    def _build_contextual_query(self, current_query: str, context: str, preferences: Dict) -> str:
        """Build enhanced query with conversation context"""
        
        current_lower = current_query.lower()
        
        # Common follow-up patterns
        price_patterns = [r'more than \$?(\d+)', r'under \$?(\d+)', r'between \$?(\d+)', r'expensive', r'cheap', r'budget']
        brand_patterns = [r'\b(nike|adidas|puma|reebok|asics|new balance|under armour)\b']
        category_patterns = [r'\b(shoes|sneakers|boots|sandals|running|basketball)\b']
        
        is_followup = any(re.search(pattern, current_lower) for pattern in price_patterns + brand_patterns + category_patterns)
        
        if is_followup and context and "No previous conversation" not in context:
            # Extract context from conversation
            prev_category = preferences.get('categories', [])
            prev_brands = preferences.get('brands', [])
            prev_gender = preferences.get('gender', '')
            
            enhanced_parts = []
            if prev_brands:
                enhanced_parts.append(prev_brands[0])
            if prev_category:
                enhanced_parts.append(prev_category[0])
            if prev_gender:
                enhanced_parts.append(f"for {prev_gender}")
            
            enhanced_parts.append(current_query)
            
            enhanced_query = " ".join(enhanced_parts)
            return enhanced_query
        
        return current_query
    
    def search_products_node(self, state: AgentState) -> AgentState:
        """Search for products with proper query usage"""
        print(f"\n🔍 STEP 2: Searching Products")
        
        # Use processed_query instead of current_query
        search_query = state.processed_query or state.current_query
        print(f"🔎 Search Query: '{search_query}'")
        
        # Check cache first
        cached_results = self.cache_manager.get_cached_search(search_query)
        if cached_results:
            print("📦 Using cached results")
            state.search_results = cached_results
            return state
        
        # Extract price filters from search query
        price_filters = self._extract_price_filters(search_query)
        print(f"💰 Price Filters: {price_filters}")
        
        # Build filters
        filters = {}
        if price_filters:
            filters.update(price_filters)
            
        print(f"🔧 Search Filters: {filters}")
        
        # Search in Pinecone with proper query
        print("🔍 Searching in Pinecone...")
        products = self.pinecone_tool.search_similar_products(
            query=search_query,
            filters=filters,
            top_k=15  # Get more for better filtering
        )
        
        print(f"📊 Pinecone found {len(products) if products else 0} products")
        
        # Fallback search if no results
        if not products:
            print("🔄 No results found, trying fallback search...")
            conversation_context = state.conversation_context
            user_preferences = self.session_manager.get_user_preferences(state.session_id)
            
            fallback_queries = []
            if user_preferences.get('categories'):
                fallback_queries.append(user_preferences['categories'][0])
            if user_preferences.get('gender'):
                fallback_queries.append(f"{user_preferences['categories'][0] if user_preferences.get('categories') else 'products'} for {user_preferences['gender']}")
            
            for fallback_query in fallback_queries:
                products = self.pinecone_tool.search_similar_products(
                    query=fallback_query,
                    filters={},
                    top_k=10
                )
                if products:
                    print(f"📊 Fallback search '{fallback_query}' found {len(products)} products")
                    break
        
        if products:   
            products = self.json_fallback.enrich_products(products)
            print(f"🔗 After enrichment: {len(products)} products")
        
        # Cohere Rerank
        if products and len(products) > 1:
            try:
                print("🎯 Reranking with Cohere...")
                docs = []
                for p in products:
                    title = p.get("title") or ""
                    brand = p.get("brand") or ""
                    cat = p.get("category") or ""
                    price = p.get('price_value', 0)
                    features = f"{title} brand:{brand} category:{cat} price:${price} stars:{p.get('stars')} reviews:{p.get('reviews_count')}"
                    docs.append(features)
                
                rer = self.cohere_client.rerank(
                    model="rerank-english-v3.0",
                    query=search_query,
                    documents=docs,
                    top_n=min(10, len(docs))
                )
                
                reordered = []
                for r in rer.results:
                    prod = products[r.index]
                    prod["rerank_score"] = float(getattr(r, 'relevance_score', 0))
                    reordered.append(prod)
                
                products = reordered
                print(f"🎯 Reranked to {len(products)} products")
                
            except Exception as e:
                print(f"❌ Reranking failed: {e}")
        
        # Apply post-search price filtering
        if price_filters and products:
            products = self._apply_price_filters(products, price_filters)
            print(f"💰 After price filtering: {len(products)} products")
        
        # Limit to top 5 for validation
        display_products = products[:5] if products else []
        
        # Store results for validation
        search_results = {
            "products": products,
            "display_products": display_products,
            "total_found": len(products),
            "search_query": search_query,
            "filters_applied": filters,
            "original_query": state.current_query
        }
        
        self.cache_manager.cache_search_results(search_query, search_results, filters)
        
        state.search_results = search_results
        print(f"✅ Search completed: {len(products)} total, validating top {len(display_products)}")
        
        return state
    
    def validate_relevance_node(self, state: AgentState) -> AgentState:
        """Validate if search results are relevant to user's query"""
        print(f"\n🎯 STEP 2.5: Validating Relevance")
        
        search_results = state.search_results or {}
        products = search_results.get("display_products", [])
        original_query = state.current_query
        
        if not products:
            state.relevance_status = "no_results"
            return state
        
        # Build product summary for validation
        product_summaries = []
        for i, p in enumerate(products[:3], 1):  # Check top 3
            summary = f"{i}. {p.get('title', 'Product')} - {p.get('brand', '')} - {p.get('category', '')} - ${p.get('price_value', 0):.2f}"
            product_summaries.append(summary)
        
        prompt = f"""
User's Query: "{original_query}"

Top Search Results:
{chr(10).join(product_summaries)}

Analyze if these products match what the user is looking for. Consider:
1. Product category match (shoes vs shirts vs other)
2. Gender/demographic match (men vs women)
3. Brand match (if user specified brand)
4. General product type match

Classify the match as:
- HIGHLY_RELEVANT: Products exactly match the query
- PARTIALLY_RELEVANT: Products are similar/related (e.g., user wanted running shoes, got sports shoes)
- NOT_RELEVANT: Products are completely different (e.g., user wanted shirts, got shoes or unrelated items)
- You must neeed to carefully classify the products that are unmatched to the query as NOT_RELEVANT, You can check their titles, categories, brands and prices to decide. (Mainly title or descriotion will help you decide)

Return JSON:
{{
    "relevance": "HIGHLY_RELEVANT|PARTIALLY_RELEVANT|NOT_RELEVANT",
    "reasoning": "brief explanation",
    "confidence": 0.0-1.0
}}
"""

        try:
            print("🔤 Validating with Gemini...")
            response = self.classifier_llm.invoke(prompt)
            content = response.content.strip()
            
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(content)
            relevance = result.get("relevance", "HIGHLY_RELEVANT")
            
            print(f"📊 Relevance: {relevance}")
            print(f"💡 Reasoning: {result.get('reasoning', '')}")
            
            state.relevance_status = relevance.lower()
            state.relevance_reasoning = result.get("reasoning", "")
            
        except Exception as e:
            print(f"❌ Validation error: {e}")
            # Default to relevant to continue
            state.relevance_status = "highly_relevant"
        
        return state
    
    def route_after_validation(self, state: AgentState) -> str:
        """Route based on relevance validation"""
        relevance = getattr(state, 'relevance_status', 'highly_relevant')
        
        if relevance == "not_relevant" or relevance == "no_results":
            print("🚦 Routing to: no_relevant_products")
            return "no_relevant"
        
        print("🚦 Routing to: generate_response")
        return "relevant"
    
    def handle_no_relevant_products_node(self, state: AgentState) -> AgentState:
        """Handle case when no relevant products found"""
        print(f"\n🚫 STEP: Handling No Relevant Products")
        
        relevance_status = getattr(state, 'relevance_status', 'no_results')
        search_results = state.search_results or {}
        products = search_results.get("display_products", [])
        
        if relevance_status == "no_results" or not products:
            # No products at all
            prompt = f"""
User searched for: "{state.current_query}"
No products were found.

Generate a helpful response that:
1. Apologizes for not finding products
2. Ask them we dont have what they are looking for, can you try simething else or let me recommend some popular products
3. Offers to help with related products
4. Keep it brief and encouraging

Response:"""
        else:
            # Products found but not relevant
            reasoning = getattr(state, 'relevance_reasoning', 'Products did not match query')
            
            prompt = f"""
User searched for: "{state.current_query}"
Search returned products but they don't match what user is looking for.
Reason: {reasoning}

Generate a response that:
1. Clearly states we couldn't find what they're looking for 
2. Does NOT show or suggest the irrelevant products
3. Asks them to try with different keywords or more details, or offers to search some releted products. 
4. Be helpful and encouraging

Example: "I couldn't find {state.current_query} that match your requirements. Could you try rephrasing or adding more details about what you're looking for? I'm here to help!"

Response:"""

        try:
            response = self.response_llm.invoke(prompt)
            state.final_response = response.content.strip()
        except Exception as e:
            print(f"❌ Error: {e}")
            state.final_response = f"I couldn't find {state.current_query} that match your requirements. Could you try rephrasing or providing more details?"
        
        # Clear products so they don't display
        state.search_results = {
            "products": [],
            "display_products": [],
            "ui_products": [],
            "total_found": 0,
            "search_query": state.current_query,
            "relevance_issue": True
        }
        
        print(f"💬 No Relevant Response: {state.final_response}")
        return state
    
    def _extract_price_filters(self, query: str) -> Dict[str, Any]:
        """Extract price filters from query"""
        query_lower = query.lower()
        filters = {}
        
        more_than_match = re.search(r'more than \$?(\d+)', query_lower)
        if more_than_match:
            filters['price_value'] = {'$gte': float(more_than_match.group(1))}
            return filters
        
        under_match = re.search(r'under \$?(\d+)', query_lower)
        if under_match:
            filters['price_value'] = {'$lte': float(under_match.group(1))}
            return filters
        
        between_match = re.search(r'between \$?(\d+) and \$?(\d+)', query_lower)
        if between_match:
            filters['price_value'] = {
                '$gte': float(between_match.group(1)),
                '$lte': float(between_match.group(2))
            }
            return filters
        
        return filters
    
    def _apply_price_filters(self, products: List[Dict], price_filters: Dict) -> List[Dict]:
        """Apply price filters to products list"""
        if not price_filters.get('price_value'):
            return products
        
        filtered = []
        price_constraint = price_filters['price_value']
        
        for product in products:
            price = product.get('price_value', 0)
            if not price:
                continue
                
            if '$gte' in price_constraint and price < price_constraint['$gte']:
                continue
            if '$lte' in price_constraint and price > price_constraint['$lte']:
                continue
                
            filtered.append(product)
        
        return filtered
    
    def generate_response_node(self, state: AgentState) -> AgentState:
        """Generate natural response using Gemini"""
        print(f"\n🤖 STEP 3: Generating Response with Gemini")
        
        search_results = state.search_results or {}
        products = search_results.get("display_products", [])
        total_found = search_results.get("total_found", 0)
        relevance_status = getattr(state, 'relevance_status', 'highly_relevant')
        
        print(f"📊 Total products found: {total_found}")
        print(f"📱 Products to display: {len(products)}")
        print(f"🎯 Relevance: {relevance_status}")
        
        # Limit to top 3 for display
        display_products = products[:3] if products else []
        
        if display_products:
            conversation_context = state.conversation_context
            
            # Build product info for Gemini
            product_info = []
            for i, p in enumerate(display_products, 1):
                price_str = f"${p.get('price_value', 0):.2f}" if p.get('price_value') else "Price not available"
                product_info.append(f"{i}. {p.get('title', 'Product')} - {p.get('brand', '')} - {price_str} - {p.get('stars', 0)} stars ({p.get('reviews_count', 0)} reviews)")
            
            relevance_instruction = ""
            if relevance_status == "partially_relevant":
                relevance_instruction = """
IMPORTANT: These products are similar but not exactly what the user asked for.
Acknowledge this and frame them as "similar alternatives" or "related products you might like".
Example: "I found some similar products that might interest you:" or "Here are some related options:"
"""
            
            prompt = f"""
You are a helpful shopping assistant. Generate a natural, conversational response for the user's query.

User's Current Query: "{state.current_query}"
Conversation History: {conversation_context}

Search Results: Found {total_found} products total, showing top {len(display_products)}:
{chr(10).join(product_info)}

{relevance_instruction}

Instructions:
- Be conversational and helpful
- Mention the EXACT number of products being displayed ({len(display_products)})
- Don't mention the total found unless specifically relevant
- If this is a follow-up query (like price filtering), acknowledge the previous context, followup query might be only 1 word like if you previously asked for gender, now user can say 'men' or 'women' or any small query
- Keep response concise but informative (2-3 sentences max)
- Use encouraging language
- Format cleanly with proper spacing

Generate a natural response:"""

            print(f"📤 Sending to Gemini for response generation...")
            
            try:
                gemini_response = self.response_llm.invoke(prompt)
                response_text = gemini_response.content.strip()
                print(f"📥 Gemini Response: {response_text}")
            except Exception as e:
                print(f"❌ Gemini error: {e}")
                response_text = f"Here are {len(display_products)} great products I found for you!"
            
            # Convert to UI format
            ui_products = []
            for p in display_products:
                price_value = p.get("price_value")
                price_str = f"${price_value:.2f}" if isinstance(price_value, (int, float)) and price_value else "See on Amazon"
                
                ui_products.append({
                    "asin": p.get("asin"),
                    "image": p.get("image_url") or p.get("thumbnail_image") or p.get("thumbnailImage") or "",
                    "title": p.get("title") or "Product",
                    "description": p.get("brand") or p.get("category") or "",
                    "rating": float(p.get("stars") or 0),
                    "reviews": int(p.get("reviews_count") or 0),
                    "price": price_str,
                    "url": p.get("url") or "",
                    "similarity_score": p.get("similarity_score", 0),
                    "rerank_score": p.get("rerank_score", 0)
                })
            
            search_results["ui_products"] = ui_products
            search_results["display_products"] = display_products
            
        else:
            # This shouldn't happen as validation should catch it, but just in case
            response_text = "I couldn't find products matching your criteria. Could you try being more specific or using different keywords?"
            search_results["ui_products"] = []
        
        state.search_results = search_results
        state.final_response = response_text
        
        print(f"✅ Response generated successfully")
        print(f"💬 Final Response: {response_text}")
        
        return state
    
    def run_chat(self, message: str, session_id: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the complete chatbot workflow"""
        print(f"\n" + "="*60)
        print(f"🚀 Starting Chat Workflow")
        print(f"📝 Message: '{message}'")
        print(f"💬 Session: {session_id}")
        print(f"="*60)
        
        # Add user message to session memory
        self.session_manager.add_message(session_id, MessageRole.USER, message)
        
        # Get session for context
        session = self.session_manager.get_session(session_id)
        
        # Pre-fetch conversation context once
        conversation_context = self.session_manager.get_conversation_context(session_id, limit=10)
        
        # Initialize state with pre-fetched context
        initial_state = AgentState(
            messages=session.messages,
            current_query=message,
            session_id=session_id,
            user_context={**session.context, **(user_context or {})},
            needs_clarification=False,
            clarification_questions=[],
            conversation_context=conversation_context  # Add to state for reuse
        )
        
        # Run the workflow
        try:
            print("🔄 Running LangGraph workflow...")
            final_state = self.app.invoke(initial_state)
            print("✅ Workflow completed successfully")
        except Exception as e:
            print(f"❌ Workflow error: {e}")
            return {
                "response": "I'm having trouble processing your request. Please try rephrasing your question.",
                "products": [],
                "ui_products": [],
                "needs_clarification": False,
                "clarification_questions": [],
                "search_metadata": {"error": str(e)},
                "session_id": session_id
            }
        
        # Extract results
        def get_from_state(key: str, default=None):
            if isinstance(final_state, dict):
                return final_state.get(key, default)
            return getattr(final_state, key, default)

        search_results = get_from_state("search_results", {}) or {}
        products = search_results.get("products", []) if isinstance(search_results, dict) else []
        ui_products = search_results.get("ui_products") if isinstance(search_results, dict) else None
        
        response_text = get_from_state("final_response", "")
        if response_text:
            self.session_manager.add_message(
                session_id, 
                MessageRole.ASSISTANT, 
                response_text,
                {"products_count": len(ui_products) if ui_products else 0}
            )
        
        result = {
            "response": response_text,
            "products": products,
            "ui_products": ui_products,
            "needs_clarification": bool(get_from_state("needs_clarification", False)),
            "clarification_questions": get_from_state("clarification_questions", []),
            "search_metadata": {
                "total_found": (search_results.get("total_found") if isinstance(search_results, dict) else None),
                "search_query": (search_results.get("search_query") if isinstance(search_results, dict) else None),
                "filters_applied": (search_results.get("filters_applied") if isinstance(search_results, dict) else None),
                "relevance_status": getattr(final_state, 'relevance_status', None) if hasattr(final_state, 'relevance_status') else None,
            },
            "session_id": session_id
        }
        
        print(f"\n📊 FINAL RESULT:")
        print(f"💬 Response: {response_text}")
        print(f"🛍️ Products: {len(ui_products) if ui_products else 0}")
        print(f"📈 Total Found: {search_results.get('total_found', 0) if isinstance(search_results, dict) else 0}")
        print(f"="*60)
        
        return result