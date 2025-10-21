"""
Simplified Intelligent Shopping Chatbot - FIXED VERSION
Properly handles product count, validation, and filtering
WITH DETERMINISTIC PARAMETER EXTRACTION
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
from utils.query_parser import parse_query, is_followup_query, extract_category, extract_followup_count
from utils.consistency_logger import log_extraction
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
   - **CRITICAL PRICE VALIDATION:** If user specifies price range (e.g., "50-100", "under $75"), ONLY select products within that EXACT range. NEVER select products outside the range, even if they appear in search results. Better to show 0 products than show wrong price products.
   - **CRITICAL GENDER VALIDATION:** If query mentions women/wife/her/mother/sister/ladies, ONLY select products with "women", "women's", "ladies", "lady" in title or category. REJECT any product containing "men", "men's", "male", "for men" in title/category.
   - **CRITICAL GENDER VALIDATION:** If query mentions men/husband/him/father/brother, ONLY select products with "men", "men's", "male", "for men" in title or category. REJECT any product containing "women", "women's", "ladies", "female" in title/category.
   - Analyze EACH product for relevance to the query if not relevant please skip that product. Also don't need to provide their ASINs of irrelevant products
   - Intelligently select the most relevant products to show according to query + past context like brand, price, style, type, and GENDER
   - List only the specific selected ASINs you want to show
4. Use this EXACT format at the end of your response:
   SELECTED_PRODUCTS: [asin1, asin2, asin3, ...]
   (Include ONLY the ASINs of products you want to display)
5. If user asks for "shoes", search with pinecone, validate intelligently and never show irrelevant products like here socks or other non-shoe items are irrelevant.
6. If user asks for "watches", NEVER show bracelets or other non-watch items
7. **GENDER IS CRITICAL:** Better to show 0 products than show wrong gender products. If search returns men's products for women's query, DO NOT select them.
8. **PRICE IS CRITICAL:** If user specifies price range, showing products outside that range is WRONG. Always verify product price matches user's requested range.

**Conversation Guidelines:**

1. **Natural Understanding:**
   - Understand user intent from context, not just current message
   - Handle follow-ups intelligently (e.g., "show me more", "cheaper ones", "Nike brand")
   - Handle follow up understanding what was the prefernce of user in prevous chat that user wont types now, For eg, IF earlier user say show cheapest [shoes], then in next query user say some query for same product then you need to understand that user want cheapest but with now specific etc. Do this for thing like price, rating, number of shoes to display, etc
   - Handle spelling mistakes and typos
   - **CRITICAL GENDER DETECTION:**
     * "for my wife/mother/sister/girlfriend/her" = WOMEN'S products ONLY
     * "for my husband/father/brother/boyfriend/him" = MEN'S products ONLY
     * "accessories for my wife" = Women's accessories (NOT men's cufflinks/ties)
     * Gender context persists across queries until explicitly changed
     * NEVER show men's products when user asked for wife/mother/sister
     * NEVER show women's products when user asked for husband/father/brother
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

7. **Show More Logic (CRITICAL FOR FOLLOW-UPS):**
   - If user says "show more", "next", "other options", "2 more", understand they want additional products
   - **MUST** use conversation history to understand WHAT CATEGORY they were looking at
   - Examples:
     * Previous: showed jewelry → "2 more" → Search for 2 more jewelry items
     * Previous: showed men's bags → "show more" → Search for more men's bags
     * Previous: showed women's shoes → "another" → Search for another women's shoe
   - **INHERIT GENDER** from previous query:
     * If previous was for "wife" → continue showing women's products
     * If previous was for "husband" → continue showing men's products
   - Search with increased offset to avoid showing duplicates
   - Track previously shown products (ASINs) to avoid repeats
   - "2 more" means show EXACTLY 2 products, not 5

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
□ **CRITICAL**: If price range specified (e.g., 50-100), is product price within that EXACT range? Reject products with price < min or price > max, even by $0.01.
□ If price/rating mentioned, does product meet criteria?, For prices and ratings make sure that thoose products whose price/rating metadata is null/empty. Dont add them in search becuase user mention about price etc. IF you even found some product with no price/rating metadata, skip that product, And dont even write them into message that you found some but there price are nnot available etc
□ IF no relevant products, is it better to say "we don't have that would you try to search something [some related one]" and dont even send ASIN to frontend for unchoosed or rejected product, ?

**Remember:** Quality over quantity. Show fewer relevant products rather than including irrelevant ones. NEVER show products outside user's specified price range."""

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

            # IMPROVED: Use normalized cache key based on query parser
            parsed_query = parse_query(query)
            cache_key = f"{parsed_query['normalized_query']}_{offset}"
            print(f"🔑 Cache key: {cache_key}")

            # FIX: Include price parameters in cache to prevent wrong cached results
            cache_filters = {**filters}
            if min_price is not None:
                cache_filters['min_price'] = min_price
            if max_price is not None:
                cache_filters['max_price'] = max_price

            cached = self.cache_manager.get_cached_search(cache_key, cache_filters)
            
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

            # FIX: Apply price filtering to BOTH cached and fresh results
            # This ensures cached results are validated even if cache key includes price
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

            # Cohere Rerank with gender-aware documents (apply to both cached and fresh)
            if len(products) > 1:
                try:
                    # Detect gender from query for reranking context
                    query_lower = query.lower()
                    gender_context = None
                    if any(kw in query_lower for kw in ["women", "women's", "ladies", "lady", "female", "her"]):
                        gender_context = "women's"
                    elif any(kw in query_lower for kw in ["men", "men's", "male", "him", "man's"]):
                        gender_context = "men's"

                    # Build reranking documents with gender context
                    if gender_context:
                        docs = [
                            f"{gender_context} {p.get('title', '')} {p.get('brand', '')} {p.get('category', '')} ${p.get('price_value', 0)}"
                            for p in products
                        ]
                        print(f"👫 Gender-aware reranking with context: {gender_context}")
                    else:
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

                    # POST-RERANK GENDER FILTERING
                    if gender_context:
                        gender_filtered = []

                        for p in products:
                            title_lower = p.get('title', '').lower()
                            category_lower = p.get('category', '').lower()

                            if gender_context == "women's":
                                # Check for women's keywords
                                has_female = any(kw in title_lower or kw in category_lower
                                               for kw in ['women', "women's", 'ladies', 'lady', 'her', 'female', 'girl'])
                                # Check for men's keywords (exclude if found)
                                has_male = any(kw in title_lower or kw in category_lower
                                             for kw in ['men', "men's", 'male', 'him', 'boy', "man's", ' for men'])

                                # Include if has female keywords OR doesn't have male keywords
                                if has_female or not has_male:
                                    gender_filtered.append(p)

                            elif gender_context == "men's":
                                # Check for men's keywords
                                has_male = any(kw in title_lower or kw in category_lower
                                             for kw in ['men', "men's", 'male', 'him', 'boy', "man's", ' for men'])
                                # Check for women's keywords (exclude if found)
                                has_female = any(kw in title_lower or kw in category_lower
                                               for kw in ['women', "women's", 'ladies', 'lady', 'her', 'female', 'girl'])

                                # Include if has male keywords OR doesn't have female keywords
                                if has_male or not has_female:
                                    gender_filtered.append(p)

                        products = gender_filtered
                        print(f"👫 Gender filtered ({gender_context}): {len(products)} products remain")

                except Exception as e:
                    print(f"⚠️ Reranking failed: {e}")

            # Apply sorting AFTER filtering (apply to both cached and fresh)
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

            # Cache results only for fresh searches (with shorter TTL for price queries)
            if not cached and not offset:
                ttl = 60 if is_price_query else 180
                self.cache_manager.cache_search_results(
                    cache_key,
                    {"products": products, "total": len(products)},
                    cache_filters,  # Use cache_filters which includes price params
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
        """Main chat function with proper product selection + deterministic extraction"""
        print(f"\n{'='*60}")
        print(f"💬 User: {message}")
        print(f"🆔 Session: {session_id}")
        print(f"{'='*60}\n")

        try:
            # 1. DETERMINISTIC PARAMETER EXTRACTION
            parsed_params = parse_query(message)
            print(f"🎯 Parsed Parameters:")
            print(f"   Clean Query: {parsed_params['clean_query']}")
            print(f"   Price Range: {parsed_params['min_price']} - {parsed_params['max_price']}")
            print(f"   Min Rating: {parsed_params['min_rating']}")
            print(f"   Sort By: {parsed_params['sort_by']}")
            print(f"   Gender: {parsed_params.get('gender')}")
            print(f"   Normalized: {parsed_params['normalized_query']}\n")

            # 2. DETECT FOLLOW-UP QUERIES AND ENRICH WITH CONTEXT
            is_followup = is_followup_query(message)
            last_context = self.session_manager.get_last_search_context(session_id)

            if is_followup:
                print(f"🔄 FOLLOW-UP DETECTED!")
                print(f"   Last Category: {last_context['last_category']}")
                print(f"   Last Gender: {last_context['last_gender']}")

                # Extract category from current query or use last
                current_category = extract_category(message)
                if not current_category and last_context['last_category']:
                    print(f"   → Injecting last category: {last_context['last_category']}")
                    # For follow-ups, REPLACE query with category (don't append follow-up text like "2 more?")
                    parsed_params['clean_query'] = last_context['last_category']

                # Inherit gender if not specified
                if not parsed_params.get('gender') and last_context['last_gender']:
                    print(f"   → Inheriting gender: {last_context['last_gender']}")
                    parsed_params['gender'] = last_context['last_gender']

                # Extract count for "2 more", etc.
                followup_count = extract_followup_count(message)
                if followup_count:
                    print(f"   → User wants {followup_count} more items")
                    parsed_params['requested_count'] = followup_count

            # 3. INHERIT GENDER FROM CONVERSATION HISTORY if not in current query
            if not parsed_params.get('gender'):
                preferences = self.session_manager.get_user_preferences(session_id)
                if preferences.get('gender'):
                    print(f"👤 Inheriting gender from history: {preferences['gender']}")
                    parsed_params['gender'] = preferences['gender']

            # 4. Add user message to session
            self.session_manager.add_message(session_id, MessageRole.USER, message)

            # 5. Get conversation history (FILTERED for relevance)
            session = self.session_manager.get_session(session_id)
            history_messages = self._format_history_for_llm_filtered(session.messages[-20:])

            # 4. Prepare messages for LLM
            messages = [
                SystemMessage(content=self.system_prompt),
                *history_messages,
                HumanMessage(content=message)
            ]

            # 5. Create search tool with pre-filled parameters
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
            
            # 6. Handle tool calls
            all_products = []
            llm_params = {}

            while response.tool_calls:
                print(f"🔧 Tool calls detected: {len(response.tool_calls)}")

                for tool_call in response.tool_calls:
                    if tool_call['name'] == 'search_products':
                        # Capture LLM-extracted parameters
                        llm_params = tool_call['args'].copy()
                        print(f"🤖 LLM extracted parameters: {llm_params}")

                        # MERGE: Combine parsed params with LLM params (parsed takes priority if present)
                        # Determine appropriate limit based on query complexity
                        suggested_limit = 30 if (parsed_params.get('price_range_detected') or parsed_params.get('rating_detected')) else 15

                        # FIX: Build query with gender prefix if gender detected
                        # For follow-ups, ALWAYS use our pre-processed query (with injected category)
                        # Don't let LLM override it with wrong interpretation
                        if is_followup and parsed_params.get('clean_query'):
                            base_query = parsed_params['clean_query']  # Use our injected category
                            print(f"   → Using pre-processed follow-up query: '{base_query}'")
                        else:
                            base_query = llm_params.get('query', parsed_params.get('clean_query', message))

                        search_query = base_query

                        if parsed_params.get('gender'):
                            gender = parsed_params['gender']
                            # Convert gender to search prefix: "male" → "men's", "female" → "women's"
                            gender_prefix = "men's" if gender == "male" else "women's" if gender == "female" else gender

                            # Only add gender prefix if not already in query
                            if gender_prefix.lower() not in base_query.lower() and gender.lower() not in base_query.lower():
                                search_query = f"{gender_prefix} {base_query}".strip()
                                print(f"👫 Adding gender to query: '{base_query}' → '{search_query}'")

                        # FIX: Use requested_count if user said "2 more", "3 more", etc.
                        final_limit = parsed_params.get('requested_count') or llm_params.get('limit', suggested_limit)

                        merged_params = {
                            'query': search_query,  # Now includes gender prefix
                            'min_price': parsed_params.get('min_price') or llm_params.get('min_price'),
                            'max_price': parsed_params.get('max_price') or llm_params.get('max_price'),
                            'min_rating': parsed_params.get('min_rating') or llm_params.get('min_rating'),
                            'sort_by': parsed_params.get('sort_by') or llm_params.get('sort_by'),
                            'limit': final_limit,  # Now respects requested_count
                            'offset': llm_params.get('offset', 0),
                        }

                        print(f"🔀 Merged parameters: {merged_params}")

                        # Execute search with merged parameters
                        result = self._search_products_impl(**merged_params)
                        result_data = json.loads(result)
                        all_products = result_data.get('products', [])

                        # FIX: Filter out products already shown in previous queries (for follow-ups)
                        if is_followup:
                            shown_asins_set = set(last_context.get('shown_asins', []))
                            if shown_asins_set:
                                original_count = len(all_products)
                                all_products = [p for p in all_products if p.get('asin') not in shown_asins_set]
                                filtered_count = original_count - len(all_products)
                                if filtered_count > 0:
                                    print(f"🔁 Filtered {filtered_count} duplicate products from previous queries")

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

            # 11. UPDATE SESSION CONTEXT FOR NEXT QUERY
            if products_to_show:
                # FIX: Only detect category from user's query, NOT from product titles
                # Product titles can be misleading (e.g., "accessory" in dress titles → jewelry category)
                detected_category = extract_category(message)

                # Get current shown ASINs
                shown_asins = [p.get('asin') for p in products_to_show if p.get('asin')]

                # FIX: For follow-ups, accumulate shown_asins; for new searches, reset
                if is_followup:
                    # Append to existing shown ASINs (avoid showing same products again)
                    existing_asins = last_context.get('shown_asins', [])
                    shown_asins = existing_asins + shown_asins
                    print(f"🔁 Accumulating shown ASINs: {len(existing_asins)} previous + {len([p.get('asin') for p in products_to_show if p.get('asin')])} new = {len(shown_asins)} total")
                else:
                    # New search - reset shown ASINs
                    print(f"🆕 New search - resetting shown ASINs: {len(shown_asins)} products")

                self.session_manager.update_search_context(
                    session_id=session_id,
                    category=detected_category,
                    gender=parsed_params.get('gender'),
                    min_price=parsed_params.get('min_price'),
                    max_price=parsed_params.get('max_price'),
                    product_count=len(products_to_show),
                    shown_asins=shown_asins
                )
                print(f"💾 Updated session context: category={detected_category}, gender={parsed_params.get('gender')}")

            # 12. LOG EXTRACTION FOR CONSISTENCY TRACKING
            log_extraction(
                session_id=session_id,
                original_query=message,
                parsed_params=parsed_params,
                llm_params=llm_params,
                search_results_count=len(all_products),
                final_products_count=len(products_to_show)
            )

            # 13. Return response
            return {
                "response": response_text,
                "products": products_to_show,
                "ui_products": ui_products,
                "needs_clarification": False,
                "clarification_questions": [],
                "search_metadata": {
                    "total_found": len(all_products),
                    "shown": len(products_to_show),
                    "search_query": message,
                    "parsed_params": parsed_params,
                    "llm_params": llm_params
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

    def _format_history_for_llm_filtered(self, messages: List) -> List:
        """
        Convert session messages to LLM format, FILTERING out off-topic messages.
        Keeps only product-related conversations to avoid context contamination.
        """
        # Keywords that indicate off-topic queries
        off_topic_keywords = [
            'what is', 'how to', 'why', 'when', 'where',
            'calculate', 'math', 'equation', '+', '=',
            'skydiving', 'recipe', 'weather', 'news',
            'tell me about', 'explain', 'define'
        ]

        # Product-related keywords
        product_keywords = [
            'show', 'find', 'search', 'get', 'give', 'recommend',
            'need', 'want', 'looking for', 'buy', 'purchase',
            'bag', 'shoe', 'watch', 'jewelry', 'clothing',
            'accessories', 'more', 'another', 'different',
            'price', 'cheap', 'expensive', 'dollar', '$',
            'wife', 'husband', 'mother', 'father', 'gift'
        ]

        formatted = []
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else str(msg)
            role = msg.role if hasattr(msg, 'role') else 'user'
            content_lower = content.lower()

            # Filter out off-topic user messages
            if role == MessageRole.USER or role == 'user':
                # Check if message is off-topic
                is_offtopic = any(kw in content_lower for kw in off_topic_keywords)
                is_product_related = any(kw in content_lower for kw in product_keywords)

                # Skip if clearly off-topic and not product-related
                if is_offtopic and not is_product_related:
                    print(f"🚫 Filtering off-topic message: {content[:50]}...")
                    continue

                formatted.append(HumanMessage(content=content))

            elif role == MessageRole.ASSISTANT or role == 'assistant':
                # Keep assistant messages (they contain product context)
                formatted.append(AIMessage(content=content))

        # Keep only last 10 messages to avoid overwhelming context
        return formatted[-10:]
    
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