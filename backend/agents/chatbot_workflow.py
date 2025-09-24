from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from models.schemas import AgentState, ConversationMessage, MessageRole
from agents.query_classifier import QueryClassifierAgent
from tools.pinecone_tool import PineconeTool
from tools.database_tool import DatabaseTool
from tools.session_manager import SessionManager
from tools.json_fallback import JsonFallbackTool
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config

class ChatbotWorkflow:
    def __init__(self):
        self.query_classifier = QueryClassifierAgent()
        self.pinecone_tool = PineconeTool()
        self.database_tool = DatabaseTool()
        self.session_manager = SessionManager(Config.REDIS_URL)
        self.json_fallback = JsonFallbackTool()
        self.rerank_llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.2
        )
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes (agents)
        workflow.add_node("classify_query", self.classify_query_node)
        workflow.add_node("handle_vague_query", self.handle_vague_query_node)
        workflow.add_node("search_products", self.search_products_node)
        workflow.add_node("generate_response", self.generate_response_node)
        
        # Define the flow
        workflow.set_entry_point("classify_query")
        
        # Conditional routing based on query type
        workflow.add_conditional_edges(
            "classify_query",
            self.route_after_classification,
            {
                "vague": "handle_vague_query",
                "specific": "search_products",
                "clarification": "search_products"
            }
        )
        
        workflow.add_edge("handle_vague_query", "generate_response")
        workflow.add_edge("search_products", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow
    
    def classify_query_node(self, state: AgentState) -> AgentState:
        """Classify the user's query"""
        current_query = state.current_query
        session_id = state.session_id
        
        # Get conversation context for better classification
        conversation_context = self.session_manager.get_conversation_context(session_id)
        enhanced_context = state.user_context.copy()
        enhanced_context["conversation_history"] = conversation_context
        
        # Classify the query with conversation context
        classification = self.query_classifier.classify_query(current_query, enhanced_context)
        
        state.query_classification = classification
        
        return state
    
    def route_after_classification(self, state: AgentState) -> str:
        """Route to appropriate handler based on classification"""
        query_type = state.query_classification.query_type
        extracted = state.query_classification.extracted_info or {}
        
        # If we have enough signals (e.g., category detected), proceed to search
        if extracted.get("category") or extracted.get("brand") or extracted.get("gender"):
            return "specific"
        
        if query_type.value == "vague":
            return "vague"
        elif query_type.value in ["specific", "clarification"]:
            return "specific"
        else:
            return "vague"  # Default fallback
    
    def handle_vague_query_node(self, state: AgentState) -> AgentState:
        """Handle vague queries by asking clarification questions"""
        classification = state.query_classification
        missing_info = classification.missing_info
        
        questions = []
        
        # Generate clarification questions
        if "gender" in missing_info:
            questions.append("Are you looking for men's or women's products?")
        
        if "category" in missing_info or "specific_category" in missing_info:
            extracted_category = classification.extracted_info.get("category")
            if extracted_category:
                questions.append(f"What specific type of {extracted_category} are you looking for?")
            else:
                questions.append("What specific product category are you interested in?")
        
        # Ensure we always return at least one helpful question
        if not questions:
            questions.append("Could you share details like category, brand, size, and budget?")
        
        state.needs_clarification = True
        state.clarification_questions = questions
        
        return state
    
    def search_products_node(self, state: AgentState) -> AgentState:
        """Search for products based on the query"""
        classification = state.query_classification
        
        # Build search query
        search_terms = []
        filters = {}
        
        # Add extracted information to search
        extracted = classification.extracted_info
        
        if extracted.get("gender"):
            search_terms.append(extracted["gender"])
        
        if extracted.get("category"):
            search_terms.append(extracted["category"])
            filters["category"] = extracted["category"]
        
        if extracted.get("brand"):
            search_terms.append(extracted["brand"])
            filters["brand"] = extracted["brand"]
        
        # Add original query
        search_terms.append(state.current_query)
        
        search_query = " ".join(search_terms)
        
        # Search in Pinecone
        products = self.pinecone_tool.search_similar_products(
            query=search_query,
            filters=filters,
            top_k=5
        )
        try:
            print(f"[search_products_node] query='{search_query}', filters={filters}, found={len(products) if products else 0}")
        except Exception:
            pass

        # Fallback: if no results, retry with raw query and no filters
        if not products:
            fallback_query = state.current_query
            products = self.pinecone_tool.search_similar_products(
                query=fallback_query,
                filters={},
                top_k=5
            )
            try:
                print(f"[search_products_node] fallback query='{fallback_query}', found={len(products) if products else 0}")
            except Exception:
                pass
        
        # Get full product details from database if needed
        if products:
            asin_list = [p["asin"] for p in products]
            detailed_products = self.database_tool.get_products_by_ids(asin_list)

            # Build lookup for vector products
            asin_to_vector = {p["asin"]: p for p in products}

            merged: List[Dict[str, Any]] = []
            # Add detailed rows when available, merging similarity score
            for detailed in detailed_products:
                asin = detailed["asin"]
                vector_product = asin_to_vector.get(asin)
                if vector_product:
                    detailed["similarity_score"] = vector_product.get("similarity_score")
                merged.append(detailed)

            # Include any vector-only products that weren't found in DB
            detailed_asins = {p["asin"] for p in detailed_products}
            for asin, vector_product in asin_to_vector.items():
                if asin not in detailed_asins:
                    merged.append(vector_product)

            products = merged
            
            # ASIN FALLBACK: Enrich with JSON data where information is missing
            products = self.json_fallback.enrich_products(products)
        
        # Store as dict instead of Pydantic model for now
        state.search_results = {
            "products": products,
            "total_found": len(products),
            "search_query": search_query,
            "filters_applied": filters
        }
        
        return state
    
    def generate_response_node(self, state: AgentState) -> AgentState:
        """Generate the final response"""
        if state.needs_clarification:
            # Return clarification questions
            response = "I'd like to help you find the perfect products! "
            response += " ".join(state.clarification_questions)
            state.final_response = response
        else:
            # Generate response with products and LLM reranking for top 3 distinct items
            total_found = state.search_results.get("total_found", 0) if state.search_results else 0
            products = (state.search_results.get("products") if state.search_results else []) or []

            if products:
                # Prepare concise product list for reranking
                condensed = []
                for p in products:
                    condensed.append({
                        "asin": p.get("asin"),
                        "title": p.get("title"),
                        "brand": p.get("brand"),
                        "category": p.get("category"),
                        "stars": p.get("stars"),
                        "reviews_count": p.get("reviews_count"),
                        "price_value": p.get("price_value"),
                        "similarity_score": p.get("similarity_score")
                    })

                # Try to infer the primary category to help filtering (from extracted info or majority of results)
                primary_category = None
                try:
                    extracted = (state.query_classification.extracted_info if state.query_classification else {}) or {}
                    if extracted.get("category"):
                        primary_category = str(extracted.get("category")).strip().lower()
                    if not primary_category and condensed:
                        from collections import Counter
                        cats = [str(c.get("category") or "").strip().lower() for c in condensed if c.get("category")]
                        if cats:
                            primary_category = Counter(cats).most_common(1)[0][0]
                except Exception:
                    primary_category = None

                prompt = (
                    "You are selecting the best 3 distinct products for a user.\n"
                    "Rules:\n"
                    "- Select at most 3 items.\n"
                    "- Prefer higher stars and more reviews; use similarity_score to break ties.\n"
                    "- Remove near-duplicates (same model with minor variations like color, pack size, version).\n"
                    "- Exclude items irrelevant to the main category (e.g., socks for shoes queries).\n"
                    "- If a primary category is provided, only choose items whose category contains it (case-insensitive).\n"
                    "Output STRICT JSON only, with key 'selected' as a list of up to 3 items; each item must have: asin, title, brand, category, stars, reviews_count, price_value. No extra keys, no explanations.\n\n"
                    f"Primary category (may be null): {primary_category}\n"
                    f"User query: {state.current_query}\n"
                    f"Products: {condensed}\n"
                )

                try:
                    llm_res = self.rerank_llm.invoke(prompt)
                    content = llm_res.content.strip()
                    if content.startswith('```json'):
                        content = content.replace('```json', '').replace('```', '')
                    import json
                    parsed = json.loads(content)
                    selected = parsed.get("selected", [])

                    # Map to UI schema for frontend consumption
                    ui_products = []
                    for s in selected[:3]:
                        title = s.get("title") or "Product"
                        price_value = s.get("price_value")
                        price_str = (f"${price_value:.2f}" if isinstance(price_value, (int, float)) and price_value else "See on Amazon")
                        
                        # Use enriched data from JSON fallback
                        image_url = (s.get("image_url") or s.get("thumbnail_image") or 
                                   s.get("thumbnailImage") or "")
                        
                        ui_products.append({
                            "asin": s.get("asin"),
                            "image": image_url,
                            "title": title,
                            "description": s.get("brand") or s.get("category") or "",
                            "rating": float(s.get("stars") or 0),
                            "reviews": int(s.get("reviews_count") or 0),
                            "price": price_str,
                            "url": s.get("url") or "",  # Amazon URL from JSON
                            "similarity_score": s.get("similarity_score", 0)
                        })

                    state.search_results["ui_products"] = ui_products
                    # Record count of picks for metadata consumers
                    state.search_results["top_picks_count"] = len(ui_products)
                    response = f"I found {total_found} great products for you! Here are my top 3 picks."
                except Exception:
                    response = f"I found {total_found} great products for you!"
            else:
                response = "I couldn't find any products matching your criteria. Could you try being more specific?"

            state.final_response = response
        
        return state
    
    def run_chat(self, message: str, session_id: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the complete chatbot workflow"""
        
        # Add user message to session memory
        self.session_manager.add_message(session_id, MessageRole.USER, message)
        
        # Get session for context
        session = self.session_manager.get_session(session_id)
        
        # Initialize state with session context
        initial_state = AgentState(
            messages=session.messages,
            current_query=message,
            session_id=session_id,
            user_context={**session.context, **(user_context or {})},
            needs_clarification=False,
            clarification_questions=[]
        )
        
        # Run the workflow
        final_state = self.app.invoke(initial_state)
        
        # Support both dict-based and attribute-based state
        def get_from_state(key: str, default=None):
            if isinstance(final_state, dict):
                return final_state.get(key, default)
            return getattr(final_state, key, default)

        search_results = get_from_state("search_results", {}) or {}
        products = []
        if isinstance(search_results, dict):
            products = search_results.get("products", [])
        ui_products = search_results.get("ui_products") if isinstance(search_results, dict) else None
        
        # Add assistant response to session memory
        response_text = get_from_state("final_response", "")
        if response_text:
            self.session_manager.add_message(
                session_id, 
                MessageRole.ASSISTANT, 
                response_text,
                {"products_count": len(products) if products else 0}
            )
        
        return {
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