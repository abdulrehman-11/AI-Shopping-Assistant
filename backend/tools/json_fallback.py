import json
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