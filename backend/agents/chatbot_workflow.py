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
        print("ðŸ”§ Initializing ChatbotWorkflow...")
        
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
        print("âœ… All tools initialized successfully")
    
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
        # New categories-related nodes
        workflow.add_node("show_categories", self.show_categories_node)
        workflow.add_node("category_info", self.category_info_node)
        
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
                "specific": "process_query",
                "categories": "show_categories",
                "category_info": "category_info"
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
        # Ensure categories flows terminate the workflow
        workflow.add_edge("show_categories", END)
        workflow.add_edge("category_info", END)
        
        return workflow
    
    def classify_intent_node(self, state: AgentState) -> AgentState:
        """Enhanced classification with inventory check and question detection"""
        print(f"\nðŸŽ¯ STEP 0: Classifying Intent")
        print(f"ðŸ“ User Query: '{state.current_query}'")
        
        # Get context once and store in state for reuse
        if not hasattr(state, 'conversation_context') or not state.conversation_context:
            state.conversation_context = self.session_manager.get_conversation_context(state.session_id, limit=10)
        
        conversation_context = state.conversation_context
        # Read simple preferences derived from entire session history
        user_prefs = self.session_manager.get_user_preferences(state.session_id)
        
        # Heuristic: detect explicit category listing questions early (before LLM)
        ql = (state.current_query or "").lower().strip()
        categories_triggers = [
            "what categories",
            "which categories",
            "show categories",
            "list categories",
            "do you have categories",
            "what kind of categories",
            "all categories"
        ]
        if any(t in ql for t in categories_triggers) or ("category" in ql and ("what" in ql or "which" in ql)):
            state.query_classification = QueryClassification(
                query_type=QueryType("categories"),
                confidence=0.95,
                extracted_info={},
                missing_info=[]
            )
            return state

        # Heuristic: detect category info questions like "what products you have in clothes/clothing"
        if re.search(r"what\s+(products|do you have|items).*(in|for)\s+(cloths|clothes|clothing|shirts|shoes|bags|jewelry|jewellery|nike)", ql):
            # Extract rough category word for downstream node
            m = re.search(r"(cloths|clothes|clothing|shirts|shoes|bags|jewelry|jewellery|nike)", ql)
            if m:
                state.requested_category = m.group(1)
            state.query_classification = QueryClassification(
                query_type=QueryType("category_info"),
                confidence=0.9,
                extracted_info={"category": getattr(state, 'requested_category', '')},
                missing_info=[]
            )
            return state

        # Heuristic: if user mentions a category but not gender, and we have gender in preferences, treat as SPECIFIC
        category_terms = ["shirts", "shirt", "clothing", "cloths", "clothes", "shoes", "bags", "jewelry", "jewellery", "nike"]
        mentioned_category = next((t for t in category_terms if t in ql), None)
        if mentioned_category and user_prefs.get("gender"):
            # Normalize gender and category
            gender_word = "men" if user_prefs["gender"] == "male" else ("women" if user_prefs["gender"] == "female" else "unisex")
            norm_map = {"cloths": "clothing", "clothes": "clothing"}
            category_norm = norm_map.get(mentioned_category, mentioned_category)
            state.query_classification = QueryClassification(
                query_type=QueryType("specific"),
                confidence=0.92,
                extracted_info={"category": category_norm, "has_gender": True, "gender": gender_word},
                missing_info=[]
            )
            return state

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
    
    3. VAGUE: Shopping/buying intent but missing critical info (GENDER for clothing/shoes/accessories): Gender means men/women/unisex and relevant keywords are also considered as gender, So if these keywords available in query then it is not vague but if not then it is vague. But make sure, Not every query need to be gendered.
       - Examples: "I want shoes", "looking for clothes", "need a watch"
       - NOTE: Missing brand, size, price is OK - only missing gender makes it vague
       - NOTE: Also note that not everything need to be gendered - e.g. "I want a laptop", "I want to buy something for my wife", This is also gendered query. Because wife is female etc So understand these query as SPECIFIC not VAGUE, Understand the query on your own and decide either it neeed to be gendered or not
       - IMPORTANT: Extract category to check inventory
       - Uncommon categories: jewellery, perfume, watches, accessories (for brands not typically associated with them)
    
    4. SPECIFIC: Clear shopping intent with sufficient details OR follow-up to previous specific query
       - Examples: "shoes for men", "women's dress", "nike shoes", "more expensive", "under $100", "dress for unisex" or even just 'men or women'
       - Follow-ups are SPECIFIC if previous context has gender 
       - IMPORTANT: If user says "No [X], I want [Y]", classify as SPECIFIC and extract [Y] as the actual query
       - Example: "No laptop bags, I want laptops" -> SPECIFIC, extract "laptops"
    Consider conversation context - if user previously specified gender, follow-ups are SPECIFIC.
    Note: Make sure you process query by considering spelling mistakes, becuase sometimes there is a spelling mistake that you need to understand & correct 
    
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
            print("ðŸ”¤ Sending to Gemini classifier...")
            response = self.classifier_llm.invoke(prompt)
            content = response.content.strip()
            
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            result = json.loads(content)
            print(f"ðŸ“¥ Classification Result: {json.dumps(result, indent=2)}")
            
            classification_type = result.get("classification", "SPECIFIC")
            extracted_info = result.get("extracted_info", {})
            
            # Quick inventory check for VAGUE queries
            if classification_type == "VAGUE":
                category = extracted_info.get("category", "")
                if category:
                    print(f"ðŸ” Checking inventory for category: {category}")
                    inventory_check = self._quick_inventory_check(category)
                    
                    if not inventory_check:
                        print(f"âŒ Category '{category}' not available in inventory")
                        classification_type = "UNAVAILABLE"
                        state.unavailable_category = category
                    else:
                        print(f"âœ… Category '{category}' found in inventory")
                # If we already know gender from preferences, upgrade to SPECIFIC
                if user_prefs.get("gender"):
                    print("âœ… Using session gender to upgrade VAGUE -> SPECIFIC")
                    classification_type = "SPECIFIC"
                    extracted_info["has_gender"] = True
                    extracted_info["gender"] = "men" if user_prefs["gender"] == "male" else ("women" if user_prefs["gender"] == "female" else "unisex")
            
            query_classification = QueryClassification(
                query_type=QueryType(classification_type.lower()),
                confidence=float(result.get("confidence", 0.8)),
                extracted_info=extracted_info,
                missing_info=["gender"] if classification_type == "VAGUE" else []
            )
            
            state.query_classification = query_classification
            print(f"âœ… Intent classified as: {classification_type}")
            
        except Exception as e:
            print(f"âŒ Classification error: {e}")
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
            # Handle spelling variations and compound terms
            category_lower = category.lower()

            # Common spelling variations
            spelling_variations = {
                'jewellery': ['jewelry', 'jewellery', 'jewellry', 'jewelery'],
                'jewelry': ['jewelry', 'jewellery', 'jewellry', 'jewelery'],
                'dress shoes': ['dress shoes', 'formal shoes', 'oxford', 'loafers', 'shoes'],
                'tshirt': ['tshirt', 't-shirt', 'tee', 'shirt'],
                'unisex': ['unisex', 'men women', 'both genders']
            }

            # Get variations to search
            search_terms = spelling_variations.get(category_lower, [category_lower])
            if category_lower not in search_terms:
                search_terms.append(category_lower)

            # Also add partial matches for compound terms
            if ' ' in category_lower:
                # For "dress shoes", also search "shoes"
                parts = category_lower.split()
                search_terms.extend(parts)

            # Search with multiple variations
            for search_term in search_terms:
                products = self.pinecone_tool.search_similar_products(
                    query=search_term,
                    filters=None,
                    top_k=10  # Get more to verify
                )

                if products and len(products) > 0:
                    # More lenient matching - check if any product is relevant
                    for p in products:
                        title = (p.get('title', '') or '').lower()
                        cat = (p.get('category', '') or '').lower()

                        # Check for any of the search variations
                        for variant in search_terms:
                            if variant in title or variant in cat:
                                return True

                        # High similarity score means it's probably relevant
                        if p.get('similarity_score', 0) > 0.65:  # Lower threshold
                            return True

            return False

        except Exception as e:
            print(f"âš ï¸ Inventory check error: {e}")
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
        
        # Standard routing: return a route key that matches the conditional edge keys
        valid_routes = {"off_topic", "vague", "specific", "product_question", "unavailable", "categories", "category_info"}
        route_key = classification if classification in valid_routes else "specific"
        print(f"ðŸš¦ Routing to: {route_key}")
        return route_key
    
    def handle_off_topic_node(self, state: AgentState) -> AgentState:
        """Handle off-topic queries"""
        print(f"\nâŒ STEP: Handling Off-Topic Query")
        
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
            print(f"âŒ Error generating off-topic response: {e}")
            state.final_response = "I'm a shopping assistant here to help you find great products. What would you like to shop for today?"
        
        print(f"ðŸ’¬ Off-topic Response: {state.final_response}")
        return state

    def show_categories_node(self, state: AgentState) -> AgentState:
        """Return a conversational list of available categories with follow-ups."""
        print("\nðŸ“š STEP: Showing Categories")
        categories = [
            {"slug": "men-bags", "name": "Men's Bags", "desc": "Premium bags, briefcases, and backpacks"},
            {"slug": "men-jewelry", "name": "Men's Jewelry", "desc": "Elegant watches, rings, and accessories"},
            {"slug": "men-shoes", "name": "Men's Shoes", "desc": "From casual sneakers to formal dress shoes"},
            {"slug": "men-clothing", "name": "Men's Clothing", "desc": "Stylish apparel for every occasion"},
            {"slug": "nike-shoes", "name": "Nike Shoes", "desc": "Iconic sneakers and athletic footwear"},
            {"slug": "women-clothing", "name": "Women's Clothing", "desc": "Fashion-forward clothing for women"}
        ]

        # Build friendly message
        lines = ["Here are the categories I can help you with right now:"]
        for c in categories:
            lines.append(f"- {c['name']}: {c['desc']}")

        followups = [
            "Suggest men shoes",
            "Show women's clothing",
            "Find men's bags",
            "Suggest Nike running shoes",
            "Show men clothing under $50"
        ]
        lines.append("")
        lines.append("You can try these follow-ups:")
        for f in followups:
            lines.append(f"- {f}")

        state.final_response = "\n".join(lines)
        # Ensure no products are attached for this conversational turn
        state.search_results = {"products": [], "display_products": [], "ui_products": [], "total_found": 0}
        return state

    def category_info_node(self, state: AgentState) -> AgentState:
        """Summarize what's available within a category without listing products."""
        print("\nðŸ—‚ï¸ STEP: Category Info Summary")
        raw_cat = getattr(state, 'requested_category', '') or state.query_classification.extracted_info.get('category', '')
        cat_map = {
            "cloths": "clothing",
            "clothes": "clothing",
            "clothing": "clothing",
            "jewellery": "jewelry",
            "jewelry": "jewelry",
            "bags": "bags",
            "shoes": "shoes",
            "nike": "nike shoes"
        }
        norm_cat = cat_map.get((raw_cat or '').lower(), raw_cat or 'clothing')

        try:
            products = self.pinecone_tool.search_similar_products(
                query=norm_cat,
                filters={},
                top_k=20
            ) or []

            titles = [(p.get('title') or '') for p in products if p]
            brands = [(p.get('brand') or '') for p in products if p]
            # Simple frequency counts
            from collections import Counter
            brand_counts = Counter([b for b in brands if b])

            # Extract common types by simple keyword scan in titles
            keywords = [
                'sneaker','running','casual','dress','hoodie','t-shirt','shirt','jeans','bag','backpack','watch','ring'
            ]
            kw_counts = Counter()
            for t in titles:
                tl = t.lower()
                for kw in keywords:
                    if kw in tl:
                        kw_counts[kw] += 1

            top_brands = ", ".join([b for b,_ in brand_counts.most_common(5)]) or "various brands"
            top_types = ", ".join([k for k,_ in kw_counts.most_common(5)]) or "multiple styles"

            followups = [
                f"Suggest {('men ' + norm_cat) if 'shoe' in norm_cat or 'clothing' in norm_cat else norm_cat}",
                f"Show {norm_cat} under $50",
                f"Find top-rated {norm_cat}",
                f"Show popular {norm_cat} brands"
            ]

            state.final_response = (
                f"In {norm_cat.title()}, we have a variety of options across {top_brands}."
                f" Popular types include {top_types}.\n\n"
                "Tell me which gender (men/women) or budget you prefer, and I'll narrow it down.\n"
                "You can try: " + "; ".join(followups)
            )
            state.search_results = {"products": [], "display_products": [], "ui_products": [], "total_found": 0}
        except Exception as e:
            print(f"âš ï¸ Category info error: {e}")
            state.final_response = (
                f"I can help you explore {norm_cat}. Do you want men or women, and any budget or brand?"
            )
            state.search_results = {"products": [], "display_products": [], "ui_products": [], "total_found": 0}

        return state
    
    def handle_unavailable_category_node(self, state: AgentState) -> AgentState:
        """Handle queries for unavailable categories"""
        print(f"\nðŸš« STEP: Handling Unavailable Category")
        
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
            print(f"âŒ Error: {e}")
            state.final_response = f"I apologize, but we don't currently have {category} available. Can I help you find something else?"
        
        print(f"ðŸ’¬ Unavailable Response: {state.final_response}")
        return state
    
    def handle_vague_node(self, state: AgentState) -> AgentState:
        """Handle vague queries that need clarification"""
        print(f"\nâ“ STEP: Handling Vague Query")
        
        conversation_context = state.conversation_context
        
        prompt = f"""
User has shopping intent but didn't specify gender: (Gender means men/women/unisex and relevant keywords like boy/girl or other relvant etc are also considered as gender, So if these keywords available in query then it is not vague but if not then it is vague. But make sure, Not every query need to be gendered.) "{state.current_query}"
Conversation History: {conversation_context}

Generate a helpful response that:
1. Acknowledges their interest
2. Asks specifically about gender (men/women)
3. Can suggest popular options
4. Be encouraging and specific to their query

Examples:
- For "I want shoes": "I'd love to help you find the perfect shoes! Are you looking for shoes for men, women Once I know that, I can show you some great options."
- For "need a watch": "Great choice! Watches make excellent purchases. Are you shopping for a men's watch, women's watch, or perhaps for a child? Let me know and I'll find some perfect options for you."

Generate a specific response for their query:"""

        try:
            response = self.response_llm.invoke(prompt)
            state.final_response = response.content.strip()
            state.needs_clarification = True
        except Exception as e:
            print(f"âŒ Error generating vague response: {e}")
            state.final_response = "I'd be happy to help you find what you're looking for! Could you let me know if you're shopping for men, women?"
            state.needs_clarification = True
        
        print(f"ðŸ’¬ Vague Query Response: {state.final_response}")
        return state
    
    def answer_product_question_node(self, state: AgentState) -> AgentState:
        """Handle specific product questions (price, features, availability)"""
        print(f"\nâ“ STEP: Answering Product Question")
        
        # First, handle comparative/"these" follow-ups based on last shown products from session memory
        try:
            q_lower = (state.current_query or "").lower()
            comparative_triggers = ["why both", "both same", "these", "them", "those", "same product", "difference", "different", "are these"]
            has_comparative = any(t in q_lower for t in comparative_triggers)
            last_display = self.session_manager.get_context_value(state.session_id, "last_display_products", [])
            if has_comparative and isinstance(last_display, list) and len(last_display) >= 2:
                # Build brief comparison using the last two shown products
                p1 = last_display[0]
                p2 = last_display[1]
                title1 = p1.get("title", "Product A")
                title2 = p2.get("title", "Product B")
                brand1 = p1.get("brand", "")
                brand2 = p2.get("brand", "")
                price1 = p1.get("price_value")
                price2 = p2.get("price_value")
                rating1 = p1.get("stars")
                rating2 = p2.get("stars")

                prompt = f"""
The user asked a follow-up about recently shown products: "{state.current_query}"

Compare these two products briefly and explain if they are duplicates/variants or how they differ. Be concise (2 sentences max).

Product A: title="{title1}", brand="{brand1}", price_value={price1}, rating={rating1}
Product B: title="{title2}", brand="{brand2}", price_value={price2}, rating={rating2}

Rules:
- If titles are identical or nearly identical and brands match, explain they are the same model or variants (e.g., different sizes/colors/ASINs).
- Otherwise, point out a clear difference (brand, model, features) to answer the question.
"""
                try:
                    resp = self.response_llm.invoke(prompt)
                    state.final_response = resp.content.strip()
                except Exception:
                    if title1 == title2 and brand1 == brand2:
                        state.final_response = "These appear to be the same model, likely listed as separate variants (size/color) with different ASINs."
                    else:
                        state.final_response = "They are different itemsâ€”compare the brand/model details to pick the one you prefer."

                # Do not attach products again in this explanation-only path
                state.search_results = {"products": [], "display_products": [], "ui_products": [], "total_found": 0}
                print(f"ðŸ’¬ Comparative Answer: {state.final_response}")
                return state
        except Exception as e:
            print(f"âš ï¸ Comparative handling failed: {e}")

        extracted_info = state.query_classification.extracted_info
        product_name = extracted_info.get("product_name", "")
        brand = extracted_info.get("brand", "")
        
        # Build search query for the specific product
        search_query = f"{brand} {product_name}".strip() if brand else product_name
        if not search_query:
            search_query = state.current_query
        
        print(f"ðŸ” Searching for product: {search_query}")
        
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
            print(f"âŒ Product question error: {e}")
            state.final_response = "I'm having trouble finding that product information. Could you try rephrasing your question?"
            state.search_results = {"products": [], "ui_products": [], "total_found": 0}
        
        print(f"ðŸ’¬ Answer: {state.final_response}")
        return state
    
    def process_query_node(self, state: AgentState) -> AgentState:
        """Process specific queries with conversation context"""
        print(f"\nðŸ” STEP 1: Processing Specific Query")
        print(f"ðŸ“ User Query: '{state.current_query}'")
        
        current_query = state.current_query
        session_id = state.session_id
        
        # Reuse context from state
        conversation_context = state.conversation_context
        print(f"ðŸ“š Using Cached Context")
        
        # Get user preferences
        user_preferences = self.session_manager.get_user_preferences(session_id)
        # Inject last known contextual values from session for better follow-ups
        try:
            user_preferences['last_search_query'] = self.session_manager.get_context_value(session_id, 'last_search_query')
            user_preferences['last_display_products'] = self.session_manager.get_context_value(session_id, 'last_display_products', [])
        except Exception:
            pass
        print(f"ðŸ‘¤ User Preferences: {user_preferences}")

        # Track what we're currently discussing
        if hasattr(state, 'search_results') and state.search_results:
            last_products = state.search_results.get('display_products', [])
            if last_products:
                # Store the category/type of last shown products
                last_category = last_products[0].get('category', '')
                user_preferences['last_shown_category'] = last_category
                user_preferences['last_shown_products'] = [p.get('title', '') for p in last_products[:3]]
        
        # Build enhanced query with context
        enhanced_query = self._build_contextual_query(current_query, conversation_context, user_preferences)
        print(f"ðŸ”Ž Enhanced Query: '{enhanced_query}'")
        
        # Process query naturally
        print("ðŸ¤– Sending to SimpleProcessor...")
        processed = self.simple_processor.process_query(enhanced_query, conversation_context)
        print(f"ðŸ“Š SimpleProcessor Result: {json.dumps(processed, indent=2)}")
        
        # Use the enhanced search terms from SimpleProcessor
        final_search_query = processed.get("search_terms", enhanced_query)
        print(f"ðŸŽ¯ Final Search Query: '{final_search_query}'")
        
        # Store results
        state.processed_query = final_search_query
        state.original_simple_response = processed.get("natural_response", "")
        
        print(f"âœ… Query processed successfully")
        print(f"ðŸ”Ž Will search for: '{final_search_query}'")
        
        return state
    
    def _build_contextual_query(self, current_query: str, context: str, preferences: Dict) -> str:
        """Build enhanced query with conversation context"""
    
        current_lower = current_query.lower()
        last_search_query = (preferences or {}).get('last_search_query') or ''
        last_display_products = (preferences or {}).get('last_display_products') or []
       
        # Check for negation patterns (no, not, don't want, etc.)
        negation_patterns = [r'\bno\b', r'\bnot\b', r"don't want", r"don't need", r"instead"]
        has_negation = any(re.search(pattern, current_lower) for pattern in negation_patterns)
       
        # If user is negating or correcting, prioritize current query
        if has_negation:
            # Extract what they DO want after negation
            if 'want' in current_lower:
                parts = current_lower.split('want')
                if len(parts) > 1:
                    return parts[-1].strip()
            elif 'need' in current_lower:
                parts = current_lower.split('need')
                if len(parts) > 1:
                    return parts[-1].strip()
            return current_query  # Use query as-is for negations
       
        # Detect 'more/another' style follow-ups referencing prior search
        more_patterns = [r'\bmore\b', r'\banother\b', r'\b2 more\b', r'\btwo more\b', r'\bshow more\b', r'\bsuggest\b']
        if any(re.search(p, current_lower) for p in more_patterns) and last_search_query:
            # Keep the previous search terms, optionally adjust count but search query stays category-based
            return last_search_query
        # But if asking for "X more", we need to exclude previously shown products
        if re.search(r'\d+\s+more', current_lower):
            # Mark that we need different products
            preferences['exclude_asins'] = [p.get('asin') for p in last_display_products if p.get('asin')]
        
        # For normal follow-ups, enhance with context
        is_followup = len(current_query.split()) <= 3  # Short queries are likely follow-ups
       
        if is_followup and context and "No previous conversation" not in context:
            prev_category = preferences.get('categories', [])
            prev_brands = preferences.get('brands', [])
            prev_gender = preferences.get('gender', '')
           
            # Build contextual query
            enhanced_parts = []
           
            # Check if current query is just gender
            if current_lower in ['men', 'women', 'unisex']:
                if prev_category:
                    return f"{prev_category[0]} for {current_lower}"
           
            # Check if it's a category change
            category_keywords = ['shoes', 'cloths', 'clothes', 'shirts', 'pants', 'bags', 'watches']
            if any(keyword in current_lower for keyword in category_keywords):
                if prev_gender:
                    return f"{current_query} for {prev_gender}"
           
            # Default enhancement
            if prev_brands and not any(brand.lower() in current_lower for brand in prev_brands):
                enhanced_parts.append(prev_brands[0])
            if prev_gender and prev_gender not in current_lower:
                enhanced_parts.append(f"for {prev_gender}")
            enhanced_parts.append(current_query)
           
            return " ".join(enhanced_parts)
       
        return current_query
    
    def search_products_node(self, state: AgentState) -> AgentState:
        """Search for products with proper query usage"""
        print(f"\nðŸ” STEP 2: Searching Products")
        
        # Use processed_query instead of current_query
        search_query = state.processed_query or state.current_query
        print(f"ðŸ”Ž Search Query: '{search_query}'")
        
        # Check cache first
        cached_results = self.cache_manager.get_cached_search(search_query)
        if cached_results:
            print("ðŸ“¦ Using cached results")
            state.search_results = cached_results
            return state
        
        # Extract price filters from search query
        price_filters = self._extract_price_filters(search_query)
        print(f"ðŸ’° Price Filters: {price_filters}")

        min_rating = self._extract_rating_filter(search_query)
        if min_rating > 0:
            print(f"â­ Minimum Rating Filter: {min_rating}")
        
        # Build filters
        filters = {}
        if price_filters:
            filters.update(price_filters)
            
        print(f"ðŸ”§ Search Filters: {filters}")
        
        # Search in Pinecone with proper query
        print("🔍 Searching in Pinecone...")
        products = self.pinecone_tool.search_similar_products(
            query=search_query,
            filters=filters,
            top_k=25  # Get more to allow exclusions
        )

        # Exclude previously shown products if this is a "more" request
        user_preferences = self.session_manager.get_user_preferences(state.session_id)
        exclude_asins = user_preferences.get('exclude_asins', [])
        if exclude_asins and products:
            original_count = len(products)
            products = [p for p in products if p.get('asin') not in exclude_asins]
            print(f"🔄 Excluded {original_count - len(products)} previously shown products")
        
        print(f"ðŸ“Š Pinecone found {len(products) if products else 0} products")
        
        # Fallback search if no results
        if not products:
            print("ðŸ”„ No results found, trying fallback search...")
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
                    print(f"ðŸ“Š Fallback search '{fallback_query}' found {len(products)} products")
                    break
        
        if products:   
            products = self.json_fallback.enrich_products(products)
            print(f"ðŸ”— After enrichment: {len(products)} products")
        
        # Cohere Rerank
        if products and len(products) > 1:
            try:
                print("ðŸŽ¯ Reranking with Cohere...")
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
                print(f"ðŸŽ¯ Reranked to {len(products)} products")
                
            except Exception as e:
                print(f"âŒ Reranking failed: {e}")

        # ✅ Apply strict filtering
        products = self._apply_strict_filters(products, search_query)
        print(f"📋 After strict filtering: {len(products)} products")
        
        
        # Apply post-search price filtering
        if price_filters and products:
            products = self._apply_price_filters(products, price_filters)
            print(f"ðŸ’° After price filtering: {len(products)} products")
        # Apply rating filter
        if min_rating > 0 and products:
            products = [p for p in products if float(p.get('stars', 0)) >= min_rating]
            print(f"â­ After rating filtering: {len(products)} products")
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
        # Ensure last shown products are accessible for validation
        if display_products:
            state.last_shown_products = [p.get('title', '') for p in display_products]
        
        self.cache_manager.cache_search_results(search_query, search_results, filters)

        # Store rating filter info
        if min_rating > 0:
            search_results["rating_filter"] = min_rating
        
        state.search_results = search_results
        print(f"âœ… Search completed: {len(products)} total, validating top {len(display_products)}")
        
        # Persist last search context for future follow-ups
        try:
            self.session_manager.update_context(state.session_id, 'last_search_query', search_query)
            self.session_manager.update_context(state.session_id, 'last_display_products', display_products)
            # Also provide quick access on state for validators
            state.last_shown_products = [p.get('title', '') for p in display_products]
        except Exception as e:
            print(f"âš ï¸ Failed saving last search context: {e}")
        
        return state
    
    def validate_relevance_node(self, state: AgentState) -> AgentState:
        """Validate if search results are relevant to user's query"""
        print(f"\nðŸŽ¯ STEP 2.5: Validating Relevance")
        
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
        
        # After the existing product_summaries building...

        # Individual product validation
        prompt = f"""
Analyze EACH product individually for relevance to the user's query.

User's Query: "{original_query}"

Products to validate:
{chr(10).join(product_summaries)}

For EACH product, determine if it matches the query criteria:
- Product type match (e.g., if user wants "bag", is it actually a bag?)
- Color match (if specified - e.g., "blue" means the product should be blue colored, not just have "blue" in brand name)
- Must Gender match (if specified)
- Also check for prices, is the prices match what user required
- Category match (shoes vs socks, bracelet vs watch, etc etc.)

Return JSON with individual scores:
{{
    "products": [
        {{"index": 0, "relevant": true/false, "reason": "explanation"}},
        {{"index": 1, "relevant": true/false, "reason": "explanation"}},
        ...
    ],
    "overall_relevance": "HIGHLY_RELEVANT|PARTIALLY_RELEVANT|NOT_RELEVANT"
}}

STRICT RULES:
- "blue bag" means a bag that is blue in color, NOT products with "blue" in brand name
- "dress shoes" means formal shoes, NOT socks or casual shoes
- "leather bracelet" means bracelet made of leather, NOT watches or other accessories
- If user specific something like about price, ratings, brand, colours, etc or even number of products to shown make sure to validate that too, by checking the data available in product metadata correctly and intelligenetly
- Must make sure to skip those that are duplicate like if 2 products are seems as same (same means same model but different ASINs or variants) then keep only one of them and mark this as well as are doing for those that are not showing
- Be strict about product type matching
"""

        try:
            print("ðŸ”¤ Validating with Gemini...")
            response = self.classifier_llm.invoke(prompt)
            content = response.content.strip()
    
            print(f"ðŸ” Raw Gemini response: {content[:200]}...")
    
            # Enhanced JSON extraction - handles text before/after JSON
            json_content = content
    
            # Method 1: Look for ```json code blocks
            if '```json' in content:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)
            # Method 2: Look for regular ``` blocks
            elif '```' in content:
                json_match = re.search(r'```\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                        json_content = json_match.group(1)
            # Method 3: Find any JSON object with "relevance" key
            else:
                json_match = re.search(r'\{[^{}]*"relevance"[^{}]*\}', content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(0)
    
            print(f"ðŸ“„ Extracted JSON: {json_content[:200]}...")
    
            result = json.loads(json_content)

            validated_products = []
            for prod_validation in result.get("products", []):
                if prod_validation.get("relevant", False):
                    idx = prod_validation.get("index", -1)
                    if 0 <= idx < len(products):
                        validated_products.append(products[idx])

            # ✅ Update the search results with filtered products
            state.search_results["display_products"] = validated_products[:5]  # Keep max 5
            state.search_results["products"] = validated_products
            state.search_results["total_found"] = len(validated_products)
            relevance = result.get("relevance", "HIGHLY_RELEVANT")
    
            print(f"ðŸ“Š Relevance: {relevance}")
            print(f"ðŸ’¡ Reasoning: {result.get('reasoning', '')}")
    
            state.relevance_status = relevance.lower()
            state.relevance_reasoning = result.get("reasoning", "")

        except json.JSONDecodeError as e:
            print(f"âŒ JSON parsing error: {e}")
            print(f"ðŸ“„ Full content: {content if 'content' in locals() else 'No content'}")
    
            # Fallback: Look for keywords in the response
            content_lower = content.lower() if 'content' in locals() else ""
            if 'not_relevant' in content_lower or '"relevance": "not_relevant"' in content_lower:
                print("ðŸ” Detected NOT_RELEVANT from keywords")
                state.relevance_status = "not_relevant"
                state.relevance_reasoning = "Products do not match user query"
            elif 'partially_relevant' in content_lower or 'partially' in content_lower:
                print("ðŸ” Detected PARTIALLY_RELEVANT from keywords")
                state.relevance_status = "partially_relevant"
                state.relevance_reasoning = "Products are similar but not exact match"
            else:
                print("âš ï¸ Defaulting to highly_relevant")
                state.relevance_status = "highly_relevant"
        
        except Exception as e:
            print(f"âŒ Validation error: {e}")
            state.relevance_status = "highly_relevant"

        return state
    
    def route_after_validation(self, state: AgentState) -> str:
        """Route based on relevance validation"""
        relevance = getattr(state, 'relevance_status', 'highly_relevant')
        
        if relevance == "not_relevant" or relevance == "no_results":
            print("ðŸš¦ Routing to: no_relevant_products")
            return "no_relevant"
        
        print("ðŸš¦ Routing to: generate_response")
        return "relevant"
    
    def handle_no_relevant_products_node(self, state: AgentState) -> AgentState:
        """Handle case when no relevant products found"""
        print(f"\nðŸš« STEP: Handling No Relevant Products")
        
        relevance_status = getattr(state, 'relevance_status', 'no_results')
        search_results = state.search_results or {}
        products = search_results.get("display_products", [])
        
        if relevance_status == "no_results" or not products:
            # No products at all
            prompt = f"""
User searched for: "{state.current_query}"
No products were found.

Previous context: {state.conversation_context}

Generate a helpful response that:
1. Clearly states: "I couldn't find any [EXACT PRODUCT TYPE] that match your request"
2. If this was a correction (user said "no X, I want Y"), acknowledge: "I understand you're looking for Y, not X"
3. Suggest they try different keywords or ask what specific type they need
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
            print(f"âŒ Error: {e}")
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
        
        print(f"ðŸ’¬ No Relevant Response: {state.final_response}")
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
    
    def _apply_strict_filters(self, products: List[Dict], query: str) -> List[Dict]:
        """Apply strict post-search filters based on query keywords"""
        query_lower = query.lower()
        filtered = []
        
        # Define product type keywords and their exclusions
        type_exclusions = {
            'bag': ['socks', 'shoes', 'shirt', 'pants', 'watch', 'bracelet'],
            'shoes': ['socks', 'bag', 'shirt', 'pants', 'insole', 'laces'],
            'bracelet': ['watch', 'necklace', 'ring', 'socks', 'shoes'],
            'dress shoes': ['boots', 'sneakers', 'socks', 'casual', 'athletic']
        }
        
        # Extract the main product type from query
        requested_type = None
        for ptype in type_exclusions.keys():
            if ptype in query_lower:
                requested_type = ptype
                break
            
        for product in products:
            title_lower = (product.get('title', '') or '').lower()
            category_lower = (product.get('category', '') or '').lower()
            
            # Check exclusions
            if requested_type and requested_type in type_exclusions:
                excluded = False
                for exclusion in type_exclusions[requested_type]:
                    if exclusion in title_lower or exclusion in category_lower:
                        excluded = True
                        break
                if excluded:
                    continue
                
            # Check color matching (if color specified)
            color_words = ['blue', 'red', 'green', 'black', 'white', 'brown', 'pink', 'yellow']
            for color in color_words:
                if color in query_lower:
                    # Color should be in title/description, not just brand name
                    if color not in title_lower.split() and color not in product.get('color', '').lower():
                        # Skip if color doesn't match
                        if not any(color in word.lower() for word in title_lower.split() if 'brand' not in word.lower()):
                            continue
                        
            filtered.append(product)
        
        return filtered
    
    def _extract_rating_filter(self, query: str) -> float:
        """Extract minimum rating from query"""
        query_lower = query.lower()
    
        # Match patterns like "more than 4.5 rating/ratting/stars"
        rating_match = re.search(r'(?:more than|above|over|at least)\s+(\d+\.?\d*)\s*(?:rating|ratting|star)', query_lower)
        if rating_match:
            return float(rating_match.group(1))
    
        return 0.0
    
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
        print(f"\nðŸ¤– STEP 3: Generating Response with Gemini")
        
        search_results = state.search_results or {}
        products = search_results.get("display_products", [])
        total_found = search_results.get("total_found", 0)
        relevance_status = getattr(state, 'relevance_status', 'highly_relevant')
        
        print(f"ðŸ“Š Total products found: {total_found}")
        print(f"ðŸ“± Products to display: {len(products)}")
        print(f"ðŸŽ¯ Relevance: {relevance_status}")
        
        # Limit to top 3 for display
        # Extract requested number from query
        import re
        query_lower = state.current_query.lower()
        number_match = re.search(r'\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b', query_lower)
        requested_count = 3  # default

        # First check for "X more" patterns
        more_match = re.search(r'(\d+)\s+more', query_lower)
        if more_match:
            requested_count = int(more_match.group(1))
        elif number_match:
            num_word = number_match.group(1)
            word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 
                    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
            requested_count = word_to_num.get(num_word, int(num_word) if num_word.isdigit() else 3)
            if more_match:
                try:
                    requested_count = int(more_match.group(1))
                except Exception:
                    requested_count = 3

        

        # Limit to requested number for display
        display_products = products[:requested_count] if products else []

        # ✅ Acknowledge if fewer relevant products than requested
        acknowledgement_note = " "
        if len(display_products) < requested_count and len(display_products) > 0:
            acknowledgement_note = (
                f"\nNOTE: User requested {requested_count} but only {len(display_products)} relevant products were found. "
                "Acknowledge this naturally."
    )


        print ("display_products = ",display_products)
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
- If this is a follow-up query (like price filtering), acknowledge the previous context, followup query might be only 1 word like if you previously asked for gender, now user can say 'men' or 'women' or unisex or any small query
- Keep response concise but informative (2-3 sentences max)
- Use encouraging language
- Format cleanly with proper spacing

Generate a natural response:"""
            
            prompt += acknowledgement_note

            print(f"ðŸ“¤ Sending to Gemini for response generation...")
            
            try:
                gemini_response = self.response_llm.invoke(prompt)
                response_text = gemini_response.content.strip()
                print(f"ðŸ“¥ Gemini Response: {response_text}")
            except Exception as e:
                print(f"âŒ Gemini error: {e}")
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
        
        # Persist lightweight summary of last shown products for follow-up understanding
        try:
            if display_products:
                summary = []
                for p in display_products[:5]:
                    summary.append({
                        "asin": p.get("asin"),
                        "title": p.get("title"),
                        "brand": p.get("brand"),
                        "price_value": p.get("price_value"),
                        "stars": p.get("stars"),
                        "url": p.get("url"),
                    })
                self.session_manager.update_context(state.session_id, "last_display_products", summary)
        except Exception as e:
            print(f"âš ï¸ Failed to persist last_display_products: {e}")
        
        print(f"âœ… Response generated successfully")
        print(f"ðŸ’¬ Final Response: {response_text}")
        
        return state
    
    def run_chat(self, message: str, session_id: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the complete chatbot workflow"""
        print(f"\n" + "="*60)
        print(f"ðŸš€ Starting Chat Workflow")
        print(f"ðŸ“ Message: '{message}'")
        print(f"ðŸ’¬ Session: {session_id}")
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
            print("ðŸ”„ Running LangGraph workflow...")
            final_state = self.app.invoke(initial_state)
            print("âœ… Workflow completed successfully")
        except Exception as e:
            print(f"âŒ Workflow error: {e}")
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
        
        print(f"\nðŸ“Š FINAL RESULT:")
        print(f"ðŸ’¬ Response: {response_text}")
        print(f"ðŸ›ï¸ Products: {len(ui_products) if ui_products else 0}")
        print(f"ðŸ“ˆ Total Found: {search_results.get('total_found', 0) if isinstance(search_results, dict) else 0}")
        print(f"="*60)
        
        return result