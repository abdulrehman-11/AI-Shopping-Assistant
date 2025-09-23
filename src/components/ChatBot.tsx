import React, { useState, useEffect, useRef } from 'react';
import { X, MessageCircle, Volume2, VolumeX, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import VoiceVisualizer from './VoiceVisualizer';
import ProductCard from './ProductCard';
import productsData from '@/data/products.json';

interface Message {
  id: number;
  type: 'bot' | 'user';
  text: string;
  timestamp: string;
  products?: any[];
}

interface ChatBotProps {
  onClose: () => void;
}

const ChatBot: React.FC<ChatBotProps> = ({ onClose }) => {
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('chatMessages');
    return saved ? JSON.parse(saved) : [
      {
        id: 1,
        type: 'bot',
        text: "Hi! I'm your AI shopping assistant. I can help you find products, compare prices, and make recommendations. How can I help you today?",
        timestamp: new Date().toISOString()
      }
    ];
  });
  
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isVoiceMode, setIsVoiceMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isTTSEnabled, setIsTTSEnabled] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages));
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const addMessage = (type: 'bot' | 'user', text: string, products?: any[]) => {
    const newMessage: Message = {
      id: Date.now(),
      type,
      text,
      timestamp: new Date().toISOString(),
      products
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;

    addMessage('user', inputValue);
    setIsTyping(true);

    // Simulate AI response with product search
    setTimeout(() => {
      const userQuery = inputValue.toLowerCase();
      let response = "I found some products that might interest you!";
      let suggestedProducts: any[] = [];

      // Simple keyword matching for product suggestions
      if (userQuery.includes('bag') || userQuery.includes('backpack')) {
        suggestedProducts = productsData.filter(p => p.category === 'Men Bags').slice(0, 3);
        response = "Here are some great bags I found for you:";
      } else if (userQuery.includes('shoe') || userQuery.includes('sneaker')) {
        suggestedProducts = productsData.filter(p => p.category === 'Men Shoes' || p.category === 'Nike Shoes').slice(0, 3);
        response = "Check out these popular shoes:";
      } else if (userQuery.includes('jewelry') || userQuery.includes('watch')) {
        suggestedProducts = productsData.filter(p => p.category === 'Men Jwelerry').slice(0, 3);
        response = "Here are some elegant jewelry pieces:";
      } else if (userQuery.includes('clothing') || userQuery.includes('shirt') || userQuery.includes('hoodie')) {
        suggestedProducts = productsData.filter(p => p.category === 'Men Clothing' || p.category === 'Women Clothing').slice(0, 3);
        response = "I found some great clothing options:";
      } else {
        // Random product suggestions
        const shuffled = [...productsData].sort(() => 0.5 - Math.random());
        suggestedProducts = shuffled.slice(0, 3);
        response = "Based on our popular items, you might like these:";
      }

      addMessage('bot', response, suggestedProducts);
      setIsTyping(false);

      // Text-to-speech
      if (isTTSEnabled && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(response);
        utterance.rate = 0.9;
        speechSynthesis.speak(utterance);
      }
    }, 1000);

    setInputValue('');
  };

  const clearChat = () => {
    setMessages([
      {
        id: 1,
        type: 'bot',
        text: "Chat cleared! How can I help you today?",
        timestamp: new Date().toISOString()
      }
    ]);
  };

  const toggleVoiceMode = async () => {
    if (!isVoiceMode) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContextRef.current = new AudioContext();
        analyserRef.current = audioContextRef.current.createAnalyser();
        const source = audioContextRef.current.createMediaStreamSource(stream);
        source.connect(analyserRef.current);
        setIsVoiceMode(true);
      } catch (error) {
        console.error('Voice access denied:', error);
      }
    } else {
      setIsVoiceMode(false);
      setIsListening(false);
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
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
              <div className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse" />
              Online
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

      <CardContent className="flex-1 p-0 flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] p-3 rounded-lg ${
                message.type === 'user' 
                  ? 'bg-primary text-primary-foreground' 
                  : 'bg-muted'
              }`}>
                <p className="text-sm">{message.text}</p>
                
                {message.products && message.products.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {message.products.map((product, index) => (
                      <div key={index} className="bg-card p-2 rounded border">
                        <div className="flex items-center space-x-2">
                          <img 
                            src={product.thumbnailImage} 
                            alt={product.title}
                            className="w-12 h-12 object-cover rounded"
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium line-clamp-2">{product.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {product.price ? `${product.price.currency}${product.price.value}` : 'See on Amazon'}
                            </p>
                            <Button
                              size="sm"
                              className="mt-1 h-6 text-xs bg-gradient-primary"
                              onClick={() => window.open(product.url, '_blank')}
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

        {isVoiceMode && (
          <VoiceVisualizer 
            isListening={isListening} 
            analyser={analyserRef.current} 
          />
        )}

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
              variant={isVoiceMode ? "default" : "outline"}
              size="sm"
              className="px-3"
            >
              🎤
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