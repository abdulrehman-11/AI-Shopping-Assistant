# ShopSmart - AI-Powered E-Commerce Shopping Assistant

An intelligent shopping assistant platform that combines advanced AI, semantic search, and real-time conversation to help users discover and purchase products from Amazon effortlessly.

## 🎯 Overview

ShopSmart is a full-stack e-commerce application featuring an AI-powered chatbot that understands natural language queries, provides personalized product recommendations, and maintains conversation context. The platform uses cutting-edge technologies like LangGraph for workflow orchestration, vector databases for semantic search, and generative AI for intelligent responses.

## ✨ Features

- **AI-Powered Chatbot**: Conversational shopping assistant with contextual understanding
- **Semantic Search**: Vector-based product search using Pinecone and Cohere embeddings
- **Multi-Intent Classification**: Automatically classifies queries as product search, questions, vague queries, or off-topic
- **Conversation Memory**: Maintains user session history and preferences
- **Smart Filtering**: Price, rating, and relevance-based product filtering
- **Real-Time Relevance Validation**: Ensures search results match user intent
- **Category Browsing**: Organized product categories with sorting and filtering
- **Responsive UI**: Modern, mobile-friendly interface built with React and Tailwind CSS
- **Offline Fallback**: Mock responses when backend is unavailable

## 🏗️ Architecture Overview

### Backend Flow

When a user sends a message, here's what happens:

1. **Message Reception** → User message arrives at `/chat` endpoint
2. **Classification** → AI classifies intent (specific search, vague, product question, off-topic, etc.)
3. **Routing** → Based on classification, message routes to appropriate handler
4. **Processing** → Query is enhanced with conversation context
5. **Search** → Products are searched using vector similarity and metadata filters
6. **Validation** → AI validates if results match user intent
7. **Generation** → Natural response is generated with product recommendations
8. **Response** → Final response sent back to frontend with products

See [Backend Processing Flow](#backend-processing-flow-detailed) below for detailed information.

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Workflow Orchestration**: LangGraph
- **LLM**: Google Gemini (gemini-2.5-flash-lite)
- **Vector Database**: Pinecone
- **Embeddings**: Cohere
- **Session Management**: Redis (with in-memory fallback)
- **Database**: Neon PostgreSQL
- **Server**: Uvicorn

### Frontend
- **Framework**: React 18 with TypeScript
- **Routing**: React Router v6
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **State Management**: React Query
- **Icons**: Lucide React
- **Bundler**: Vite

## 📋 Prerequisites

### Required
- **Node.js**: v18.0.0 or higher
- **Python**: v3.9 or higher
- **Git**: For version control

### API Keys Required
- **Google Gemini API Key**: [Get it here](https://makersuite.google.com/app/apikey)
- **Pinecone API Key**: [Sign up at Pinecone](https://www.pinecone.io/)
- **Cohere API Key**: [Get it here](https://cohere.com/)

### Optional
- **Redis**: For session management (can use in-memory fallback)
- **Neon Database**: For persistent storage (currently optional in config)

## 🚀 Backend Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Create Environment File
Create a `.env` file in the backend root directory:
```env
# LLM Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite

# Vector Database
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX=your_pinecone_index_name

# Embeddings
COHERE_API_KEY=your_cohere_api_key_here

# Session Management
REDIS_URL=redis://localhost:6379  # Optional, defaults to in-memory

# Database (Optional)
NEON_HOST=your_neon_host
NEON_DB=your_database_name
NEON_USER=your_username
NEON_PASSWORD=your_password
```

### 5. Verify Configuration
```bash
python -c "from config import Config; print('✓ Configuration loaded successfully')"
```

### 6. Run Backend Server
```bash
python app.py
```

The backend will start at `http://localhost:8000`

**Available Endpoints:**
- `POST /chat` - Send message to chatbot
- `POST /search` - Direct product search
- `GET /health` - Health check
- `GET /session/{session_id}/history` - Get conversation history
- `DELETE /session/{session_id}` - Clear session
- `GET /categories` - Get product categories
- `GET /brands` - Get popular brands
- `GET /debug/*` - Debug endpoints for development

## 🎨 Frontend Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd frontend
```

### 2. Install Dependencies
```bash
npm install
# or
yarn install
```

### 3. Create Environment File
Create a `.env.local` file in the frontend root:
```env
VITE_API_URL=http://localhost:8000
NODE_ENV=development
```

### 4. Run Development Server
```bash
npm run dev
# or
yarn dev
```

The frontend will be available at `http://localhost:5173`

### 5. Build for Production
```bash
npm run build
```

## 🔄 Backend Processing Flow (Detailed)

### Step 1: Intent Classification
When you send a message like "I want shoes", the system:
- Uses Gemini AI to classify the intent
- Extracts category, brand, gender information
- Checks inventory availability
- Returns one of: **SPECIFIC**, **VAGUE**, **PRODUCT_QUESTION**, **OFF_TOPIC**, or **UNAVAILABLE**

**Example:**
```
Message: "I want shoes"
Classification: VAGUE (missing gender)
Response: "Are you looking for shoes for men, women, or kids?"
```

### Step 2: Query Processing
For specific queries, the system:
- Retrieves conversation context
- Extracts user preferences from history
- Combines current query with context
- Sends to SimpleProcessor for enhancement

**Example:**
```
Current: "more expensive ones"
Context: Previously searched "nike shoes for men"
Enhanced: "nike shoes for men more expensive"
```

### Step 3: Product Search
- Checks cache for existing results
- Extracts price and rating filters from query
- Searches Pinecone with vector embeddings
- Reranks with Cohere for relevance
- Applies post-search filters

### Step 4: Relevance Validation
- Takes top 3 products
- Sends to Gemini for relevance check
- Returns: HIGHLY_RELEVANT, PARTIALLY_RELEVANT, or NOT_RELEVANT
- Routes to no results handler if not relevant

### Step 5: Response Generation
- Formats top 3 products
- Generates natural response with Gemini
- Converts to UI format for display
- Saves to session history

## 📁 Project Structure

### Backend
```
backend/
├── app.py                    # FastAPI application
├── config.py                 # Configuration management
├── chatbot_workflow.py       # LangGraph workflow
├── simple_processor.py       # Query processing
├── requirements.txt          # Python dependencies
├── agents/
│   └── query_classifier.py   # Query classification logic
├── tools/
│   ├── pinecone_tool.py      # Vector search
│   ├── session_manager.py    # Session management
│   ├── cache_manager.py      # Result caching
│   └── database_tool.py      # Database operations
└── models/
    └── schemas.py            # Pydantic models
```

### Frontend
```
frontend/
├── src/
│   ├── App.tsx               # Main app component
│   ├── pages/
│   │   ├── Index.tsx         # Home page
│   │   ├── CategoryPage.tsx  # Category listing
│   │   ├── SearchPage.tsx    # Search results
│   │   └── NotFound.tsx      # 404 page
│   ├── components/
│   │   ├── ChatBot.tsx       # Chatbot component
│   │   ├── Header.tsx        # Navigation header
│   │   ├── ProductCard.tsx   # Product display
│   │   └── CategoryCard.tsx  # Category card
│   ├── data/
│   │   └── products.json     # Product database
│   ├── assets/               # Images and static files
│   └── styles/               # Global styles
├── vite.config.ts            # Vite configuration
├── tsconfig.json             # TypeScript configuration
└── package.json              # Node dependencies
```

## 💬 How the Chatbot Works

### Natural Conversation Flow

**Example 1: Product Search**
```
User: "I want nike shoes for men"
Bot: Classifies as SPECIFIC → Searches → Finds relevant products
Bot: "I found 3 great Nike shoes for men! Here are my top picks..."
Bot: Shows product cards with images, prices, ratings

User: "more expensive ones"
Bot: Understands follow-up → Filters by price → Shows premium options
Bot: "Here are more premium Nike shoes for men..."
```

**Example 2: Clarification**
```
User: "I want shoes"
Bot: Classifies as VAGUE → Needs gender info
Bot: "I'd love to help! Are you looking for shoes for men, women, or kids?"
Bot: Shows quick-select buttons for each option

User: "men"
Bot: Now SPECIFIC → Searches and shows results
```

**Example 3: Product Question**
```
User: "What is the price of Nike Air Max?"
Bot: Classifies as PRODUCT_QUESTION → Searches for that specific product
Bot: "The Nike Air Max is priced at $129.99 with 4.5 stars (1,250 reviews)"
Bot: Shows the product card
```

### Session Management

- Each user gets a unique session ID (stored in localStorage)
- Conversation history is maintained for context
- User preferences are extracted from chat history
- Up to 20 recent messages are stored
- Previous context helps with follow-up queries

## 🧪 Testing the API

### Health Check
```bash
curl http://localhost:8000/health
```

### Send Chat Message
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want nike shoes for men",
    "session_id": "test_session_123"
  }'
```

### Direct Product Search
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "nike shoes",
    "limit": 10
  }'
```

### Get Categories
```bash
curl http://localhost:8000/categories
```

## 🌐 Deployment

### Backend Deployment (Render.com Example)
1. Push code to GitHub
2. Connect GitHub repository to Render
3. Set environment variables in Render dashboard
4. Deploy as Web Service
5. Backend URL becomes accessible globally

### Frontend Deployment (Vercel Example)
1. Push code to GitHub
2. Connect GitHub repository to Vercel
3. Set `VITE_API_URL` to your backend URL
4. Deploy automatically
5. Frontend available on `vercel.app` domain

## 🔐 Environment Variables Explained

| Variable | Purpose | Required |
|----------|---------|----------|
| `GEMINI_API_KEY` | Google Gemini LLM access | Yes |
| `PINECONE_API_KEY` | Vector database authentication | Yes |
| `COHERE_API_KEY` | Text embedding and reranking | Yes |
| `GEMINI_MODEL` | Model to use (default: gemini-2.5-flash-lite) | No |
| `REDIS_URL` | Redis connection string | No (in-memory fallback) |
| `PINECONE_INDEX` | Index name in Pinecone | Yes |
| `NEON_HOST` | PostgreSQL host | No |
| `NEON_DB` | Database name | No |
| `NEON_USER` | Database username | No |
| `NEON_PASSWORD` | Database password | No |

## 📊 Key Components Explained

### ChatbotWorkflow
Orchestrates the entire conversation flow using LangGraph:
- **Nodes**: Classification, search, validation, response generation
- **Edges**: Conditional routing based on classification
- **State Management**: Maintains conversation state throughout workflow

### SimpleProcessor
Enhances queries with conversation context:
- Combines current query with previous context
- Extracts structured information (category, brand, gender)
- Creates optimized search terms

### SessionManager
Manages user sessions and conversation history:
- Stores messages in Redis or in-memory
- Tracks user preferences
- Maintains session context

### Pinecone Tool
Handles vector similarity search:
- Converts queries to embeddings using Cohere
- Searches similar products in Pinecone
- Applies metadata filters (price, rating)

## 🐛 Troubleshooting

### Backend Won't Start
```bash
# Check Python version
python --version  # Should be 3.9+

# Check if port 8000 is in use
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Verify environment variables
echo $GEMINI_API_KEY
```

### Chat Not Working
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify API keys in `.env` file
3. Check browser console for errors
4. Try clearing chat history and starting fresh

### Products Not Showing
1. Verify Pinecone index name is correct
2. Check Pinecone has products indexed
3. Try debug endpoint: `curl http://localhost:8000/debug/search`
4. Verify Cohere API key is valid

### Session Not Persisting
1. If using Redis, verify Redis is running
2. Check localStorage is not disabled in browser
3. Verify session ID is being created (check browser DevTools)

## 📚 API Documentation

### POST /chat
Send a message and get response with products.

**Request:**
```json
{
  "message": "I want nike shoes for men",
  "session_id": "session_123",
  "user_id": "user_123"  // optional
}
```

**Response:**
```json
{
  "response": "I found 3 great Nike shoes for men! Here are my top picks...",
  "products": [/* raw product data */],
  "ui_products": [/* formatted for UI */],
  "needs_clarification": false,
  "clarification_questions": [],
  "search_metadata": {
    "total_found": 15,
    "search_query": "nike shoes for men",
    "relevance_status": "highly_relevant"
  },
  "session_id": "session_123"
}
```

### POST /search
Direct product search without conversation context.

**Request:**
```json
{
  "query": "nike shoes",
  "filters": {"price_value": {"$lte": 150}},
  "limit": 10
}
```

**Response:**
```json
{
  "products": [/* product array */],
  "total_count": 10
}
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -am 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Google Gemini**: For powerful language understanding and generation
- **Pinecone**: For scalable vector search
- **Cohere**: For embeddings and reranking
- **LangGraph**: For workflow orchestration
- **React & Tailwind**: For beautiful UI
- **shadcn/ui**: For accessible components

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section above

## 🚀 Future Enhancements

- [ ] Voice input for chat
- [ ] Multi-language support
- [ ] Advanced filters (color, size, brand preferences)
- [ ] User accounts and saved preferences
- [ ] Order history and tracking
- [ ] Product comparisons
- [ ] Review and rating system
- [ ] Wishlist functionality
- [ ] Real-time inventory sync
- [ ] Mobile app (React Native)

---

**Happy Shopping! 🛍️**

Made with ❤️ using AI and modern web technologies.