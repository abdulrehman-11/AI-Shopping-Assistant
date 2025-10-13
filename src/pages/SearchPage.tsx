import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import Header from '@/components/Header';
import ProductCard from '@/components/ProductCard';
import { Button } from '@/components/ui/button';
import ChatBot from '@/components/ChatBot';
import { Loader2, MessageCircle } from 'lucide-react';
import productsData from '@/data/products.json';

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

  const searchProducts = (searchQuery: string) => {
    setLoading(true);
    setHasSearched(true);
    setProducts([]);
    
    // Simulate loading delay for better UX
    setTimeout(() => {
      const queryLc = searchQuery.toLowerCase().trim();
      const queryWords = queryLc.split(/\s+/).filter(word => word.length > 2);
      
      console.log('Searching for:', queryLc);
      console.log('Query words:', queryWords);
      
      const scored = productsData
        .map((p: any) => {
          const title = p.title?.toLowerCase() || '';
          const brand = p.brand?.toLowerCase() || '';
          const category = p.category?.toLowerCase() || '';
          const description = p.description?.toLowerCase() || '';
          
          let score = 0;
          
          // Exact matches (highest priority)
          if (title === queryLc) score += 100;
          if (brand === queryLc) score += 80;
          
          // Full query contained in title
          if (title.includes(queryLc)) score += 50;
          
          // Brand matches with query
          if (brand.includes(queryLc)) score += 40;
          
          // Category matches
          if (category.includes(queryLc)) score += 30;
          
          // Word-by-word matching
          if (queryWords.length > 0) {
            const titleMatches = queryWords.filter(word => title.includes(word)).length;
            const brandMatches = queryWords.filter(word => brand.includes(word)).length;
            const categoryMatches = queryWords.filter(word => category.includes(word)).length;
            
            const totalMatches = titleMatches + brandMatches + categoryMatches;
            const matchRatio = totalMatches / (queryWords.length * 3); // Out of possible matches
            
            // Require at least one word match
            if (totalMatches > 0) {
              score += totalMatches * 8;
              
              // Bonus for high match ratio
              if (matchRatio >= 0.5) {
                score += 15;
              }
            }
          }
          
          // Bonus for quality products
          if (p.stars && p.stars >= 4.0) score += 2;
          if (p.reviewsCount && p.reviewsCount > 1000) score += 2;
          if (p.thumbnailImage) score += 1; // Bonus for having image
          
          return { ...p, _searchScore: score };
        })
        .filter((p: any) => p._searchScore >= 15) // Only relevant results
        .sort((a: any, b: any) => b._searchScore - a._searchScore)
        .map(({ _searchScore, ...rest }: any) => rest);
      
      console.log(`Found ${scored.length} relevant products`);
      if (scored.length > 0) {
        console.log('Top result:', scored[0].title);
        console.log('Has image:', !!scored[0].thumbnailImage);
      }
      
      setProducts(scored);
      setLoading(false);
    }, 300); // Small delay for smooth UX
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
            <>Results for "{query}" ({products.length} {products.length === 1 ? 'product' : 'products'} found)</>
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
              Use the search bar above to find products, or browse our categories.
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
          <MessageCircle className="h-6 w-6" />
        </Button>
      )}
      
      {isChatOpen && <ChatBot onClose={() => setIsChatOpen(false)} />}
    </div>
  );
};

export default SearchPage;