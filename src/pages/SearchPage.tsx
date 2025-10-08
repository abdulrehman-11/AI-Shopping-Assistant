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
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (query) {
      searchProducts(query);
    } else {
      setProducts([]);
      setHasSearched(false);
    }
  }, [query]);

  const searchProducts = async (searchQuery: string) => {
    setLoading(true);
    setHasSearched(true);
    setProducts([]); // Clear previous results immediately
    
    try {
      const response = await fetch(`${process.env.NODE_ENV === 'production' 
        ? 'https://ai-shopping-assistant-1.onrender.com' 
        : 'http://localhost:8000'}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, limit: 30 })
      });
      
      const data = await response.json();
      const normalized = (data.products || []).map((p: any) => ({
        ...p,
        thumbnailImage: p.thumbnailImage || p.image || '',
      }));
      
      // Remove duplicates based on ASIN and improve relevance
      const uniqueProducts = normalized.reduce((acc: any[], product: any) => {
        const existingIndex = acc.findIndex(p => p.asin === product.asin);
        if (existingIndex === -1) {
          acc.push(product);
        } else {
          // Keep the product with better similarity score or more complete data
          const existing = acc[existingIndex];
          if (product.similarity_score > existing.similarity_score || 
              (product.title && product.title.length > existing.title?.length)) {
            acc[existingIndex] = product;
          }
        }
        return acc;
      }, []);
      
      // Sort by relevance and limit to top results
      const sortedProducts = uniqueProducts
        .sort((a, b) => (b.similarity_score || 0) - (a.similarity_score || 0))
        .slice(0, 20);
      
      setProducts(sortedProducts);
    } catch (error) {
      console.error('Search error:', error);
      // Improved fallback search with better relevance scoring
      const productsModule = await import('@/data/products.json');
      const queryLc = searchQuery.toLowerCase().trim();
      const queryWords = queryLc.split(/\s+/).filter(word => word.length > 0);
      
      const scored = productsModule.default
        .map((p: any) => {
          const title = p.title?.toLowerCase() || '';
          const brand = p.brand?.toLowerCase() || '';
          const category = p.category?.toLowerCase() || '';
          const description = p.description?.toLowerCase() || '';
          
          let score = 0;
          
          // Exact matches get highest scores
          if (title === queryLc) score += 20;
          if (brand === queryLc) score += 15;
          
          // Partial matches in title (most important)
          if (title.includes(queryLc)) score += 10;
          
          // Word-by-word matching in title
          queryWords.forEach(word => {
            if (title.includes(word)) score += 5;
            if (brand.includes(word)) score += 3;
            if (category.includes(word)) score += 2;
            if (description.includes(word)) score += 1;
          });
          
          // Boost for products with complete data
          if (p.thumbnailImage && p.price) score += 2;
          if (p.stars && p.stars > 4) score += 1;
          
          return { ...p, _score: score };
        })
        .filter((p: any) => p._score > 0)
        .sort((a: any, b: any) => b._score - a._score)
        .slice(0, 20)
        .map(({ _score, ...rest }: any) => ({
          ...rest,
          thumbnailImage: rest.thumbnailImage || rest.image || '',
        }));
      
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
          {loading ? (
            <>Searching for "{query}"...</>
          ) : hasSearched ? (
            <>Results for "{query}" ({products.length} products found)</>
          ) : (
            <>Enter a search term to find products</>
          )}
        </p>
        
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin mb-4" />
            <p className="text-muted-foreground">Searching for products...</p>
          </div>
        ) : hasSearched && products.length === 0 ? (
          <div className="text-center py-16">
            <h3 className="text-2xl font-semibold mb-4">No products found</h3>
            <p className="text-muted-foreground mb-6">
              We couldn't find any products matching "{query}". Try different keywords or browse our categories.
            </p>
            <Button 
              onClick={() => window.location.href = '/'}
              className="bg-gradient-primary hover:opacity-90"
            >
              Browse Categories
            </Button>
          </div>
        ) : hasSearched ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {products.map((product, index) => (
              <ProductCard key={`${product.asin}-${index}`} product={product} />
            ))}
          </div>
        ) : (
          <div className="text-center py-16">
            <h3 className="text-2xl font-semibold mb-4">Start Your Search</h3>
            <p className="text-muted-foreground">
              Use the search bar above to find products, or browse our categories below.
            </p>
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