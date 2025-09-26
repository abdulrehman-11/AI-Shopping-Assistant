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
        #self.database_tool = DatabaseTool()
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
        """Build workflow with proper routing"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classify_intent", self.classify_intent_node)
        workflow.add_node("handle_off_topic", self.handle_off_topic_node)
        workflow.add_node("handle_vague", self.handle_vague_node)
        workflow.add_node("process_query", self.process_query_node)
        workflow.add_node("search_products", self.search_products_node)
        workflow.add_node("generate_response", self.generate_response_node)
        
        # Set entry point and add conditional edges
        workflow.set_entry_point("classify_intent")
        workflow.add_conditional_edges(
            "classify_intent",
            self.route_after_classification,
            {
                "off_topic": "handle_off_topic",
                "vague": "handle_vague", 
                "specific": "process_query"
            }
        )
        
        # Connect remaining edges
        workflow.add_edge("handle_off_topic", END)
        workflow.add_edge("handle_vague", END)
        workflow.add_edge("process_query", "search_products")
        workflow.add_edge("search_products", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow
    
    def classify_intent_node(self, state: AgentState) -> AgentState:
        """Classify user intent using Gemini"""
        print(f"\n🎯 STEP 0: Classifying Intent")
        print(f"📝 User Query: '{state.current_query}'")
        
        conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=6)
        
        prompt = f"""
Classify this user query for an e-commerce shopping assistant.

Current Query: "{state.current_query}"
Conversation History: {conversation_context}

Classification Rules:
1. OFF_TOPIC: Not related to shopping, products, or e-commerce
   - Examples: "What is China?", "How to cook pasta?", "What's the weather?"
   
2. VAGUE: Shopping intent but missing GENDER (this is the only criteria for vague)
   - Examples: "I want shoes", "looking for clothes", "need electronics"
   - NOTE: Missing brand, size, price, category is OK - only missing gender makes it vague
   
3. SPECIFIC: Clear shopping intent with gender specified OR follow-up to previous specific query
   - Examples: "shoes for men", "women's dress", "nike shoes", "more expensive", "under $100"

Consider conversation context - if user previously specified gender, follow-ups are SPECIFIC.

Return JSON:
{{
    "classification": "OFF_TOPIC|VAGUE|SPECIFIC",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of classification",
    "extracted_info": {{
        "has_gender": true/false,
        "has_category": true/false,
        "is_followup": true/false
    }}
}}
"""

        try:
            print("📤 Sending to Gemini classifier...")
            response = self.classifier_llm.invoke(prompt)
            content = response.content.strip()
            
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(content)
            print(f"📥 Classification Result: {json.dumps(result, indent=2)}")
            
            classification_type = result.get("classification", "SPECIFIC")
            
            query_classification = QueryClassification(
                query_type=QueryType(classification_type.lower()),
                confidence=float(result.get("confidence", 0.8)),
                extracted_info=result.get("extracted_info", {}),
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
    
    def route_after_classification(self, state: AgentState) -> str:
        """Route based on classification"""
        query_type = state.query_classification.query_type.value
        print(f"🚦 Routing to: {query_type}")
        return query_type
    
    def handle_off_topic_node(self, state: AgentState) -> AgentState:
        """Handle off-topic queries"""
        print(f"\n❌ STEP: Handling Off-Topic Query")
        
        prompt = f"""
The user asked an off-topic question: "{state.current_query}"

Generate a polite response that:
1. Acknowledges their question
2. Explains you're a shopping assistant
3. Offers to help with product recommendations
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
    
    def handle_vague_node(self, state: AgentState) -> AgentState:
        """Handle vague queries that need clarification"""
        print(f"\n❓ STEP: Handling Vague Query")
        
        conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=6)
        
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
    
    def process_query_node(self, state: AgentState) -> AgentState:
        """Process specific queries with conversation context"""
        print(f"\n🔍 STEP 1: Processing Specific Query")
        print(f"📝 User Query: '{state.current_query}'")
        
        current_query = state.current_query
        session_id = state.session_id
        
        # Get conversation context
        conversation_context = self.session_manager.get_conversation_context(session_id, limit=10)
        print(f"📚 Conversation Context: {conversation_context}")
        
        # Get user preferences
        user_preferences = self.session_manager.get_user_preferences(session_id)
        print(f"👤 User Preferences: {user_preferences}")
        
        # Build enhanced query with context
        enhanced_query = self._build_contextual_query(current_query, conversation_context, user_preferences)
        print(f"🔍 Enhanced Query: '{enhanced_query}'")
        
        # Process query naturally
        print("🤖 Sending to SimpleProcessor...")
        processed = self.simple_processor.process_query(enhanced_query, conversation_context)
        print(f"📊 SimpleProcessor Result: {json.dumps(processed, indent=2)}")
        
        # Use the enhanced search terms from SimpleProcessor
        final_search_query = processed.get("search_terms", enhanced_query)
        print(f"🎯 Final Search Query: '{final_search_query}'")
        
        # Store results
        state.processed_query = final_search_query  # Use the processed search terms
        state.original_simple_response = processed.get("natural_response", "")
        
        print(f"✅ Query processed successfully")
        print(f"🔍 Will search for: '{final_search_query}'")
        
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
        
        # IMPORTANT: Use processed_query instead of current_query
        search_query = state.processed_query or state.current_query
        print(f"🔍 Search Query: '{search_query}'")
        
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
            query=search_query,  # Use the enhanced search query
            filters=filters,
            top_k=10
        )
        
        print(f"📊 Pinecone found {len(products) if products else 0} products")
        
        # Fallback search if no results
        if not products:
            print("🔄 No results found, trying fallback search...")
            # Try with just the category from context
            conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=6)
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
        
        # Database enhancement
        '''
        if products:
            print("🗃️ Enhancing with database details...")
            asin_list = [p["asin"] for p in products]
            try:
                detailed_products = self.database_tool.get_products_by_ids(asin_list)
                
                # Merge results
                asin_to_vector = {p["asin"]: p for p in products}
                merged = []
                
                for detailed in detailed_products:
                    asin = detailed["asin"]
                    vector_product = asin_to_vector.get(asin)
                    if vector_product:
                        detailed["similarity_score"] = vector_product.get("similarity_score")
                    merged.append(detailed)
                
                # Include any vector-only products
                detailed_asins = {p["asin"] for p in detailed_products}
                for asin, vector_product in asin_to_vector.items():
                    if asin not in detailed_asins:
                        merged.append(vector_product)

                products = merged
            except Exception as e:
                print(f"⚠️ Database enhancement failed: {e}") 
                # Continue with Pinecone results only 
        '''
        if products:   
            products = self.json_fallback.enrich_products(products)
            print(f"🔗 After enhancement: {len(products)} products")
        
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
        
        # Limit to top 3 for display
        display_products = products[:3] if products else []
        
        # Store results
        search_results = {
            "products": products,
            "display_products": display_products,
            "total_found": len(products),
            "search_query": search_query,
            "filters_applied": filters
        }
        
        self.cache_manager.cache_search_results(search_query, search_results, filters)
        
        state.search_results = search_results
        print(f"✅ Search completed: {len(products)} total, showing {len(display_products)}")
        
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
        
        print(f"📊 Total products found: {total_found}")
        print(f"📱 Products to display: {len(products)}")
        
        if products:
            conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=6)
            
            # Build product info for Gemini
            product_info = []
            for i, p in enumerate(products, 1):
                price_str = f"${p.get('price_value', 0):.2f}" if p.get('price_value') else "Price not available"
                product_info.append(f"{i}. {p.get('title', 'Product')} - {p.get('brand', '')} - {price_str} - {p.get('stars', 0)} stars ({p.get('reviews_count', 0)} reviews)")
            
            prompt = f"""
You are a helpful shopping assistant. Generate a natural, conversational response for the user's query.

User's Current Query: "{state.current_query}"
Conversation History: {conversation_context}

Search Results: Found {total_found} products total, showing top {len(products)}:
{chr(10).join(product_info)}

- Once you have the product please compare it with the query and conversation history. If the provided product fully matches the user query then Go with normal answer as below instructions, but if products are different even slightly different you need to answer that you dont have this product but find some similar products.
For example if user ask for "more expensive" and you have only less expensive products or vise versa then you need to answer that you dont have more expensive products but find some similar products. and even do that for products miss matched. 
Instructions:
- Be conversational and helpful
- Mention the EXACT number of products being displayed ({len(products)})
- Don't mention the total found unless specifically relevant
- If this is a follow-up query (like price filtering), acknowledge the previous context
- Keep response concise but informative
- Use encouraging language

- Also if user is asking some general question about product or shopping, You need to answer them as a normal question but not as a product search.
- Find the relevant information from the conversation history and pinecone search result. because pinecone also have description of the product. So it can answer some general question about product.
For eg If someone ask tell me about adidas Men's Daily 3.0 Skate Shoe made of? Pinecone have information in it and says, These men's adidas skate-inspired shoes have all the heritage elements coupled with modern materials and super-soft cushioning. So you need to generate answer of that

Answer in a good format of paragraphing and aligning and keep that consise and to the point.

Generate a natural response:"""

            print(f"📤 Sending to Gemini for response generation...")
            
            try:
                gemini_response = self.response_llm.invoke(prompt)
                response_text = gemini_response.content.strip()
                print(f"📥 Gemini Response: {response_text}")
            except Exception as e:
                print(f"❌ Gemini error: {e}")
                response_text = f"Here are {len(products)} great products I found for you!"
            
            # Convert to UI format
            ui_products = []
            for p in products:
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
                    "similarity_score": p.get("similarity_score", 0)
                })
            
            search_results["ui_products"] = ui_products
            
        else:
            conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=6)
            
            prompt = f"""
The user's query didn't return any products.

User's Query: "{state.current_query}"
Conversation History: {conversation_context}

Generate a helpful response that:
- Acknowledges no products were found
- Suggests alternatives or asks for clarification
- Is encouraging and helpful
- References conversation history if relevant

Response:"""

            try:
                gemini_response = self.response_llm.invoke(prompt)
                response_text = gemini_response.content.strip()
            except Exception as e:
                print(f"❌ Gemini error: {e}")
                response_text = "I couldn't find products matching your criteria. Could you try being more specific?"
        
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
        
        # Initialize state
        initial_state = AgentState(
            messages=session.messages,
            current_query=message,
            session_id=session_id,
            user_context={**session.context, **(user_context or {})},
            needs_clarification=False,
            clarification_questions=[]
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
            },
            "session_id": session_id
        }
        
        print(f"\n📊 FINAL RESULT:")
        print(f"💬 Response: {response_text}")
        print(f"🛍️ Products: {len(ui_products) if ui_products else 0}")
        print(f"📈 Total Found: {search_results.get('total_found', 0)}")
        print(f"="*60)
        
        return result