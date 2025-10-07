import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Header from '@/components/Header';
import ProductCard from '@/components/ProductCard';
import { Button } from '@/components/ui/button';
import ChatBot from '@/components/ChatBot';
import { Loader2 } from 'lucide-react';

const SearchPage = () => {
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [products, setProducts] = useState([]);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (query) {
      searchProducts(query);
    }
  }, [query]);

  const searchProducts = async (searchQuery: string) => {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NODE_ENV === 'production' 
        ? 'https://ai-shopping-assistant-1.onrender.com' 
        : 'http://localhost:8000'}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, limit: 20 })
      });
      
      const data = await response.json();
      const normalized = (data.products || []).map((p: any) => ({
        ...p,
        thumbnailImage: p.thumbnailImage || p.image || '',
      }));
      setProducts(normalized);
    } catch (error) {
      console.error('Search error:', error);
      // Fallback to local search
      const productsModule = await import('@/data/products.json');
      const queryLc = searchQuery.toLowerCase();
      const scored = productsModule.default
        .map((p: any) => {
          const title = p.title?.toLowerCase() || '';
          const brand = p.brand?.toLowerCase() || '';
          const category = p.category?.toLowerCase() || '';
          let score = 0;
          if (title === queryLc) score += 10; // exact match boost
          if (title.includes(queryLc)) score += 6;
          if (brand.includes(queryLc)) score += 3;
          if (category.includes(queryLc)) score += 2;
          // multi-word partials
          queryLc.split(/\s+/).forEach((tok) => {
            if (!tok) return;
            if (title.includes(tok)) score += 1;
          });
          return { ...p, _score: score };
        })
        .filter((p: any) => p._score > 0)
        .sort((a: any, b: any) => b._score - a._score)
        .slice(0, 20)
        .map(({ _score, ...rest }: any) => rest);
      setProducts(scored);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-2">Search Results</h1>
        <p className="text-muted-foreground mb-6">
          Results for "{query}" ({products.length} products found)
        </p>
        
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {products.map((product) => (
              <ProductCard key={product.asin} product={product} />
            ))}
          </div>
        )}
      </div>
      {!isChatOpen && (
        <Button
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-primary hover:opacity-90 shadow-2xl z-40"
          size="lg"
        >
          💬
        </Button>
      )}
      {isChatOpen && <ChatBot onClose={() => setIsChatOpen(false)} />}
    </div>
  );
};

export default SearchPage;