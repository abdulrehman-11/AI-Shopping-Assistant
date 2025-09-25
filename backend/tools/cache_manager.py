import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.memory_cache = {}
        self.cache_duration = 300  # 5 minutes
    
    def _get_cache_key(self, query: str, filters: Dict = None) -> str:
        """Generate cache key from query and filters"""
        cache_data = {"query": query.lower().strip(), "filters": filters or {}}
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
    
    def cache_search_results(self, query: str, results: Dict, filters: Dict = None):
        """Cache search results"""
        cache_key = self._get_cache_key(query, filters)
        
        try:
            if self.redis:
                self.redis.setex(cache_key, self.cache_duration, json.dumps(results))
            else:
                self.memory_cache[cache_key] = (results, datetime.now())
                
                # Clean old entries
                if len(self.memory_cache) > 100:
                    oldest_key = min(self.memory_cache.keys(), 
                                   key=lambda k: self.memory_cache[k][1])
                    del self.memory_cache[oldest_key]
                    
        except Exception as e:
            print(f"Cache storage error: {e}")