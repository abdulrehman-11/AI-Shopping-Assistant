# E-commerce AI Shopping Assistant

An intelligent AI-powered shopping platform that combines semantic search, real-time product recommendations, and conversational AI to create a seamless shopping experience. Browse millions of Amazon products with natural language queries powered by Google's Gemini, Pinecone vector search, and Cohere reranking.

**Live Demo:** [https://ai-shopping-assistant-eight.vercel.app/](https://ai-shopping-assistant-eight.vercel.app/)

---

## What This Project Does

This is a full-stack e-commerce application that revolutionizes how users discover and shop for products. Instead of traditional category browsing or keyword-based search, users can have natural conversations with an AI assistant that understands their preferences, context, and intent.

### Key Capabilities

- **Conversational Shopping**: Ask for products in natural language like "Show me affordable Nike shoes" or "I need a leather bag under $100"
- **Context-Aware Search**: The AI remembers conversation history and understands follow-up requests like "Show me cheaper options"
- **Smart Product Ranking**: Results are reranked by AI to show the most relevant products first, not just keyword matches
- **Category Browsing**: Traditional category navigation with sorting and filtering options
- **Session Management**: Persistent conversation memory so your shopping context is maintained

---

## How It's Efficient

### Semantic Search Technology
- **Vector Embeddings**: Uses Cohere embeddings to convert product descriptions and user queries into semantic vectors
- **Pinecone Database**: Searches through vector space to find conceptually similar products, not just keyword matches
- **Intelligent Reranking**: Cohere's rerank model scores results based on relevance to user intent, ensuring top results are always the best matches

### Performance Optimizations
- **Caching**: Redis caching layer reduces redundant searches and API calls
- **Hybrid Search**: Combines vector search with price filtering and rating thresholds for faster results
- **Batch Processing**: Processes multiple search parameters simultaneously for efficient results

### Smart Filtering
- **Price Awareness**: Automatically extracts price ranges from natural language queries
- **Rating-Based Search**: Filters by star ratings and review counts when users ask for "best rated" or "highly reviewed" products
- **Category Validation**: Ensures that when you ask for shoes, you don't get socks or unrelated items

---

## Features

### Frontend (React + TypeScript)
- **Modern UI**: Clean, responsive design with gradient themes
- **ChatBot Widget**: Floating assistant available on every page
- **Product Grid**: Beautiful product cards with images, ratings, prices, and direct Amazon links
- **Smart Search**: Advanced search functionality across the platform
- **Category Pages**: Browse products by category with sorting and filtering
- **Offline Fallback**: Works in offline mode with cached product data

### Backend (FastAPI + Python)
- **Gemini Integration**: Uses Google's latest Gemini model for natural language understanding
- **Pinecone Vector Search**: Semantic product search across thousands of items
- **Session Management**: Redis-backed conversation memory
- **Multi-Tool Architecture**: Combines Pinecone search, JSON fallback enrichment, and database lookups
- **Cohere Reranking**: Intelligent result ranking for better relevance
- **PostgreSQL Database**: Neon database for product metadata

---

## Getting Started

### Prerequisites
- Node.js 16+ (Frontend)
- Python 3.9+ (Backend)
- API Keys:
  - Google Gemini API
  - Pinecone API
  - Cohere API
- Database:
  - Neon PostgreSQL (optional)
  - Redis URL (optional, uses in-memory fallback)

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with required variables
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key
COHERE_API_KEY=your_cohere_api_key
PINECONE_INDEX=your_index_name
REDIS_URL=your_redis_url
GEMINI_MODEL=gemini-2.5-flash-lite
EOF

# Run the backend server
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The backend API will be available at `http://localhost:8000`

---

## Project Structure

```
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatBot.tsx          # Main chatbot interface
│   │   │   ├── ProductCard.tsx      # Product display component
│   │   │   ├── CategoryCard.tsx     # Category cards
│   │   │   └── Header.tsx           # Navigation header
│   │   ├── pages/
│   │   │   ├── Index.tsx            # Home page
│   │   │   ├── CategoryPage.tsx     # Category browsing
│   │   │   ├── SearchPage.tsx       # Search results
│   │   │   └── NotFound.tsx         # 404 page
│   │   ├── App.tsx                  # Main app component
│   │   └── main.tsx                 # Entry point
│   └── package.json
│
└── backend/
    ├── agents/
    │   └── simple_chatbot.py        # Main chatbot logic
    ├── tools/
    │   ├── pinecone_tool.py         # Vector search
    │   ├── session_manager.py       # Conversation memory
    │   ├── cache_manager.py         # Redis caching
    │   ├── json_fallback.py         # Data enrichment
    │   └── database_tool.py         # PostgreSQL queries
    ├── app.py                        # FastAPI application
    ├── config.py                     # Configuration
    └── requirements.txt              # Python dependencies
```

---

## Environment Variables

### Backend (.env)

```env
# LLM and AI Services
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash-lite

# Vector Search
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_index_name

# Text Embeddings
COHERE_API_KEY=your_cohere_api_key

# Database (Neon PostgreSQL)
NEON_HOST=your_neon_host
NEON_DB=your_database_name
NEON_USER=your_db_user
NEON_PASSWORD=your_db_password

# Cache
REDIS_URL=redis://localhost:6379
# For Redis Cloud: rediss://user:password@host:port
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
# For production
VITE_API_URL=https://your-backend-url.com
```

---

## Technology Stack

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **React Query** - Data fetching
- **Shadcn/UI** - Component library
- **Lucide Icons** - Icon library

### Backend
- **FastAPI** - Web framework
- **LangChain** - LLM orchestration
- **Google Gemini** - Large language model
- **Pinecone** - Vector database
- **Cohere** - Text embeddings and reranking
- **Redis** - Session and result caching
- **PostgreSQL (Neon)** - Product metadata database
- **Pydantic** - Data validation

---

## How It Works

### 1. User Query Processing
When a user sends a message, the system:
- Adds the message to conversation history
- Sends it to Gemini along with the system prompt and conversation context
- Gemini understands the intent and decides whether to search for products

### 2. Product Search
If a search is needed:
- Query is embedded into a vector using Cohere embeddings
- Pinecone searches for semantically similar product vectors
- Results are enriched with metadata from JSON and PostgreSQL
- Price and rating filters are applied

### 3. Result Reranking
- Cohere's rerank model scores all results against the original query
- Results are sorted by relevance score, ensuring quality results
- Duplicates are removed and results are validated

### 4. Response Generation
- Gemini analyzes the search results
- Validates that products match the user's intent (e.g., shoes query returns shoes, not socks)
- Selects the top 5-10 most relevant products
- Generates a natural language response

### 5. Session Management
- Conversation history is stored in Redis or in-memory
- Context is maintained for follow-up questions
- Previous searches inform future recommendations

---

## 🎓 Key Concepts

### Semantic Search
Instead of matching keywords, semantic search finds products with similar meaning. For example, "affordable sneakers" and "budget athletic shoes" would return similar results because they have the same intent.

### Vector Embeddings
Text is converted into mathematical vectors that capture semantic meaning. Products with similar vectors are conceptually related, enabling intelligent search.

### Reranking
After finding candidate products, a specialized rerank model scores them for relevance, ensuring the most appropriate products appear first.

### Session Memory
The chatbot maintains conversation history so it understands context. For example, after showing Nike shoes, "Show me cheaper options" knows to search for cheaper Nike shoes, not just any cheap shoes.

---

## Deployment

### Frontend Deployment (Vercel)

```bash
# Push to GitHub
git push origin main

# Connect repository to Vercel
# Set environment variables in Vercel dashboard
# Automatic deployment on push
```

### Backend Deployment (Render/Heroku)

```bash
# Create Procfile
echo "web: uvicorn app:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
git push heroku main
```

Or use Render:
- Connect GitHub repository
- Set environment variables
- Deploy

---

## Performance Tips

### Optimization Strategies
- **Increase Cache TTL** for popular searches
- **Batch Similar Queries** to reduce API calls
- **Index Optimization** in Pinecone for faster vector search
- **Connection Pooling** for database queries
- **CDN Integration** for frontend assets

### Monitoring
- Track API response times
- Monitor cache hit rates
- Watch for slow database queries
- Alert on failed searches

---

## Troubleshooting

### Backend Connection Issues
```
Error: Backend connection failed
Solution: Ensure backend is running on correct port and CORS is properly configured
```

### Slow Search Results
```
Solution: Check Pinecone index size and vector count
Increase cache TTL for popular queries
Enable Redis caching
```

### Products Not Showing
```
Solution: Verify Pinecone index has products indexed
Check that API keys are valid
Ensure JSON fallback file exists at data/products.json
```

### Session Not Persisting
```
Solution: Check Redis connection in console
Verify REDIS_URL environment variable
Use in-memory fallback if Redis unavailable
```

---

## API Documentation

### Chat Endpoint

**POST** `/chat`

Request:
```json
{
  "message": "Show me Nike shoes",
  "session_id": "session_123",
  "user_id": "user_456"
}
```

Response:
```json
{
  "response": "Here are some popular Nike shoes for you!",
  "products": [
    {
      "asin": "B07XKZ5RQF",
      "title": "Nike Air Max...",
      "price": "$99.99",
      "rating": 4.5,
      "reviews": 2341,
      "url": "https://amazon.com/dp/..."
    }
  ],
  "session_id": "session_123"
}
```

### Session Management

**GET** `/session/{session_id}/history` - Get conversation history

**DELETE** `/session/{session_id}` - Clear session

### Health Check

**GET** `/health` - Check backend status

---

## License

MIT License - feel free to use this project for personal or commercial purposes.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript for frontend code
- Write meaningful commit messages
- Test your changes before submitting

---

## Support

For issues, questions, or suggestions:
1. Check the troubleshooting section above
2. Review existing GitHub issues
3. Create a new issue with detailed information

---

## Acknowledgments

- Google Gemini for powerful language understanding
- Pinecone for fast vector search
- Cohere for embeddings and reranking
- LangChain for LLM orchestration
- The open source community

---

Thank You !