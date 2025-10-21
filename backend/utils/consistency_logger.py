"""
Consistency Logger
Tracks parameter extraction and search results for consistency monitoring.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict


class ConsistencyLogger:
    """Log and track query parameter extraction for consistency analysis"""

    def __init__(self):
        self.extraction_log = []  # List of extraction events
        self.query_fingerprints = defaultdict(list)  # Track similar queries
        self.max_log_size = 1000  # Keep last 1000 entries in memory

    def log_extraction(
        self,
        session_id: str,
        original_query: str,
        parsed_params: Dict[str, Any],
        llm_params: Optional[Dict[str, Any]] = None,
        search_results_count: int = 0,
        final_products_count: int = 0
    ):
        """
        Log a parameter extraction event.

        Args:
            session_id: Session identifier
            original_query: Original user query
            parsed_params: Parameters extracted by QueryParser
            llm_params: Parameters extracted by LLM (optional)
            search_results_count: Number of results from search
            final_products_count: Number of products shown to user
        """
        timestamp = datetime.now().isoformat()
        query_fingerprint = self._get_query_fingerprint(original_query)

        log_entry = {
            'timestamp': timestamp,
            'session_id': session_id,
            'original_query': original_query,
            'query_fingerprint': query_fingerprint,
            'parsed_params': parsed_params,
            'llm_params': llm_params or {},
            'search_results_count': search_results_count,
            'final_products_count': final_products_count,
            'params_match': self._params_match(parsed_params, llm_params) if llm_params else None
        }

        # Add to main log
        self.extraction_log.append(log_entry)

        # Track by fingerprint for consistency analysis
        self.query_fingerprints[query_fingerprint].append(log_entry)

        # Trim log if too large
        if len(self.extraction_log) > self.max_log_size:
            self.extraction_log = self.extraction_log[-self.max_log_size:]

        # Print debug info
        self._print_debug(log_entry)

    def _get_query_fingerprint(self, query: str) -> str:
        """
        Generate a fingerprint for semantically similar queries.
        Normalizes query to group similar intents.
        """
        # Normalize: lowercase, remove extra spaces, basic cleaning
        normalized = query.lower().strip()
        normalized = ' '.join(normalized.split())  # Normalize whitespace

        # Remove common variations that don't change intent
        replacements = [
            ('dollars', '$'),
            ('dollar', '$'),
            ('bucks', '$'),
            (' to ', '-'),
            (' and ', '-'),
            ('from ', ''),
            ('give me ', ''),
            ('show me ', ''),
            ('find ', ''),
            ('i need ', ''),
            ('i want ', ''),
        ]

        for old, new in replacements:
            normalized = normalized.replace(old, new)

        # Generate hash for fingerprint
        return hashlib.md5(normalized.encode()).hexdigest()[:8]

    def _params_match(self, parsed: Dict[str, Any], llm: Optional[Dict[str, Any]]) -> Dict[str, bool]:
        """Check if parsed and LLM parameters match"""
        if not llm:
            return {}

        return {
            'min_price_match': parsed.get('min_price') == llm.get('min_price'),
            'max_price_match': parsed.get('max_price') == llm.get('max_price'),
            'min_rating_match': parsed.get('min_rating') == llm.get('min_rating'),
            'sort_by_match': parsed.get('sort_by') == llm.get('sort_by'),
        }

    def _print_debug(self, entry: Dict[str, Any]):
        """Print debug information for monitoring"""
        print(f"\n{'='*70}")
        print(f"📊 CONSISTENCY LOG [{entry['timestamp']}]")
        print(f"{'='*70}")
        print(f"Query: {entry['original_query']}")
        print(f"Fingerprint: {entry['query_fingerprint']}")
        print(f"\n🔍 Parsed Parameters:")
        print(f"   Min Price: {entry['parsed_params'].get('min_price')}")
        print(f"   Max Price: {entry['parsed_params'].get('max_price')}")
        print(f"   Min Rating: {entry['parsed_params'].get('min_rating')}")
        print(f"   Sort By: {entry['parsed_params'].get('sort_by')}")
        print(f"   Clean Query: {entry['parsed_params'].get('clean_query')}")

        if entry['llm_params']:
            print(f"\n🤖 LLM Parameters:")
            print(f"   Min Price: {entry['llm_params'].get('min_price')}")
            print(f"   Max Price: {entry['llm_params'].get('max_price')}")
            print(f"   Min Rating: {entry['llm_params'].get('min_rating')}")
            print(f"   Sort By: {entry['llm_params'].get('sort_by')}")

            if entry['params_match']:
                matches = entry['params_match']
                match_rate = sum(matches.values()) / len(matches) * 100 if matches else 0
                print(f"\n✓ Parameter Match Rate: {match_rate:.0f}%")

        print(f"\n📦 Results: {entry['search_results_count']} found → {entry['final_products_count']} shown")
        print(f"{'='*70}\n")

    def get_consistency_report(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a consistency report for a specific query or all queries.

        Returns statistics about parameter extraction consistency.
        """
        if query:
            fingerprint = self._get_query_fingerprint(query)
            entries = self.query_fingerprints.get(fingerprint, [])
        else:
            entries = self.extraction_log

        if not entries:
            return {'error': 'No data available'}

        # Calculate statistics
        total_queries = len(entries)
        queries_with_llm = sum(1 for e in entries if e['llm_params'])

        # Price extraction consistency
        parsed_prices = [e for e in entries if e['parsed_params'].get('min_price') or e['parsed_params'].get('max_price')]
        price_consistency = len(parsed_prices) / total_queries * 100 if total_queries > 0 else 0

        # Rating extraction consistency
        parsed_ratings = [e for e in entries if e['parsed_params'].get('min_rating')]
        rating_consistency = len(parsed_ratings) / total_queries * 100 if total_queries > 0 else 0

        # LLM vs Parsed match rate
        matches = [e for e in entries if e.get('params_match') and all(e['params_match'].values())]
        llm_match_rate = len(matches) / queries_with_llm * 100 if queries_with_llm > 0 else 0

        # Results consistency (same fingerprint should return similar counts)
        if query:
            result_counts = [e['final_products_count'] for e in entries]
            results_variance = self._calculate_variance(result_counts)
            results_consistent = results_variance < 2.0  # Low variance = consistent
        else:
            results_consistent = None
            results_variance = None

        report = {
            'total_queries': total_queries,
            'queries_with_llm_params': queries_with_llm,
            'price_extraction_rate': f"{price_consistency:.1f}%",
            'rating_extraction_rate': f"{rating_consistency:.1f}%",
            'llm_match_rate': f"{llm_match_rate:.1f}%",
            'results_consistent': results_consistent,
            'results_variance': results_variance,
            'sample_queries': [e['original_query'] for e in entries[:5]],
        }

        return report

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5  # Return standard deviation

    def get_query_history(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get extraction history for a specific query"""
        fingerprint = self._get_query_fingerprint(query)
        entries = self.query_fingerprints.get(fingerprint, [])
        return entries[-limit:]

    def export_log(self, filepath: str):
        """Export log to JSON file for analysis"""
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'extraction_log': self.extraction_log,
                    'fingerprint_groups': {k: v for k, v in self.query_fingerprints.items()},
                    'exported_at': datetime.now().isoformat()
                }, f, indent=2)
            print(f"✅ Log exported to {filepath}")
        except Exception as e:
            print(f"❌ Export failed: {e}")

    def clear_log(self):
        """Clear all logs"""
        self.extraction_log = []
        self.query_fingerprints = defaultdict(list)
        print("🗑️  Log cleared")


# Singleton instance
_logger = ConsistencyLogger()


def log_extraction(*args, **kwargs):
    """Log a parameter extraction event"""
    return _logger.log_extraction(*args, **kwargs)


def get_consistency_report(*args, **kwargs):
    """Get consistency report"""
    return _logger.get_consistency_report(*args, **kwargs)


def get_query_history(*args, **kwargs):
    """Get query history"""
    return _logger.get_query_history(*args, **kwargs)


def export_log(*args, **kwargs):
    """Export log"""
    return _logger.export_log(*args, **kwargs)


def get_logger() -> ConsistencyLogger:
    """Get the singleton logger instance"""
    return _logger
