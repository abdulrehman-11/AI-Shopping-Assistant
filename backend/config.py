import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    
    # Database
    NEON_HOST = os.getenv("NEON_HOST")
    NEON_DB = os.getenv("NEON_DB")
    NEON_USER = os.getenv("NEON_USER")
    NEON_PASSWORD = os.getenv("NEON_PASSWORD")
    
    # Vector DB
    PINECONE_INDEX = os.getenv("PINECONE_INDEX")
    
    # Cache
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # LLM Settings
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    MAX_CONTEXT_MESSAGES = 10
    
    # Search Settings
    MAX_SEARCH_RESULTS = 5
    SIMILARITY_THRESHOLD = 0.7

# Validate required environment variables
required_vars = [
    "GEMINI_API_KEY", "PINECONE_API_KEY", "COHERE_API_KEY",
    "NEON_HOST", "NEON_DB", "NEON_USER", "NEON_PASSWORD", "PINECONE_INDEX"
]

missing_vars = [var for var in required_vars if not getattr(Config, var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {missing_vars}")

def validate_db_connection():
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=Config.NEON_HOST,
            dbname=Config.NEON_DB,
            user=Config.NEON_USER,
            password=Config.NEON_PASSWORD,
            sslmode='require'
        )
        conn.close()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Test connection on import
if __name__ != "__main__":
    validate_db_connection()