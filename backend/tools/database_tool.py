import psycopg2
from typing import List, Dict, Any, Optional
from config import Config

class DatabaseTool:
    def __init__(self):
        self.connection_params = {
            'host': Config.NEON_HOST,
            'dbname': Config.NEON_DB,
            'user': Config.NEON_USER,
            'password': Config.NEON_PASSWORD,
            'sslmode': 'require'
        }
    
    def get_products_by_ids(self, asin_list: List[str]) -> List[Dict[str, Any]]:
        """Get full product details from database by ASIN list"""
        if not asin_list:
            return []
            
        try:
            conn = psycopg2.connect(**self.connection_params)
            cur = conn.cursor()
            
            # Create placeholders for IN clause
            placeholders = ','.join(['%s'] * len(asin_list))
            
            query = f"""
                SELECT asin, title, category, brand, stars, reviews_count, price_value
                FROM products 
                WHERE asin IN ({placeholders})
            """
            
            cur.execute(query, asin_list)
            rows = cur.fetchall()
            
            # Convert to dict format
            products = []
            for row in rows:
                products.append({
                    'asin': row[0],
                    'title': row[1],
                    'category': row[2],
                    'brand': row[3],
                    'stars': float(row[4]) if row[4] else None,
                    'reviews_count': int(row[5]) if row[5] else None,
                    'price_value': float(row[6]) if row[6] else None
                })
            
            cur.close()
            conn.close()
            
            return products
            
        except Exception as e:
            print(f"Database error: {e}")
            return []
    
    def get_product_by_id(self, asin: str) -> Optional[Dict[str, Any]]:
        """Get single product by ASIN"""
        products = self.get_products_by_ids([asin])
        return products[0] if products else None