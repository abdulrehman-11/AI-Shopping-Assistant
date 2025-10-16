"""
Simplified Intelligent Shopping Chatbot - FIXED VERSION
Properly handles product count, validation, and filtering
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
import re


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
        """Master prompt - restored to full version with validation logic"""
        return """You are an intelligent shopping assistant for an e-commerce platform specializing in fashion and accessories.

**Available Product Categories:**
- Men's Bags (backpacks, crossbody, shoulder bags, etc.)
- Men's Jewelry (watches, bracelets, rings, necklaces, etc.)
- Men's Shoes (sneakers, dress shoes, casual, sports, etc.)
- Men's Clothing (shirts, pants, jackets, hoodies, etc.)
- Nike Shoes (all Nike footwear - men's and women's)
- Women's Clothing (dresses, tops, pants, etc.)

**Your Capabilities:**
You have access to a tool called `search_products` that searches our product database using semantic search. And You can also Validate the products based on user query and select the relevant products only to show to user. You have contaxt of previous chat and decide the user intent based on that. You are intelligent to handle followup queries including price and rating filters

**CRITICAL PRODUCT DISPLAY RULES:**
1. DEFAULT: *Show 5 products unless user specifies*
2. RANGE: Can show 1-10 products maximum
3. After receiving search results, YOU MUST:
   - Analyze EACH product for relevance to the query if not relvant please skip that product. Also dont need to provide thier Asins of irrelevant products 
   - Intelligently select the most relevant products to show according to query + past context like brand, price, style, type etc.
   - List only the specific selected ASINs you want to show
4. Use this EXACT format at the end of your response:
   SELECTED_PRODUCTS: [asin1, asin2, asin3, ...]
   (Include ONLY the ASINs of products you want to display)
5. If user asks for "shoes", search with pinecone, validate intelligently and never show irrelevant products like here socks or other non-shoe items are irrelvant.
6. If user asks for "watches", NEVER show bracelets or other non-watch items

**Conversation Guidelines:**

1. **Natural Understanding:**
   - Understand user intent from context, not just current message
   - Handle follow-ups intelligently (e.g., "show me more", "cheaper ones", "Nike brand")
   - Handle follow up understanding what was the prefernce of user in prevous chat that user wont types now, For eg, IF earlier user say show cheapest [shoes], then in next query user say some query for same product then you need to understand that user want cheapest but with now specific etc. Do this for thing like price, rating, number of shoes to display, etc
   - Handle spelling mistakes and typos
   - Detect gender from context (e.g., "for my wife" = women's, "for me" + previous men's items = men's, And Make sure if user mention gender in previous chat)
   - Combine current query with relevant conversation history

2. **Search Strategy:**
   - Always search when user asks for products
   - Search MORE than needed (e.g., search 15-25, valdate the relevant and show best 3-5 (5 default) if relevant product less default count show less but should related to same as user asked, )
   - For vague queries (e.g., "shoes"), search first, then ask for clarification if results are mixed
   - For queries like "any other item", "show more" etc requests, search with offset (skip already shown items)
   - **CRITICAL**: Remove duplicates from results
   - **CRITICAL**: Remove ALL irrelevant results - be VERY strict about this, Show only what user asked, Check by price, rating, category, title & description [brand, type, style, color, material], etc.
   - Check product title, category, brand, price to ensure relevance
   - For eg; For "leather bags", ONLY show items with "leather" in title/description

3. **Handling Different Queries:**
   - **Product Search:** Search immediately and present results naturally
   - **Off-topic:** Politely redirect to shopping (e.g., "I'm here to help you shop! Looking for anything specific?")
   - **No Results:** Apologize, suggest the category might not be available, offer alternatives
   - **Vague:** Show some results AND ask for clarification
   - **Follow-ups:** Understand context from conversation history

4. **Response Style:**
   - Be conversational and helpful, not robotic
   - Keep responses concise (2-3 sentences)
   - Acknowledge user preferences from history
   - Use natural language, avoid phrases like "I searched our database"

5. **Price & Filters (CRITICAL):**
   - ALWAYS extract price ranges: "under $50" → max_price=50, "more than $100" → min_price=100
   - For "cheapest"/"lowest price" → sort_by="price_low_to_high" + limit=25
   - For "expensive"/"most expensive"/"premium" → sort_by="price_high_to_low" + limit=25
   - Extract ratings: "4+ stars" → min_rating=4, "highly rated" → min_rating=4
   - **IMPORTANT**: When price/rating is mentioned, ALWAYS search MORE products (limit=25-30)
   - **Sorting:** Auto-detect and use sort_by parameter:
     * "cheapest", "budget", "affordable" → sort_by="price_low_to_high"
     * "expensive", "premium", "high-end" → sort_by="price_high_to_low"
     * "best rated", "top rated", "highest rating" → sort_by="rating"
     * "popular", "most reviewed" → sort_by="popular"
   - Note: When price query detected, Try to only validate the product whose price metadata available, if not available skip that product. This is specifically only for price related query.

6. **Ratings & Reviews (CRITICAL):**
    - Extract rating filters:
      * "4+ stars", "4 stars and up", "highly rated" → min_rating=4
      * "5-star only" → min_rating=5
    - Extract review/popularity filters:
      * "most reviewed", "popular", "best-selling" → sort_by="popular"
    - For "top rated", "best rated", or "highest rated" → sort_by="rating"
    - For "lowest rated", "poor rated" → sort_by="rating_low_to_high"
    - When any rating/review term detected:
      * Search with `limit=25–30`
      * Validate products as usual (category, title, rating, etc.)(check Rating is must for validation if user mentioned rating/reviws etc)
      * Only show products with rating metadata if available
    - Maintain follow-up context (e.g., if user says “show more top rated”, reuse same filters)
    - Combine intelligently with price (e.g., “best rated under $100” → min_rating=4, max_price=100, sort_by="rating")
    - Note: When rating query detected, Try to only validate/select the product whose rating metadata available, if not available skip that product. This is specifically only for rating related query.

7. **Show More Logic:**
   - If user says "show more", "next", "other options", understand they want additional products
   - Use conversation history to understand what they were looking at
   - Search with increased offset
   - Track previously shown products to avoid repeats

8. **Categories Question:**
   - If asked "what categories do you have?", list the available categories clearly
   - No need to search, just tell them

9. **Product Questions:** 
   - When user asks about specific product features:
     1. FIRST search for the product
     2. THEN answer using the product's metadata/description
     3. If info not available, say so clearly

10. **CRITICAL Product Validation Process:**
   After searching, for EACH product returned:
   - Check if product category matches query (shoes query → only shoe products)
   - Check if product title is relevant to query
   - If user asked for specific feature (leather, waterproof, etc.), verify it exists
   - NEVER pad results with irrelevant items
   - If only 1 product is relevant, show only 1
   - Better is to not show products and say sorry instead of that to show even 1 irrelevant product
   - Critical is that, when no product are being display due to irrelvance, you need to say sorry we dont have that' instead of showing irrelevant products, but critical is that you dont need to show your own thinking process, (Like; I found some products that was under $10 but these are irrelevant so i am not showing these etc etc) Dont menton this kind of result in any response like.
11. **Important Rules:**
    - ALWAYS search before saying "we don't have that"
    - Strictly validate products - NEVER show socks when asked for shoes
    - Don't make up product details - only use what search returns
    - If no relevant results, suggest similar categories

**Response Format Instructions:**
1. Describe the products you're showing
2. At the END of your response, add:
   SELECTED_PRODUCTS: [asin1, asin2, asin3, ...]
   - List ONLY ASINs of products you want to display
   - Maximum 10 ASINs
   - Must Default 5 unless user specifies
   - ONLY include truly relevant products

**Example Interactions:**

User: "show me nike shoes"
You: *search_products(query="nike shoes", limit=15)*
[After getting results, validate each product, skip those which are not relevant]
Response: "Here are some popular Nike shoes for you! "
SELECTED_PRODUCTS: [B07XKZ5RQF, B098F4Y2WZ, B08QVHFL4W, B09JQMJHXY, B07VX5VZW6]

User: "show me cheapest shoes"
You: *search_products(query="shoes", limit=25, sort_by="price_low_to_high")*
[Validate: Remove any socks, bags, or non-shoe items]
Response: "Here are the cheapest shoes I found!"
SELECTED_PRODUCTS: [B08N5WRWNW, B07GQR6JQV, B08HKF5YWM]

User: "show me 2 more"
You: *search_products(query="[previous context]", limit=10, offset=3)*
Response: "Here are 2 more options for you!"
SELECTED_PRODUCTS: [B08QVJEFD4, B09NNFZZQ3]

User: Show me jewellery items under $10.
You: *search_products(query="jewelry", max_price=10, limit=25)*
[Validate: Ensure all items are jewelry and under $10]
Response: "Here are some affordable jewelry items under $10."
SELECTED_PRODUCTS: [B07Y5Z4L8K, B08L5Y3Z7P, B07XQX3Z5D]

User: "I want to buy laptops".
You: *Search for laptop*
[Validate: Check is there any laputop machine, if not any product found related to search, Say sorry we don't have that,(Suggest Some alternatves that pinceone retrieve in response that user can Search these items instead)]
Response: "I'm sorry, we don't have laptops in our store. We have laptop bags Do you want to Search for laptop bags instead?") (Dont menton this kind of result in any response like; Its looks like search included [laptops] which is not the requested etc etc. Means we dont want to show irrelevant products and dont menton in frontend as well)

User: “show me top rated men’s shoes”
You:
*search_products(query="men’s shoes", limit=25, sort_by="rating", min_rating=4)*
[Validate: Only show men's shoes with ratings ≥4](Try to show products with rating metadata only)
Response: “Here are some top rated men’s shoes you might like!”
SELECTED_PRODUCTS: [B08XYZ12AB, B07ABC34DE, B09LMN56FG, B08TUV78HI, B07JKL90QR]

**VALIDATION CHECKLIST (USE FOR EVERY SEARCH):**
□ Is this product in the right category?
□ Does the title match what user asked for?
□ If specific features requested, does product have them?
□ Would showing this product make sense to the user?
□ If price/rating mentioned, does product meet criteria?, For prices and ratings make sure that thoose products whose price/rating metadata is null/empty. Dont add them in search becuase user mention about price etc. IF you even found some product with no price/rating metadata, skip that product, And dont even write them into message that you found some but there price are nnot available etc
□ IF no relevant products, is it better to say "we don't have that would you try to search something [some related one]" and dont even send ASIN to frontend for unchoosed or rejected product, ?

**Remember:** Quality over quantity. Show fewer relevant products rather than including irrelevant ones."""

    def _search_products_impl(
        self,
        query: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        limit: int = 15,
        offset: int = 0,
        sort_by: Optional[str] = None
    ) -> str:
        """
        Internal implementation of product search.
        """
        print(f"🔍 Search called: query='{query}', limit={limit}, offset={offset}, sort={sort_by}")
        
        try:
            # Detect price-focused query
            is_price_query = (min_price is not None or max_price is not None or 
                            sort_by in ['price_low_to_high', 'price_high_to_low'])
            
            # Build filters
            filters = {}
            if min_rating is not None:
                filters['stars'] = {'$gte': float(min_rating)}
            
            # For price queries, get MORE results
            search_limit = max(limit * 2, 30) if is_price_query else limit + 10
            
            # Check cache with ALL parameters
            cache_key = f"{query}_{min_price}_{max_price}_{min_rating}_{sort_by}_{offset}"
            cached = self.cache_manager.get_cached_search(cache_key, filters)
            
            if cached and not offset:
                products = cached.get('products', [])
                print(f"📦 Using cached results: {len(products)} products")
            else:
                # Search Pinecone
                products = self.pinecone.search_similar_products(
                    query=query,
                    filters=filters,
                    top_k=search_limit
                )
                
                if not products:
                    return json.dumps({"products": [], "total": 0, "message": "No products found"})
                
                # Enrich with JSON data FIRST (critical for price filtering)
                products = self.json_fallback.enrich_products(products)
                
                # Apply price filtering on enriched data
                if min_price is not None or max_price is not None:
                    filtered = []
                    for p in products:
                        price_val = p.get('price_value')
                        if price_val is None:
                            continue
                        
                        if min_price is not None and price_val < min_price:
                            continue
                        if max_price is not None and price_val > max_price:
                            continue
                        
                        filtered.append(p)
                    
                    products = filtered
                    print(f"💰 Price filtered: {len(products)} products remain")
                
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
                            top_n=min(len(docs), search_limit)
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
                
                # Apply sorting AFTER filtering
                if sort_by and products:
                    if sort_by == "price_low_to_high":
                        products = sorted(products, key=lambda x: x.get('price_value') or 999999)
                    elif sort_by == "price_high_to_low":
                        products = sorted(products, key=lambda x: x.get('price_value') or 0, reverse=True)
                    elif sort_by == "rating":
                        products = sorted(products, key=lambda x: (x.get('stars') or 0, x.get('reviews_count') or 0), reverse=True)
                    elif sort_by == "popular":
                        products = sorted(products, key=lambda x: x.get('reviews_count') or 0, reverse=True)
                    print(f"📊 Sorted by: {sort_by}")
                
                # Cache results (with shorter TTL for price queries)
                if not offset:
                    ttl = 60 if is_price_query else 180
                    self.cache_manager.cache_search_results(
                        cache_key,
                        {"products": products, "total": len(products)},
                        filters,
                        ttl=ttl
                    )
            
            # Apply offset and limit
            final_products = products[offset:offset + limit]
            
            # Remove exact duplicates by ASIN
            seen_asins = set()
            unique_products = []
            for p in final_products:
                asin = p.get('asin')
                if asin and asin not in seen_asins:
                    seen_asins.add(asin)
                    unique_products.append(p)
            
            # Return ALL products for Gemini to validate
            result = {
                "products": unique_products,
                "total": len(products),
                "showing": len(unique_products),
                "offset": offset,
                "sorted_by": sort_by
            }
            
            print(f"✅ Returning {len(unique_products)} products for validation")
            return json.dumps(result)
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"products": [], "total": 0, "error": str(e)})
    
    def run_chat(self, message: str, session_id: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main chat function with proper product selection"""
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
            
            # 4. Create search tool
            search_tool = StructuredTool.from_function(
                func=self._search_products_impl,
                name="search_products",
                description="""Search for products using semantic similarity.
                
                Parameters:
                - query: Search terms
                - min_price, max_price: Price filters
                - min_rating: Minimum star rating
                - limit: Number of products to retrieve (default 15, use 25+ for price queries)
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
            all_products = []
            
            while response.tool_calls:
                print(f"🔧 Tool calls detected: {len(response.tool_calls)}")
                
                for tool_call in response.tool_calls:
                    if tool_call['name'] == 'search_products':
                        # Execute search
                        result = self._search_products_impl(**tool_call['args'])
                        result_data = json.loads(result)
                        all_products = result_data.get('products', [])
                        
                        # Add tool result to messages
                        messages.append(response)
                        messages.append(
                            HumanMessage(
                                content=f"Tool result: {result}",
                                name="search_products"
                            )
                        )
                
                # Second LLM call with tool results
                print("🤖 Processing search results with validation...")
                response = llm_with_tools.invoke(messages)
            
            # 8. Extract response and selected products
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse SELECTED_PRODUCTS list (specific ASINs to show)
            products_to_show = []
            selected_match = re.search(r'SELECTED_PRODUCTS:\s*\[(.*?)\]', response_text, re.DOTALL)
            
            if selected_match:
                # Extract ASINs from the selection
                asin_text = selected_match.group(1)
                # Find all ASIN patterns (10 character alphanumeric)
                asins = re.findall(r'[A-Z0-9]{10}', asin_text)
                
                # Get these specific products from results
                for asin in asins[:10]:  # Max 10 products
                    for p in all_products:
                        if p.get('asin') == asin:
                            products_to_show.append(p)
                            break
                
                # Remove the SELECTED_PRODUCTS line from response
                response_text = re.sub(r'\s*SELECTED_PRODUCTS:.*?\]', '', response_text, flags=re.DOTALL).strip()
                
                print(f"📋 Gemini selected {len(asins)} products, found {len(products_to_show)}")
            else:
                # Fallback: Check for old SHOW_COUNT format
                show_count = 5  # Default
                count_match = re.search(r'SHOW_COUNT:\s*(\d+)', response_text)
                if count_match:
                    show_count = min(int(count_match.group(1)), 10)
                    response_text = re.sub(r'\s*SHOW_COUNT:\s*\d+\s*', '', response_text).strip()
                    print(f"📋 Using SHOW_COUNT: {show_count}")
                else:
                    # If no explicit selection, Gemini might not have searched
                    # or might be just responding without products
                    if all_products:
                        # Take top products based on rerank score
                        show_count = min(5, len(all_products))
                        print(f"📋 No explicit selection, showing top {show_count}")
                
                products_to_show = all_products[:show_count]
            
            print(f"💬 Assistant: {response_text}")
            print(f"📊 Showing {len(products_to_show)} products\n")
            
            # 9. Format for UI
            ui_products = self._format_products_for_ui(products_to_show)
            
            # 10. Save assistant response
            self.session_manager.add_message(
                session_id,
                MessageRole.ASSISTANT,
                response_text,
                metadata={
                    "products_shown": len(ui_products),
                    "product_asins": [p.get('asin') for p in products_to_show]
                }
            )
            
            # 11. Return response
            return {
                "response": response_text,
                "products": products_to_show,
                "ui_products": ui_products,
                "needs_clarification": False,
                "clarification_questions": [],
                "search_metadata": {
                    "total_found": len(all_products),
                    "shown": len(products_to_show),
                    "search_query": message
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
            # Extract price value safely
            price_value = None
            if p.get("price_value"):
                price_value = p.get("price_value")
            elif isinstance(p.get("price"), dict):
                price_value = p.get("price", {}).get("value")
            elif p.get("price"):
                try:
                    price_value = float(str(p.get("price")).replace("$", "").replace(",", ""))
                except:
                    pass
            
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