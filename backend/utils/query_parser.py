"""
Deterministic Query Parser
Extracts price, rating, and other filters from natural language queries using regex patterns.
Provides fallback to ensure consistent parameter extraction regardless of LLM variability.
"""

import re
from typing import Dict, Any, Optional, Tuple


class QueryParser:
    """Parse search queries to extract structured parameters deterministically"""

    def __init__(self):
        # Price patterns - ordered by specificity
        self.price_patterns = [
            # Range patterns: "from X to Y", "between X and Y", "X-Y"
            (r'(?:from|between)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:to|and|-)\s*\$?\s*(\d+(?:\.\d+)?)', 'range'),
            # Standalone range: "30-35 dollars" or "$30-$35"
            (r'\$?\s*(\d+(?:\.\d+)?)\s*-\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars?|bucks?|\$)', 'range'),
            # Under/less than: "under $50", "less than 100 dollars"
            (r'(?:under|below|less\s+than|cheaper\s+than)\s*\$?\s*(\d+(?:\.\d+)?)', 'max'),
            # Over/more than: "over $50", "more than 100 dollars"
            (r'(?:over|above|more\s+than|greater\s+than)\s*\$?\s*(\d+(?:\.\d+)?)', 'min'),
            # Around/about: "around $50", "about 100 dollars"
            (r'(?:around|about|approximately)\s*\$?\s*(\d+(?:\.\d+)?)', 'around'),
            # Direct price: "$50", "50 dollars"
            (r'\$\s*(\d+(?:\.\d+)?)', 'direct'),
            (r'(\d+(?:\.\d+)?)\s*(?:dollars?|bucks?|\$)', 'direct'),
        ]

        # Rating patterns
        self.rating_patterns = [
            # "4+ stars", "4 stars and up"
            (r'(\d(?:\.\d+)?)\s*\+?\s*stars?', 'min'),
            # "4 star and up", "at least 4 stars"
            (r'(?:at\s+least|minimum)\s*(\d(?:\.\d+)?)\s*stars?', 'min'),
            # "5 star only", "only 5 stars"
            (r'(?:only|exactly)\s*(\d(?:\.\d+)?)\s*stars?', 'exact'),
            # "highly rated", "top rated" -> implicit 4+
            (r'(?:highly|top|best)\s+rated', 'high'),
        ]

        # Sorting keywords
        self.sort_keywords = {
            'cheapest': 'price_low_to_high',
            'lowest price': 'price_low_to_high',
            'budget': 'price_low_to_high',
            'affordable': 'price_low_to_high',
            'most expensive': 'price_high_to_low',
            'highest price': 'price_high_to_low',
            'premium': 'price_high_to_low',
            'luxury': 'price_high_to_low',
            'best rated': 'rating',
            'top rated': 'rating',
            'highest rating': 'rating',
            'most reviewed': 'popular',
            'popular': 'popular',
            'best selling': 'popular',
        }

        # Gender detection - ENHANCED with family relationships
        self.gender_keywords = {
            'male': ['men', "men's", 'man', 'male', 'boy', 'boys', 'husband', 'father', 'dad', 'brother', 'son', 'boyfriend', 'grandpa', 'grandfather', 'uncle', 'nephew', 'him', 'his'],
            'female': ['women', "women's", 'woman', 'female', 'girl', 'girls', 'ladies', 'lady', 'wife', 'mother', 'mom', 'sister', 'daughter', 'girlfriend', 'grandma', 'grandmother', 'aunt', 'niece', 'her']
        }

        # Follow-up keywords - detect when user wants more of same type
        self.followup_keywords = [
            'more', 'another', 'next', 'different', 'else', 'other', 'similar',
            'show more', 'give me more', 'any other', 'something else', 'additional'
        ]

        # Category keywords for context extraction
        self.category_keywords = {
            'bags': ['bag', 'bags', 'backpack', 'purse', 'handbag', 'tote', 'satchel', 'messenger'],
            'jewelry': ['jewelry', 'jewellery', 'necklace', 'bracelet', 'ring', 'earring', 'watch', 'watches', 'chain', 'pendant', 'accessories', 'accessory', 'cufflink', 'tie clip'],
            'shoes': ['shoe', 'shoes', 'sneaker', 'sneakers', 'boot', 'boots', 'sandal', 'sandals', 'loafer', 'loafers'],
            'clothing': ['shirt', 'shirts', 'pants', 'jeans', 'dress', 'dresses', 'jacket', 'jackets', 'coat', 'sweater', 'hoodie', 'sweatshirt']
        }

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a query and extract all structured parameters.

        Returns:
            Dict with keys: normalized_query, min_price, max_price, min_rating,
                          sort_by, gender, price_range_detected, rating_detected
        """
        query_lower = query.lower().strip()
        result = {
            'original_query': query,
            'normalized_query': query_lower,
            'min_price': None,
            'max_price': None,
            'min_rating': None,
            'sort_by': None,
            'gender': None,
            'price_range_detected': False,
            'rating_detected': False,
            'clean_query': query_lower,  # Query with price/rating terms removed
        }

        # Extract price information
        price_info = self._extract_price(query_lower)
        if price_info:
            result.update(price_info)
            result['price_range_detected'] = True

        # Extract rating information
        rating_info = self._extract_rating(query_lower)
        if rating_info:
            result.update(rating_info)
            result['rating_detected'] = True

        # Detect sort preference
        sort_by = self._detect_sort(query_lower)
        if sort_by:
            result['sort_by'] = sort_by

        # Detect gender
        gender = self._detect_gender(query_lower)
        if gender:
            result['gender'] = gender

        # Generate clean query (remove price/rating terms for better semantic search)
        result['clean_query'] = self._clean_query(query_lower)

        # Normalize query for cache key
        result['normalized_query'] = self._normalize_for_cache(result)

        return result

    def _extract_price(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract price range from query"""
        for pattern, pattern_type in self.price_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if pattern_type == 'range':
                    min_val = float(match.group(1))
                    max_val = float(match.group(2))
                    return {'min_price': min_val, 'max_price': max_val}
                elif pattern_type == 'max':
                    return {'max_price': float(match.group(1))}
                elif pattern_type == 'min':
                    return {'min_price': float(match.group(1))}
                elif pattern_type == 'around':
                    price = float(match.group(1))
                    # "around $50" -> 40-60 range (±20%)
                    margin = price * 0.2
                    return {'min_price': price - margin, 'max_price': price + margin}
                elif pattern_type == 'direct':
                    # For direct mentions, check context
                    price = float(match.group(1))
                    # If "under" or "less" appears near the price
                    context = query[max(0, match.start()-20):match.end()+20]
                    if any(word in context for word in ['under', 'less', 'below', 'cheaper']):
                        return {'max_price': price}
                    elif any(word in context for word in ['over', 'more', 'above', 'greater']):
                        return {'min_price': price}
                    # Default: exact price as max (show things up to this price)
                    return {'max_price': price}
        return None

    def _extract_rating(self, query: str) -> Optional[Dict[str, Any]]:
        """Extract rating requirement from query"""
        for pattern, pattern_type in self.rating_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if pattern_type == 'high':
                    # "highly rated" -> 4+ stars
                    return {'min_rating': 4.0}
                elif pattern_type == 'exact':
                    rating = float(match.group(1))
                    return {'min_rating': rating}
                elif pattern_type == 'min':
                    rating = float(match.group(1))
                    return {'min_rating': rating}
        return None

    def _detect_sort(self, query: str) -> Optional[str]:
        """Detect sorting preference from query"""
        for keyword, sort_value in self.sort_keywords.items():
            if keyword in query:
                return sort_value
        return None

    def _detect_gender(self, query: str) -> Optional[str]:
        """Detect gender preference from query with word boundary matching"""
        # Sort keywords by length (longest first) to prioritize specific matches
        all_matches = []

        for gender, keywords in self.gender_keywords.items():
            for kw in keywords:
                # FIX: Use word boundaries for ALL words to prevent false matches
                # Examples: "he" in "her", "men" in "recommend", "man" in "woman"
                # Always use word boundaries for reliable matching
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, query):
                    all_matches.append((gender, len(kw), kw))

        # If multiple matches, prioritize:
        # 1. Longer keywords (more specific)
        # 2. Family relationships over generic terms
        if all_matches:
            # Sort by keyword length (descending) - longer = more specific
            all_matches.sort(key=lambda x: x[1], reverse=True)
            return all_matches[0][0]

        return None

    def _clean_query(self, query: str) -> str:
        """
        Remove price and rating terms from query to get clean product search terms.
        Example: "watch from 30 to 35 dollars" -> "watch"
        """
        clean = query

        # Remove price phrases
        price_remove_patterns = [
            r'(?:from|between)\s*\$?\s*\d+(?:\.\d+)?\s*(?:to|and|-)\s*\$?\s*\d+(?:\.\d+)?(?:\s*(?:dollars?|bucks?|\$))?',
            r'(?:under|below|less\s+than|cheaper\s+than|over|above|more\s+than|greater\s+than)\s*\$?\s*\d+(?:\.\d+)?(?:\s*(?:dollars?|bucks?|\$))?',
            r'(?:around|about|approximately)\s*\$?\s*\d+(?:\.\d+)?(?:\s*(?:dollars?|bucks?|\$))?',
            r'\$\s*\d+(?:\.\d+)?(?:\s*(?:dollars?|bucks?|\$))?',
            r'\d+(?:\.\d+)?\s*(?:dollars?|bucks?|\$)',
        ]

        for pattern in price_remove_patterns:
            clean = re.sub(pattern, ' ', clean, flags=re.IGNORECASE)

        # Remove rating phrases
        rating_remove_patterns = [
            r'\d(?:\.\d+)?\s*\+?\s*stars?(?:\s+and\s+up)?',
            r'(?:at\s+least|minimum|only|exactly)\s*\d(?:\.\d+)?\s*stars?',
            r'(?:highly|top|best)\s+rated',
        ]

        for pattern in rating_remove_patterns:
            clean = re.sub(pattern, ' ', clean, flags=re.IGNORECASE)

        # Remove sort keywords
        for keyword in self.sort_keywords.keys():
            clean = clean.replace(keyword, ' ')

        # Clean up whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()

        return clean

    def _normalize_for_cache(self, parsed: Dict[str, Any]) -> str:
        """
        Create a normalized query string for cache key generation.
        Ensures that similar queries generate the same cache key.
        """
        parts = []

        # Add clean query (product type)
        parts.append(parsed['clean_query'].strip())

        # Add price range in consistent format
        if parsed['min_price'] is not None:
            parts.append(f"minprice:{parsed['min_price']}")
        if parsed['max_price'] is not None:
            parts.append(f"maxprice:{parsed['max_price']}")

        # Add rating
        if parsed['min_rating'] is not None:
            parts.append(f"minrating:{parsed['min_rating']}")

        # Add sort
        if parsed['sort_by']:
            parts.append(f"sort:{parsed['sort_by']}")

        # Add gender
        if parsed['gender']:
            parts.append(f"gender:{parsed['gender']}")

        return '||'.join(parts)

    def suggest_limit(self, parsed: Dict[str, Any]) -> int:
        """
        Suggest appropriate search limit based on query complexity.
        Price/rating queries need more results for filtering.
        """
        if parsed['price_range_detected'] or parsed['rating_detected']:
            return 30  # Need more results for price/rating filtering
        return 15  # Default

    def is_followup_query(self, query: str) -> bool:
        """
        Detect if query is a follow-up request for more products.
        Examples: "2 more", "show more", "another", "next"
        """
        query_lower = query.lower().strip()

        # Check for number + keyword pattern (e.g., "2 more", "3 more")
        if re.search(r'\d+\s+(?:more|another|other)', query_lower):
            return True

        # Check for followup keywords
        for keyword in self.followup_keywords:
            if keyword in query_lower:
                return True

        # Check if query is very short and vague (likely follow-up)
        if len(query_lower.split()) <= 3 and any(kw in query_lower for kw in ['more', 'another', 'next']):
            return True

        return False

    def extract_category_from_query(self, query: str) -> Optional[str]:
        """
        Extract product category from query with prioritization.
        Returns: 'bags', 'jewelry', 'shoes', 'clothing', or None

        Prioritization strategy:
        1. Specific product names (dress, shoe, bag) override generic terms (accessory)
        2. Longer keywords are more specific
        3. Category priority: clothing > shoes > bags > jewelry
        """
        query_lower = query.lower()

        # Collect all matching categories with their matching keywords
        category_matches = []

        # Define specificity scores (higher = more specific product type)
        specificity_scores = {
            # Specific product types (highest priority)
            'dress': 10, 'dresses': 10,
            'shoe': 10, 'shoes': 10, 'sneaker': 10, 'sneakers': 10, 'boot': 10, 'boots': 10,
            'bag': 10, 'bags': 10, 'backpack': 10, 'purse': 10, 'handbag': 10,
            'shirt': 10, 'shirts': 10, 'pants': 10, 'jeans': 10,
            'jacket': 10, 'jackets': 10, 'coat': 10, 'sweater': 10, 'hoodie': 10,

            # Specific jewelry types (medium priority)
            'necklace': 8, 'bracelet': 8, 'ring': 8, 'earring': 8,
            'watch': 8, 'watches': 8, 'chain': 8, 'pendant': 8,

            # Generic terms (lowest priority)
            'accessories': 3, 'accessory': 3,
            'jewelry': 5, 'jewellery': 5,
            'clothing': 5,
        }

        for category, keywords in self.category_keywords.items():
            matching_keywords = [kw for kw in keywords if kw in query_lower]
            if matching_keywords:
                # Calculate score: specificity + keyword length
                best_keyword = max(matching_keywords,
                                 key=lambda kw: (specificity_scores.get(kw, 1), len(kw)))
                best_score = specificity_scores.get(best_keyword, 1)
                category_matches.append((category, best_score, len(best_keyword), best_keyword))

        if not category_matches:
            return None

        # Sort by: specificity score (desc), then keyword length (desc), then category priority
        category_priority = {'clothing': 0, 'shoes': 1, 'bags': 2, 'jewelry': 3}

        category_matches.sort(key=lambda x: (
            -x[1],  # Specificity score (higher is better)
            -x[2],  # Keyword length (longer is better)
            category_priority.get(x[0], 99)  # Category priority
        ))

        return category_matches[0][0]

    def extract_followup_count(self, query: str) -> Optional[int]:
        """
        Extract number from follow-up query.
        Examples: "2 more" → 2, "show me 3 more" → 3
        """
        match = re.search(r'(\d+)\s+(?:more|another|other)', query.lower())
        if match:
            return int(match.group(1))
        return None


# Singleton instance
_parser = QueryParser()


def parse_query(query: str) -> Dict[str, Any]:
    """Parse a query and extract structured parameters"""
    return _parser.parse_query(query)


def is_followup_query(query: str) -> bool:
    """Check if query is a follow-up request"""
    return _parser.is_followup_query(query)


def extract_category(query: str) -> Optional[str]:
    """Extract product category from query"""
    return _parser.extract_category_from_query(query)


def extract_followup_count(query: str) -> Optional[int]:
    """Extract count from follow-up query (e.g., '2 more' → 2)"""
    return _parser.extract_followup_count(query)


def get_parser() -> QueryParser:
    """Get the singleton parser instance"""
    return _parser
