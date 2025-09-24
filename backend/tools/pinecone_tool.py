from pinecone import Pinecone
import cohere
from typing import List, Dict, Any
from config import Config

class PineconeTool:
    def __init__(self):
        # Initialize Pinecone
        self.pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        self.index = self.pc.Index(Config.PINECONE_INDEX)
        
        # Initialize Cohere for embeddings
        self.co = cohere.Client(Config.COHERE_API_KEY)
    
    def search_similar_products(self, query: str, filters: Dict[str, Any] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar products using vector similarity"""
        try:
            # Generate embedding for search query
            response = self.co.embed(
                texts=[query],
                model="embed-english-light-v3.0",
                input_type="search_query"  # Different input type for queries
            )
            query_vector = response.embeddings[0]
            
            # Build Pinecone filter cautiously: avoid strict category equality which often mismatches
            pinecone_filter = None
            if filters:
                temp_filter: Dict[str, Any] = {}
                # Only keep numeric or exact-safe filters
                if 'min_stars' in filters and filters['min_stars'] is not None:
                    temp_filter['stars'] = {'$gte': float(filters['min_stars'])}
                if 'brand' in filters and filters['brand']:
                    temp_filter['brand'] = {'$eq': str(filters['brand'])}
                # Do NOT include category equality unless your index stores a normalized field
                pinecone_filter = temp_filter or None
            
            # Search in Pinecone
            search_results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=pinecone_filter
            )
            
            # Format and threshold results
            products = []
            for match in search_results.matches:
                product = {
                    'asin': match.id,
                    'similarity_score': float(match.score),
                    'title': match.metadata.get('title', ''),
                    'category': match.metadata.get('category', ''),
                    'brand': match.metadata.get('brand', ''),
                    'stars': match.metadata.get('stars', 0),
                    'reviews_count': match.metadata.get('reviews_count', 0),
                    'price_value': match.metadata.get('price_value', 0)
                }
                products.append(product)
            
            # Do not apply a hard threshold by default; return raw scored results
            
            return products
            
        except Exception as e:
            print(f"Pinecone search error: {e}")
            return []