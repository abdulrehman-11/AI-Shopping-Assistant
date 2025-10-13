import json
import os
from typing import List, Dict, Any, Optional

class JsonFallbackTool:
    """Fallback tool to enrich product data from JSON when ASIN info is missing from Pinecone/DB"""
    
    def __init__(self, json_file_path: str = "../src/data/products.json"):
        self.products_data = {}
        self.load_json_data(json_file_path)
    
    def load_json_data(self, file_path: str):
        """Load and index products by ASIN"""
        try:
            # Try multiple possible paths
            possible_paths = [
                file_path,
                "src/data/products.json",
                "../src/data/products.json",
                "data/products.json"
            ]
            
            data = None
            for path in possible_paths:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✅ Loaded JSON fallback data from {path}")
                        break
                except FileNotFoundError:
                    continue
            
            if not data:
                print("⚠️ Could not load JSON fallback data - will work without it")
                return
            
            # Index by ASIN for fast lookup
            for product in data:
                asin = product.get('asin')
                if asin:
                    self.products_data[asin] = product
                    
            print(f"📊 Indexed {len(self.products_data)} products for fallback")
            
        except Exception as e:
            print(f"JSON fallback loading error: {e}")
    
    def enrich_products(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich product list with JSON data where information is missing"""
        if not self.products_data:
            return products
        
        enriched = []
        
        for product in products:
            asin = product.get('asin')
            if not asin:
                enriched.append(product)
                continue
            
            json_product = self.products_data.get(asin)
            if not json_product:
                enriched.append(product)
                continue
            
            # Create enriched product by merging vector/DB data with JSON data
            enriched_product = product.copy()
            
            # Fill missing fields from JSON
            field_mappings = {
                'title': 'title',
                'category': 'category', 
                'brand': 'brand',
                'stars': 'stars',
                'reviews_count': 'reviews_count',
                'price_value': 'price.value',
                'image_url': 'image',
                'url': 'url',
                'description': 'description'
            }
            
            for product_field, json_path in field_mappings.items():
                # Only fill if the field is missing or empty
                if not enriched_product.get(product_field):
                    json_value = self._get_nested_value(json_product, json_path)
                    if json_value is not None:
                        enriched_product[product_field] = json_value
            
            # Add additional fields from JSON that might be useful
            if 'thumbnailImage' in json_product:
                enriched_product['thumbnail_image'] = json_product['thumbnailImage']
            
            enriched.append(enriched_product)
        
        return enriched
    
    def filter_and_sort_by_criteria(
        self,
        products: List[Dict],
        query: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        sort_by: Optional[str] = None
    ) -> List[Dict]:
        """
        Post-process products with strict price/rating filtering from JSON data
        """
        if not products:
            return products

        # Detect if this is a price/rating focused query
        query_lower = query.lower()
        is_price_query = any(word in query_lower for word in ['cheap', 'expensive', 'price', 'budget', 'affordable', '$', 'dollar', 'under', 'between', 'less than', 'more than'])
        is_rating_query = any(word in query_lower for word in ['rating', 'rated', 'star', 'review', 'best', 'top', 'quality'])

        if not (is_price_query or is_rating_query or min_price or max_price or min_rating):
            return products  # Return as-is if not a price/rating query

        # Get ASINs from products and look up full data from the in-memory index
        asins = [p.get('asin') for p in products if p.get('asin')]
        enriched = []
        for asin in asins:
            full_product = self.products_data.get(asin)
            if not full_product:
                # If we don't have the ASIN in the in-memory index, skip
                continue

            # full_product found from indexed JSON
            if full_product:
                # Extract actual price value
                price_value = None
                if isinstance(full_product.get('price'), dict):
                    price_value = full_product['price'].get('value')
                elif full_product.get('price'):
                    try:
                        price_value = float(str(full_product['price']).replace('$', '').replace(',', ''))
                    except:
                        pass
                    
                # Apply strict filtering
                if min_price and price_value and price_value < min_price:
                    continue
                if max_price and price_value and price_value > max_price:
                    continue
                if min_rating and full_product.get('stars', 0) < min_rating:
                    continue
                
                # Merge with original product data (preserve rerank score)
                original = next((p for p in products if p.get('asin') == asin), {})
                full_product['rerank_score'] = original.get('rerank_score', 0)
                full_product['similarity_score'] = original.get('similarity_score', 0)
                full_product['price_value'] = price_value  # Add normalized price

                enriched.append(full_product)

        # Apply sorting based on query intent or explicit sort parameter
        if sort_by or is_price_query or is_rating_query:
            # Detect implicit sorting from query
            if not sort_by:
                if any(word in query_lower for word in ['cheapest', 'lowest price', 'budget']):
                    sort_by = 'price_low_to_high'
                elif any(word in query_lower for word in ['expensive', 'highest price', 'premium']):
                    sort_by = 'price_high_to_low'
                elif any(word in query_lower for word in ['best rated', 'highest rating', 'top rated']):
                    sort_by = 'rating'

            # Apply sorting
            if sort_by in ['price_low_to_high', 'cheapest']:
                enriched = sorted(enriched, key=lambda x: x.get('price_value') or 999999)
            elif sort_by in ['price_high_to_low', 'expensive']:
                enriched = sorted(enriched, key=lambda x: x.get('price_value') or 0, reverse=True)
            elif sort_by in ['rating', 'rating_high']:
                enriched = sorted(enriched, key=lambda x: (x.get('stars') or 0, x.get('reviewsCount') or 0), reverse=True)
            elif sort_by in ['popular', 'reviews']:
                enriched = sorted(enriched, key=lambda x: x.get('reviewsCount') or 0, reverse=True)
            else:
                # Default: balance between rerank score and criteria match
                enriched = sorted(enriched, key=lambda x: x.get('rerank_score', 0), reverse=True)

        return enriched if enriched else products  # Fallback to original if no matches
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value from dict using dot notation (e.g., 'price.value')"""
        try:
            keys = path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except:
            return None
    
    def search_by_keywords(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fallback search in JSON data using keywords (for emergency cases)"""
        if not self.products_data:
            return []
        
        query_lower = query.lower()
        matches = []
        
        for asin, product in self.products_data.items():
            score = 0
            
            # Check title
            title = str(product.get('title', '')).lower()
            if query_lower in title:
                score += 3
            
            # Check category
            category = str(product.get('category', '')).lower()
            if query_lower in category:
                score += 2
            
            # Check brand
            brand = str(product.get('brand', '')).lower()
            if query_lower in brand:
                score += 2
            
            # Check description
            description = str(product.get('description', '')).lower()
            if query_lower in description:
                score += 1
            
            if score > 0:
                product_copy = product.copy()
                product_copy['fallback_score'] = score
                matches.append(product_copy)
        
        # Sort by score and return top matches
        matches.sort(key=lambda x: x.get('fallback_score', 0), reverse=True)
        return matches[:limit]
    
    def get_product_by_asin(self, asin: str) -> Optional[Dict[str, Any]]:
        """Get single product by ASIN"""
        return self.products_data.get(asin)