import React, { useState, useEffect, useRef } from 'react';
import { X, Trash2, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Product {
  asin: string;
  image?: string;
  thumbnailImage?: string;
  image_url?: string;
  title: string;
  description: string;
  rating: number;
  reviews: number;
  price: string;
  url: string;
  similarity_score?: number;
}

interface Message {
  id: number;
  type: 'bot' | 'user';
  text: string;
  timestamp: string;
  products?: Product[];
  needsClarification?: boolean;
  clarificationQuestions?: string[];
  pending?: boolean; // <-- Add this line
}

interface ChatBotProps {
  onClose: () => void;
}

// Generate or retrieve persistent session ID
const getOrCreateSessionId = () => {
  // Check if we already have a session ID
  const existingId = localStorage.getItem('chatbot_session_id');
  if (existingId) {
    return existingId;
  }
  
  // Only create new if doesn't exist
  const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  localStorage.setItem('chatbot_session_id', newId);
  return newId;
};

const BACKEND_URL = process.env.NODE_ENV === 'production' 
  ? 'https://ai-shopping-assistant-1.onrender.com'  // Replace with your actual backend URL
  : 'http://localhost:8000';

const ChatBot: React.FC<ChatBotProps> = ({ onClose }) => {
  const [sessionId] = useState(getOrCreateSessionId());
    const [messages, setMessages] = useState<Message[]>(() => {
      const currentSessionId = getOrCreateSessionId();
      const saved = localStorage.getItem(`chatMessages_${currentSessionId}`);
      return saved ? JSON.parse(saved) : [
    {
      id: 1,
      type: 'bot',
      text: "Hi! I'm your AI shopping assistant. I can help you find products using advanced semantic search. What are you looking for today?",
      timestamp: new Date().toISOString()
    }
  ];
});

  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Helper function to parse price string to ProductCard format
  const parsePrice = (priceStr: string) => {
    // Handle formats like "$49.99", "USD49.99", "49.99"
    const match = priceStr.match(/([A-Z$€£¥]*)([\d,.]+)/);
    if (match) {
      const currency = match[1] || '$';
      const value = parseFloat(match[2].replace(/,/g, ''));
      return {
        currency,
        value
      };
    }
    return undefined;
  };

  // Check backend connection on mount
  useEffect(() => {
    checkBackendConnection();
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem(`chatMessages_${sessionId}`, JSON.stringify(messages));
    scrollToBottom();
  }, [messages, sessionId]);

  useEffect(() => {
  // If there is a pending bot message, retry fetching the answer
  const lastPending = messages.find(m => m.pending && m.type === 'bot');
  const lastUser = [...messages].reverse().find(m => m.type === 'user');
  if (lastPending && lastUser) {
    setIsTyping(true);
    fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: lastUser.text,
        session_id: sessionId,
      }),
    })
      .then(res => res.json())
      .then(data => {
        setMessages(prev =>
          prev.map(msg =>
            msg.pending
              ? {
                  ...msg,
                  text: data.response,
                  products: data.ui_products || [],
                  pending: false,
                }
              : msg
          )
        );
        setIsTyping(false);
      })
      .catch(() => setIsTyping(false));
  }
  // eslint-disable-next-line
}, []);

  const checkBackendConnection = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/health`);
      if (response.ok) {
        setIsConnected(true);
        console.log('✅ Connected to backend');
      }
    } catch (error) {
      console.error('❌ Backend connection failed:', error);
      setIsConnected(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const addMessage = (type: 'bot' | 'user', text: string, products?: Product[], needsClarification?: boolean, clarificationQuestions?: string[]) => {
    const newMessage: Message = {
      id: Date.now(),
      type,
      text,
      timestamp: new Date().toISOString(),
      products,
      needsClarification,
      clarificationQuestions
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const handleSendMessage = async () => {
  if (!inputValue.trim()) return;

  const userMessage = inputValue.trim();
  addMessage('user', userMessage);
  const pendingBotMsgId = Date.now() + 1;
  setMessages(prev => [
    ...prev,
    {
      id: pendingBotMsgId,
      type: 'bot',
      text: "Thinking...",
      timestamp: new Date().toISOString(),
      pending: true
    }
  ]);
  setIsTyping(true);
  setInputValue('');

  let timeoutId: NodeJS.Timeout | null = null;

  try {
    if (!isConnected) {
      handleMockResponse(userMessage);
      return;
    }



    const response = await fetch(`${BACKEND_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    clearTimeout(timeoutId);

    if (data.needs_clarification && data.clarification_questions?.length > 0) {
      const questionText = data.response || "I need some clarification:";
      setMessages(prev =>
        prev.map(msg =>
          msg.pending
            ? {
                ...msg,
                text: questionText,
                needsClarification: true,
                clarificationQuestions: data.clarification_questions,
                pending: false
              }
            : msg
        )
      );
    } else {
      const products = data.ui_products || [];
      setMessages(prev =>
        prev.map(msg =>
          msg.pending
            ? {
                ...msg,
                text: data.response,
                products,
                pending: false
              }
            : msg
        )
      );
    }
  } catch (error) {
    clearTimeout(timeoutId);
    setMessages(prev =>
      prev.map(msg =>
        msg.pending
          ? {
              ...msg,
              text: "Sorry, we are facing some issues. Please try again after some time. Thanks!",
              pending: false
            }
          : msg
      )
    );
    setIsTyping(false);
  } finally {
    setIsTyping(false);
  }
};


  // Improved fallback method for when backend is unavailable
  const handleMockResponse = async (userQuery: string) => {
    try {
      const productsModule = await import('@/data/products.json');
      const productsData = productsModule.default;
      
      setTimeout(() => {
        const query = userQuery.toLowerCase();
        let response = "Based on what you're looking for, here are some great options:";
        let suggestedProducts: any[] = [];

        // Simple keyword matching
        if (query.includes('nike') || query.includes('shoe')) {
          suggestedProducts = productsData.filter(p => 
            p.category === 'Nike Shoes' || p.category === 'Men Shoes'
          ).slice(0, 3);
          response = "I found some excellent Nike shoes for you:";
        } else if (query.includes('shirt') || query.includes('clothing')) {
          suggestedProducts = productsData.filter(p => 
            p.category === 'Men Clothing' || p.category === 'Women Clothing'
          ).slice(0, 3);
          response = "Here are some popular clothing items:";
        } else if (query.includes('bag') || query.includes('backpack')) {
          suggestedProducts = productsData.filter(p => p.category === 'Men Bags').slice(0, 3);
          response = "Here are some great bags I found for you:";
        } else if (query.includes('jewelry') || query.includes('watch')) {
          suggestedProducts = productsData.filter(p => p.category === 'Men Jwelerry').slice(0, 3);
          response = "Here are some elegant jewelry pieces:";
        } else if (query.includes('hoodie') || query.includes('sweatshirt')) {
          suggestedProducts = productsData.filter(p => 
            p.category === 'Men Clothing' || p.category === 'Women Clothing'
          ).slice(0, 3);
          response = "I found some comfortable hoodies for you:";
        } else {
          // Default suggestions
          const shuffled = [...productsData].sort(() => 0.5 - Math.random());
          suggestedProducts = shuffled.slice(0, 3);
          response = "Let me show you some popular products that might interest you:";
        }

        // Convert to UI format
        const products: Product[] = suggestedProducts.map(p => ({
          asin: p.asin || `mock_${Date.now()}`,
          image: p.thumbnailImage || p.image || p.image_url || '',
          title: p.title,
          description: p.brand || p.category || '',
          rating: p.stars || 0,
          reviews: p.reviews_count || 0,
          price: p.price ? `${p.price.currency}${p.price.value}` : 'See on Amazon',
          url: p.url || '#'
        }));

        addMessage('bot', response, products);
        setIsTyping(false);
      }, 1000);
    } catch (error) {
      addMessage('bot', "I'm having trouble right now, but I'm here to help you find great products. What are you looking for?");
      setIsTyping(false);
    }
  };

  const clearChat = async () => {
    try {
      if (isConnected) {
        // Clear session on backend
        await fetch(`${BACKEND_URL}/session/${sessionId}`, {
          method: 'DELETE',
        });
      }
      
      // Clear local storage
      localStorage.removeItem(`chatMessages_${sessionId}`);
      localStorage.removeItem('chatbot_session_id');

      // Generate new session ID
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chatbot_session_id', newSessionId);
      
      // Reset messages
      setMessages([
        {
          id: 1,
          type: 'bot',
          text: "Chat cleared! How can I help you today?",
          timestamp: new Date().toISOString()
        }
      ]);
      // Reload to apply new session
      window.location.reload();

      
      // Generate new session ID
      
    } catch (error) {
      console.error('Clear chat error:', error);
      // Still clear locally even if backend fails
      setMessages([
        {
          id: 1,
          type: 'bot',
          text: "Chat cleared! How can I help you today?",
          timestamp: new Date().toISOString()
        }
      ]);
    }
  };


  return (
    <Card className="fixed bottom-6 right-6 w-96 h-[600px] shadow-2xl z-50 flex flex-col animate-scale-in">
      <CardHeader className="flex flex-row items-center justify-between p-4 border-b">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-primary rounded-full flex items-center justify-center text-white font-bold">
            🤖
          </div>
          <div>
            <h3 className="font-semibold">Shopping Assistant</h3>
            <Badge variant="secondary" className="text-xs">
              <div className={`w-2 h-2 rounded-full mr-1 animate-pulse ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
              {isConnected ? 'AI Online' : 'Offline Mode'}
            </Badge>
          </div>
        </div>
        
        <div className="flex items-center space-x-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearChat}
            className="h-8 w-8 p-0"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 p-0 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">

          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] p-3 rounded-lg ${
                message.type === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}>
                <div className="text-sm">
                {message.text.split('\n').map((line, index) => (
                  <p key={index} className="mb-2 last:mb-0">
                  {line.split(/(\*\*.*?\*\*)/g).map((part, partIndex) => {
                  if (part.startsWith('**') && part.endsWith('**')) {
                  return <strong key={partIndex}>{part.slice(2, -2)}</strong>;
                  }
                  return part;
                    })}
                  </p>
                    ))}
                      </div>

                
                {/* Clarification Questions */}
                {message.needsClarification && message.clarificationQuestions && (
                  <div className="mt-3 space-y-2">
                    {message.clarificationQuestions.map((question, index) => (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        className="w-full text-left justify-start"
                        onClick={() => setInputValue(question)}
                      >
                        {question}
                      </Button>
                    ))}
                  </div>
                )}
                
                {/* Product Results - Compact Inline Cards */}
                {message.products && message.products.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {message.products.map((product, index) => (
                      <div key={index} className="bg-card rounded border shadow-sm hover:shadow transition-shadow overflow-hidden">
                        <div className="flex gap-2 p-2">
                          {/* Product Image - Compact */}
                          <div className="relative w-20 h-20 flex-shrink-0 bg-gray-50 rounded overflow-hidden">
                            <img
                              src={product.image || product.thumbnailImage || product.image_url || '/placeholder.svg'}
                              alt={product.title}
                              className="w-full h-full object-contain"
                              onError={(e) => {
                                const target = e.target as HTMLImageElement;
                                if (target.src !== '/placeholder.svg') {
                                  target.src = '/placeholder.svg';
                                }
                              }}
                            />
                          </div>

                          {/* Product Info - Compact */}
                          <div className="flex-1 min-w-0 flex flex-col justify-between">
                            <div>
                              <h4 className="text-xs font-semibold line-clamp-2 leading-tight mb-1">
                                {product.title}
                              </h4>

                              {/* Rating and Reviews */}
                              {product.rating > 0 && (
                                <div className="flex items-center gap-1 mb-1">
                                  <div className="flex">
                                    {[1, 2, 3, 4, 5].map((star) => (
                                      <svg
                                        key={star}
                                        className={`w-3 h-3 ${
                                          star <= Math.round(product.rating)
                                            ? 'fill-yellow-400 text-yellow-400'
                                            : 'fill-gray-200 text-gray-200'
                                        }`}
                                        viewBox="0 0 20 20"
                                      >
                                        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                                      </svg>
                                    ))}
                                  </div>
                                  <span className="text-xs font-medium text-gray-600">
                                    {product.rating.toFixed(1)}
                                  </span>
                                  {product.reviews > 0 && (
                                    <span className="text-xs text-gray-400">
                                      ({product.reviews > 1000 ? `${(product.reviews / 1000).toFixed(1)}k` : product.reviews})
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Price and Button */}
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-bold text-primary">
                                {product.price}
                              </span>
                              <Button
                                size="sm"
                                className="h-7 text-xs px-2 bg-gradient-primary hover:opacity-90"
                                onClick={() => product.url && product.url !== '#' ? window.open(product.url, '_blank') : null}
                              >
                                <ExternalLink className="h-3 w-3 mr-1" />
                                View
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          



          
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 border-t">
          <div className="flex space-x-2">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Ask about products..."
              className="flex-1"
            />
            <Button
              onClick={handleSendMessage}
              size="sm"
              className="bg-gradient-primary hover:opacity-90"
              disabled={isTyping}
            >
              Send
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ChatBot;
