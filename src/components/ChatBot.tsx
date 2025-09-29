import React, { useState, useEffect, useRef } from 'react';
import { X, MessageCircle, Volume2, VolumeX, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import VoiceVisualizer from './VoiceVisualizer';
import ProductCard from './ProductCard';

interface Product {
  asin: string;
  image: string;
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
}

interface ChatBotProps {
  onClose: () => void;
}

// Generate consistent session ID
const generateSessionId = () => {
  // Create new session for each page load to ensure fresh conversations
  const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  localStorage.setItem('chatbot_session_id', newId);
  return newId;
};

const BACKEND_URL = process.env.NODE_ENV === 'production' 
  ? 'https://ai-shopping-assistant-1.onrender.com/'  // Replace with your actual backend URL
  : 'http://localhost:8000';

const ChatBot: React.FC<ChatBotProps> = ({ onClose }) => {
  const [sessionId] = useState(generateSessionId());
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem(`chatMessages_${generateSessionId()}`);
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
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTTSEnabled, setIsTTSEnabled] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Check backend connection on mount
  useEffect(() => {
    checkBackendConnection();
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem(`chatMessages_${sessionId}`, JSON.stringify(messages));
    scrollToBottom();
  }, [messages, sessionId]);

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
    setIsTyping(true);
    setInputValue('');

    try {
      if (!isConnected) {
        // Fallback to mock response if backend is not available
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
      
      // Handle clarification questions
      if (data.needs_clarification && data.clarification_questions?.length > 0) {
        const questionText = data.response || "I need some clarification:";
        addMessage('bot', questionText, undefined, true, data.clarification_questions);
      } else {
        // Handle regular response with products
        const products = data.ui_products || [];
        addMessage('bot', data.response, products);
      }

      

    } catch (error) {
      console.error('Chat error:', error);
      addMessage('bot', "I'm having trouble connecting to my brain right now. Let me try a simple search for you.");
      
      // Fallback to simple search
      handleMockResponse(userMessage);
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
          image: p.thumbnailImage || p.image || '',
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
      
      // Reset messages
      setMessages([
        {
          id: 1,
          type: 'bot',
          text: "Chat cleared! How can I help you today?",
          timestamp: new Date().toISOString()
        }
      ]);
      
      // Generate new session ID
      const newSessionId = generateSessionId();
      
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

  const toggleVoiceMode = async () => {
  if (!isVoiceActive) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setIsVoiceActive(true);
      startListening(stream);
    } catch (error) {
      console.error('Voice access denied:', error);
    }
  } else {
    setIsVoiceActive(false);
    setIsRecording(false);
    stopListening();
  }
};

const startListening = (stream: MediaStream) => {
  setIsRecording(true);
  // Here you would integrate with ElevenLabs STT
  // For now, using Web Speech API as placeholder
  
  if ('webkitSpeechRecognition' in window) {
    const recognition = new (window as any).webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInputValue(transcript);
      setIsRecording(false);
    };
    
    recognition.onerror = () => {
      setIsRecording(false);
    };
    
    recognition.start();
  }
};

const stopListening = () => {
  setIsRecording(false);
  // Stop any active recognition
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
            onClick={() => setIsTTSEnabled(!isTTSEnabled)}
            className="h-8 w-8 p-0"
          >
            {isTTSEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </Button>
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
              <div className={`max-w-[80%] p-3 rounded-lg ${
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
                
                {/* Product Results */}
                {message.products && message.products.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {message.products.map((product, index) => (
                      <div key={index} className="bg-card p-2 rounded border">
                        <div className="flex items-center space-x-2">
                          <img 
                            src={product.image || '/placeholder.svg'} 
                            alt={product.title}
                            className="w-12 h-12 object-cover rounded"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = '/placeholder.svg';
                            }}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium line-clamp-2">{product.title}</p>
                            <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                              {product.rating > 0 && (
                                <span>⭐ {product.rating.toFixed(1)}</span>
                              )}
                              {product.reviews > 0 && (
                                <span>({product.reviews} reviews)</span>
                              )}
                            </div>
                            <p className="text-xs text-muted-foreground">{product.price}</p>
                            <Button
                              size="sm"
                              className="mt-1 h-6 text-xs bg-gradient-primary"
                              onClick={() => product.url && product.url !== '#' ? window.open(product.url, '_blank') : null}
                            >
                              View on Amazon
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-muted p-3 rounded-lg">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          )}
          
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
           onClick={toggleVoiceMode}
          variant={isVoiceActive ? "default" : "outline"}
           size="sm"
             className={`px-3 relative ${isVoiceActive ? 'bg-primary text-primary-foreground font-bold' : ''}`}
            >
            {isRecording ? (
              <div className="animate-pulse">🎤</div>
                ) : (
              <div className={isVoiceActive ? 'animate-bounce' : ''}>🎤</div>
              )}
            </Button>
            <Button
              onClick={handleSendMessage}
              size="sm"
              className="bg-gradient-primary hover:opacity-90"
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