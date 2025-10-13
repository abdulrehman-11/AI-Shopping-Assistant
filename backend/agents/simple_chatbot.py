"""
Simplified Intelligent Shopping Chatbot
Uses Gemini with function calling for natural conversation handling
"""

import json
from typing import Dict, Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import StructuredTool
from config import Config
from tools.pinecone_tool import PineconeTool
from tools.session_manager import SessionManager
from tools.json_fallback import JsonFallbackTool
from tools.cache_manager import CacheManager
from models.schemas import MessageRole
import cohere


class SimpleChatbot:
    """Intelligent shopping assistant using single LLM with function calling"""
    
    def __init__(self):
        print("🤖 Initializing Simple Chatbot...")
        
        # Initialize tools
        self.pinecone = PineconeTool()
        self.session_manager = SessionManager(Config.REDIS_URL)
        self.json_fallback = JsonFallbackTool()
        self.cache_manager = CacheManager(
            self.session_manager.redis if self.session_manager.use_redis else None
        )
        self.cohere_client = cohere.Client(Config.COHERE_API_KEY)
        
        # Initialize Gemini with function calling
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GEMINI_API_KEY,
            temperature=0.4
        )
        
        # Define the master prompt
        self.system_prompt = self._build_system_prompt()
        
        print("✅ Simple Chatbot initialized successfully")
    
    def _build_system_prompt(self) -> str:
        """Master prompt - single source of truth"""
        return """You are an intelligent shopping assistant for an e-commerce platform specializing in fashion and accessories.

**Available Product Categories:**
- Men's Bags (backpacks, crossbody, shoulder bags, etc.)
- Men's Jewelry (watches, bracelets, rings, necklaces, etc.)
- Men's Shoes (sneakers, dress shoes, casual, sports, etc.)
- Men's Clothing (shirts, pants, jackets, hoodies, etc.)
- Nike Shoes (all Nike footwear - men's and women's)
- Women's Clothing (dresses, tops, pants, etc.)

**Your Capabilities:**
You have access to a tool called `search_products` that searches our product database using semantic search.

**Conversation Guidelines:**

1. **Natural Understanding:**
   - Understand user intent from context, not just current message
   - Handle follow-ups intelligently (e.g., "show me more", "cheaper ones", "Nike brand")
   - handle spelling mistakes and typos
   - Detect gender from context (e.g., "for my wife" = women's, "for me" + previous men's items = men's) also consider unisex if user said
   - Combine current query with relevant conversation history

2. **Search Strategy:**
   - Always search when user asks for products
   - Search MORE than needed (e.g., search 10, show best 3)
   - In your response, ONLY describe products you want to show
    *- Afteribing products, add this line: "SHOW_COUNT: X" where X is how many products to display*
   - For vague queries (e.g., "shoes"), search first, then ask for clarification if results are mixed
   - For quries like "any other item", "show more" etc requests, search with offset (skip already shown items)
   - Strictly remove duplicates from results
   - *Strictly remove irrelevant results to be shown*, For eg;  if user ask for rings and pinecone return rings + brecelets or necklaces etc, remove those irrelvant items and only show that are match with user intent
   - Carefully check the words along with user query to know is that something specific about product, Like ; user: Men leather bags, here leather is specific about product, so search with that, and also consider this when filtering irrelevant to know user priority. But leather is not just the only priority, also what user search should also be considered, like here leather + men bags should match 

3. **Handling Different Queries:**
   - **Product Search:** Search immediately and present results naturally
   - **Off-topic:** Politely redirect to shopping (e.g., "I'm here to help you shop! Looking for anything specific?")
   - **No Results:** Apologize, suggest the category might not be available, offer alternatives
   - **Vague:** Show some results AND ask for clarification (don't just ask without showing anything)
   - **Follow-ups:** Understand context (e.g., after showing "shoes", user says "under $50" → search "shoes under $50")

4. **Response Style:**
   - Be conversational and helpful, not robotic
   - Keep responses concise (2-3 sentences)
   - Acknowledge user preferences from history
   - Use natural language, avoid phrases like "I searched our database"

5. **Price & Filters (CRITICAL):**
   - ALWAYS extract price ranges: "under $50" → max_price=50, "more than $100" → min_price=100, "between $50-$100" → min_price=50, max_price=100
   - For "cheapest"/"lowest price" → sort_by="price_low_to_high" + limit=5
   - For "expensive"/"premium" → sort_by="price_high_to_low" + limit=5
   - Extract ratings: "4+ stars" → min_rating=4, "highly rated" → min_rating=4
   - **IMPORTANT**: When price/rating is mentioned, ALWAYS search MORE products (limit=25) to ensure accurate filtering
   - **Sorting:** Auto-detect and use sort_by parameter:
     * "cheapest", "budget", "affordable" → sort_by="price_low_to_high"
     * "expensive", "premium", "high-end" → sort_by="price_high_to_low"
     * "best rated", "top rated", "highest rating" → sort_by="rating"
     * "popular", "most reviewed" → sort_by="popular"

6. **Show More Logic:**
   - If user says "show more", "next", "other options", etc., understand they want additional products
   - Use the conversation history to understand what they were looking at
   - Search with increased offset or limit

7. **Categories Question:**
   - If asked "what categories do you have?", list the available categories clearly
   - No need to search, just tell them

8. **Product Questions:** When user asks about specific product features:
     1. FIRST search for the product
     2. THEN answer using the product's metadata/description/title
     3. Example: "Is X waterproof?" → Search "X" → Check description/title → Answer
     4. If description doesn't have info, search and say "I found X, but waterproof info isn't listed"

9. **CRITICAL Product Filtering**:
   - After searching, analyze EACH product returned
   - Score relevance 0-10 based on matching query intent
   - ONLY show products scoring > 5
   - If user asks for "leather", NEVER show non-leather items
   - Check product title AND category for relevance but if price also mentioned in query also chekc price tags.
   - If fewer than 3 relevant products are found, say "I only found X leather items" instead of padding with irrelevant ones

10. **Important Rules:**
   - ALWAYS search before saying "we don't have that" 
   - Analyze the products that pinecone returns and only show relevant ones, removing duplicates and irrelevant items (This is must), Even 1 product is relecant please show only that one. Here consider product title, brand, category, price etc to decide if product is relevant or not
   - Don't make up product details - only use what search returns
   - If no results, suggest similar categories (not prooducts just categories) or ask for more details

**Example Interactions:**
For each query limit=3 is not hardcoded, Yes it is dafult 3 if you found many products, So choose 3, but if 1 or 2 are relvant then show that only.
Eg:
User: "show me nike shoes"
You: *search_products(query="nike shoes", limit=3)*
Response: "Here are 3 popular Nike shoes for you! [describe briefly if needed]"

User: "show me cheapest men's bags"
You: *search_products(query="men's bags", limit=25, sort_by="price_low_to_high")*
Response: "Here are the most affordable men's bags I found! [show top 3-5]"

User: "Nike shoes between $50-$100"
You: *search_products(query="Nike shoes", min_price=50, max_price=100, limit=25)*
Response: "Found Nike shoes in your budget ($50-$100)! [show best matches]"

User: "highest rated watches"
You: *search_products(query="watches", min_rating=4, limit=25, sort_by="rating")*
Response: "These are our top-rated watches with 4+ stars! [show top 3]"

User: "Is X has Y feature/quality? etc, eg; Is Travelon Anti-Theft Metro Convertible, a leather bag"
You: *search_products(query="Travelon Anti-Theft Metro Convertible bag"or "Travelon Metro Convertible bag",check their metadata of some specific info, limit=[all same relevant products, but if same then , [limit =1]])*
Response: "I found Travelon Anti-Theft Metro Convertible bag[Check description for leather info]. According to the product details, [answer based on what you find]. Would you like to see this Bag"

User: "I want shoes" 
You: *search_products(query="shoes", limit=3)*
Response: "I found some great shoes! Are you looking for men's or women's? Here are a few options to start..."

User: [after seeing products] "show me more"
You: *search_products(query="[previous search context]", limit=3, offset=3)*
Response: "Here are 3 more options for you!"

User: [after seeing men's shoes] "under $50"
You: *search_products(query="men's shoes", max_price=50, limit =3)* 
Response: "Here are men's shoes under $50!"

User: "what categories do you have?"
Response: "We have Men's Bags, Men's Jewelry, Men's Shoes, Men's Clothing, Nike Shoes, and Women's Clothing! What would you like to explore?"

**Remember:** You're smart and conversational. Use context, understand intent, and help users shop naturally!"""

    def _search_products_impl(
        self,
        query: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        limit: int = 10,
        offset: int = 0,
        sort_by: Optional[str] = None
    ) -> str:
        """
        Internal implementation of product search.
        This is called by the tool wrapper.
        """
        print(f"🔍 Search called: query='{query}', limit={limit}, offset={offset}")
        
        try:
            # Build filters
            filters = {}
            if min_price is not None or max_price is not None:
                price_filter = {}
                if min_price is not None:
                    price_filter['$gte'] = float(min_price)
                if max_price is not None:
                    price_filter['$lte'] = float(max_price)
                filters['price_value'] = price_filter
            
            if min_rating is not None:
                filters['stars'] = {'$gte': float(min_rating)}
            
            # Check cache first
            cache_key = f"{query}_{min_price}_{max_price}_{min_rating}"
            cached = self.cache_manager.get_cached_search(cache_key, filters)
            
            if cached and not offset:
                products = cached.get('products', [])
                print(f"📦 Using cached results: {len(products)} products")
            else:
                # Search Pinecone
                search_limit = limit + offset + 10
                products = self.pinecone.search_similar_products(
                    query=query,
                    filters=filters,
                    top_k=search_limit
                )
                
                if not products:
                    return json.dumps({"products": [], "total": 0, "message": "No products found"})
                
                # Enrich with JSON data
                products = self.json_fallback.enrich_products(products)
                
                # Cohere Rerank
                if len(products) > 1:
                    try:
                        docs = [
                            f"{p.get('title', '')} {p.get('brand', '')} {p.get('category', '')} ${p.get('price_value', 0)}"
                            for p in products
                        ]
                        
                        rerank_result = self.cohere_client.rerank(
                            model="rerank-english-v3.0",
                            query=query,
                            documents=docs,
                            top_n=min(search_limit, len(docs))
                        )
                        
                        reranked = []
                        for r in rerank_result.results:
                            prod = products[r.index].copy()
                            prod['rerank_score'] = float(r.relevance_score)
                            reranked.append(prod)
                        
                        products = reranked
                        print(f"🎯 Reranked to {len(products)} products")
                        
                    except Exception as e:
                        print(f"⚠️ Reranking failed: {e}")

                # 🧠 Filter out low-relevance or non-matching products
                if products:
                    # Filter by rerank score
                    relevance_threshold = 0.3  # adjust if needed
                    products = [p for p in products if p.get('rerank_score', 1.0) > relevance_threshold]

                    # Additional keyword-based filtering
                    query_keywords = query.lower().split()
                    if "leather" in query_keywords:
                        products = [p for p in products if "leather" in p.get("title", "").lower()]
                    
                    # Apply strict price/rating filtering and sorting from JSON data
                    products = self.json_fallback.filter_and_sort_by_criteria(
                        products=products,
                        query=query,
                        min_price=min_price,
                        max_price=max_price,
                        min_rating=min_rating,
                        sort_by=sort_by
                    )
                
                # Cache results
                if not offset:
                    self.cache_manager.cache_search_results(
                        cache_key,
                        {"products": products, "total": len(products)},
                        filters
                    )
            
            # Apply offset and limit
            final_products = products[offset:offset + limit]

            # Apply sorting if requested
            if sort_by and final_products:
                if sort_by in ["price_low_to_high", "price_asc", "price_ascending"]:
                    final_products = sorted(final_products, key=lambda x: x.get('price_value') or 999999)
                    print(f"📊 Sorted by price (low to high)")
                elif sort_by in ["price_high_to_low", "price_desc", "price_descending"]:
                    final_products = sorted(final_products, key=lambda x: x.get('price_value') or 0, reverse=True)
                    print(f"📊 Sorted by price (high to low)")
                elif sort_by in ["rating", "rating_high", "top_rated"]:
                    final_products = sorted(final_products, key=lambda x: x.get('stars') or 0, reverse=True)
                    print(f"📊 Sorted by rating (high to low)")
                elif sort_by in ["reviews", "popular", "popularity"]:
                    final_products = sorted(final_products, key=lambda x: x.get('reviews_count') or 0, reverse=True)
                    print(f"📊 Sorted by popularity (reviews)")

            # Format for LLM
            result = {
                "products": final_products,
                "total": len(products),
                "showing": len(final_products),
                "offset": offset,
                "sorted_by": sort_by if sort_by else None  # ← Add this for transparency
            }
            
            print(f"✅ Returning {len(final_products)} products (total: {len(products)})")
            return json.dumps(result)
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"products": [], "total": 0, "error": str(e)})
    
    def run_chat(self, message: str, session_id: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main chat function - handles everything"""
        print(f"\n{'='*60}")
        print(f"💬 User: {message}")
        print(f"🆔 Session: {session_id}")
        print(f"{'='*60}\n")
        
        try:
            # 1. Add user message to session
            self.session_manager.add_message(session_id, MessageRole.USER, message)
            
            # 2. Get conversation history
            session = self.session_manager.get_session(session_id)
            history_messages = self._format_history_for_llm(session.messages[-20:])
            
            # 3. Prepare messages for LLM
            messages = [
                SystemMessage(content=self.system_prompt),
                *history_messages,
                HumanMessage(content=message)
            ]
            
            # 4. Create tool dynamically (fixes the 'self' issue)
            search_tool = StructuredTool.from_function(
                func=self._search_products_impl,
                name="search_products",
                description="""Search for products using semantic similarity.

                Parameters:
                - query: Search terms
                - min_price, max_price: Price filters
                - min_rating: Minimum star rating
                - limit: Number of products (default 10)
                - offset: Skip first N products (for pagination)
                - sort_by: Sort results - options: 'price_low_to_high', 'price_high_to_low', 'rating', 'popular'

                Use this when user asks for products or wants to browse.""",
            )
            
            # 5. Bind tools to LLM
            llm_with_tools = self.llm.bind_tools([search_tool])
            
            # 6. First LLM call
            print("🤖 Calling Gemini...")
            response = llm_with_tools.invoke(messages)
            
            # 7. Handle tool calls
            products_data = []
            search_limit = 3  # default

            while response.tool_calls:
                print(f"🔧 Tool calls detected: {len(response.tool_calls)}")

                for tool_call in response.tool_calls:
                    if tool_call['name'] == 'search_products':
                        # Save the limit Gemini requested
                        search_limit = tool_call['args'].get('limit', 3)  # ← CAPTURE THIS

                        # Execute search
                        result = self._search_products_impl(**tool_call['args'])
                        result_data = json.loads(result)
                        products_data = result_data.get('products', [])

                        # Add tool result to messages
                        messages.append(response)
                        messages.append(
                            HumanMessage(
                                content=f"Tool result: {result}",
                                name="search_products"
                            )
                        )

                # Second LLM call with tool results
                print("🤖 Calling Gemini with tool results...")
                response = llm_with_tools.invoke(messages)

            # 8. Extract final response
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Parse show count - use search_limit as default (what Gemini requested)
            show_count = search_limit  # ← USE THIS, not 3!
            import re
            count_match = re.search(r'SHOW_COUNT:\s*(\d+)', response_text)
            if count_match:
                show_count = int(count_match.group(1))
                # Remove the SHOW_COUNT line from user-facing response
                response_text = re.sub(r'\s*SHOW_COUNT:\s*\d+\s*', '', response_text).strip()

            print(f"💬 Assistant: {response_text}")
            print(f"📊 Show count: {show_count} (requested: {search_limit})\n")

        

            ui_products = self._format_products_for_ui(products_data[:show_count])

            
            # 10. Save assistant response
            self.session_manager.add_message(
                session_id,
                MessageRole.ASSISTANT,
                response_text,
                metadata={
                    "products_count": len(ui_products),
                    "all_products": products_data[:10],
                    "shown_products": products_data[:len(ui_products)]
                }
            )
            
            # 11. Return response
            return {
                "response": response_text,
                "products": products_data,
                "ui_products": ui_products,
                "needs_clarification": False,
                "clarification_questions": [],
                "search_metadata": {
                    "total_found": len(products_data),
                    "search_query": message,
                    "filters_applied": {}
                },
                "session_id": session_id
            }
            
        except Exception as e:
            print(f"❌ Chat error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "response": "I'm having trouble right now. Could you try rephrasing? For example: 'show me men's shoes' or 'I need Nike sneakers'.",
                "products": [],
                "ui_products": [],
                "needs_clarification": False,
                "clarification_questions": [],
                "search_metadata": {"error": str(e)},
                "session_id": session_id
            }
    
    def _format_history_for_llm(self, messages: List) -> List:
        """Convert session messages to LLM format"""
        formatted = []
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)
            role = msg.role if hasattr(msg, 'role') else 'user'
            
            if role == MessageRole.USER or role == 'user':
                formatted.append(HumanMessage(content=content))
            elif role == MessageRole.ASSISTANT or role == 'assistant':
                formatted.append(AIMessage(content=content))
        
        return formatted
    
    def _format_products_for_ui(self, products: List[Dict]) -> List[Dict]:
        """Format products for frontend display"""
        ui_products = []
        
        for p in products:
            price_value = p.get("price_value") or (p.get("price", {}).get("value") if isinstance(p.get("price"), dict) else p.get("price"))
            price_str = f"${float(price_value):.2f}" if price_value else "See on Amazon"
            
            ui_products.append({
                "asin": p.get("asin"),
                "image": p.get("image_url") or p.get("thumbnailImage") or p.get("thumbnail_image") or "",
                "title": p.get("title") or "Product",
                "description": p.get("brand") or p.get("category") or "",
                "rating": float(p.get("stars") or 0),
                "reviews": int(p.get("reviews_count") or p.get("reviewsCount") or 0),
                "price": price_str,
                "url": p.get("url") or f"https://www.amazon.com/dp/{p.get('asin', '')}",
                "similarity_score": p.get("similarity_score", 0),
                "rerank_score": p.get("rerank_score", 0)
            })
        
        return ui_products