import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.memory_cache = {}
        self.cache_duration = 300  # 5 minutes default
    
    def _get_cache_key(self, query: str, filters: Dict = None) -> str:
        """Generate cache key from query and filters - include ALL parameters"""
        # Make cache key more specific by including all filter values
        cache_data = {
            "query": query.lower().strip(), 
            "filters": filters or {}
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return f"search_cache:{hashlib.md5(cache_string.encode()).hexdigest()}"
    
    def get_cached_search(self, query: str, filters: Dict = None) -> Optional[Dict]:
        """Get cached search results"""
        cache_key = self._get_cache_key(query, filters)
        
        try:
            if self.redis:
                cached = self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            else:
                # Memory cache with expiration
                if cache_key in self.memory_cache:
                    cached_data, timestamp = self.memory_cache[cache_key]
                    if datetime.now() - timestamp < timedelta(seconds=self.cache_duration):
                        return cached_data
                    else:
                        del self.memory_cache[cache_key]
        except Exception as e:
            print(f"Cache retrieval error: {e}")
        
        return None
    
    def cache_search_results(self, query: str, results: Dict, filters: Dict = None, ttl: Optional[int] = None):
        """Cache search results with optional TTL"""
        cache_key = self._get_cache_key(query, filters)
        
        # Use provided TTL or default
        duration = int(ttl) if ttl is not None else self.cache_duration
        
        try:
            if self.redis:
                self.redis.setex(cache_key, duration, json.dumps(results))
            else:
                self.memory_cache[cache_key] = (results, datetime.now())
                
                # Clean old entries
                if len(self.memory_cache) > 100:
                    # Remove oldest entries by timestamp
                    items = list(self.memory_cache.items())
                    items.sort(key=lambda x: x[1][1])  # Sort by timestamp
                    # Keep only newest 80
                    self.memory_cache = dict(items[-80:])
                    
        except Exception as e:
            print(f"Cache storage error: {e}")