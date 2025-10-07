import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Header from '@/components/Header';
import ProductCard from '@/components/ProductCard';
import ChatBot from '@/components/ChatBot';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MessageCircle, SlidersHorizontal } from 'lucide-react';
import productsData from '@/data/products.json';

const CategoryPage = () => {
  const { slug } = useParams<{ slug: string }>();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [sortBy, setSortBy] = useState('default');
  const [priceFilter, setPriceFilter] = useState('all');

  // Map URL slugs to category names in the JSON
  const categoryMapping: { [key: string]: string } = {
    'men-bags': 'Men Bags',
    'men-jewelry': 'Men Jwelerry',
    'men-shoes': 'Men Shoes', 
    'men-clothing': 'Men Clothing',
    'nike-shoes': 'Nike Shoes',
    'women-clothing': 'Women Clothing'
  };

  const categoryName = categoryMapping[slug || ''];
  
  // Filter products by category
  const categoryProducts = useMemo(() => {
    return productsData.filter(product => product.category === categoryName);
  }, [categoryName]);

  // Sort and filter products
  const filteredAndSortedProducts = useMemo(() => {
    let filtered = [...categoryProducts];

    // Price filtering
    if (priceFilter !== 'all') {
      filtered = filtered.filter(product => {
        if (!product.price) return priceFilter === 'unknown';
        const price = product.price.value;
        switch (priceFilter) {
          case 'under-25': return price < 25;
          case '25-50': return price >= 25 && price <= 50;
          case '50-100': return price >= 50 && price <= 100;
          case 'over-100': return price > 100;
          default: return true;
        }
      });
    }

    // Sorting
    switch (sortBy) {
      case 'price-low':
        return filtered.sort((a, b) => {
          const priceA = a.price?.value || 0;
          const priceB = b.price?.value || 0;
          return priceA - priceB;
        });
      case 'price-high':
        return filtered.sort((a, b) => {
          const priceA = a.price?.value || 0;
          const priceB = b.price?.value || 0;
          return priceB - priceA;
        });
      case 'rating':
        return filtered.sort((a, b) => {
          const ratingA = a.stars || 0;
          const ratingB = b.stars || 0;
          return ratingB - ratingA;
        });
      case 'reviews':
        return filtered.sort((a, b) => {
          const reviewsA = a.reviewsCount || 0;
          const reviewsB = b.reviewsCount || 0;
          return reviewsB - reviewsA;
        });
      default:
        return filtered;
    }
  }, [categoryProducts, sortBy, priceFilter]);

  if (!categoryName) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="container mx-auto px-4 py-16 text-center">
          <h1 className="text-4xl font-bold mb-4">Category Not Found</h1>
          <p className="text-xl text-muted-foreground">
            The category you're looking for doesn't exist.
          </p>
        </div>
      </div>
    );
  }

  const categoryTitle = slug?.split('-').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      {/* Category Header */}
      <section className="bg-gradient-primary text-primary-foreground py-12">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold mb-2">{categoryTitle}</h1>
          <p className="text-xl opacity-90">
            {filteredAndSortedProducts.length} products available
          </p>
        </div>
      </section>

      {/* Filters and Sorting */}
      <section className="bg-muted/30 py-4">
        <div className="container mx-auto px-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center space-x-2">
              <SlidersHorizontal className="h-5 w-5 text-muted-foreground" />
            </div>
            
            <div className="flex flex-wrap items-center space-x-4">
              <Select value={priceFilter} onValueChange={setPriceFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Price Range" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Prices</SelectItem>
                  <SelectItem value="under-25">Under $25</SelectItem>
                  <SelectItem value="25-50">$25 - $50</SelectItem>
                  <SelectItem value="50-100">$50 - $100</SelectItem>
                  <SelectItem value="over-100">Over $100</SelectItem>
                  <SelectItem value="unknown">Price Unknown</SelectItem>
                </SelectContent>
              </Select>

              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Sort By" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Default</SelectItem>
                  <SelectItem value="price-low">Price: Low to High</SelectItem>
                  <SelectItem value="price-high">Price: High to Low</SelectItem>
                  <SelectItem value="rating">Highest Rated</SelectItem>
                  <SelectItem value="reviews">Most Reviews</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </section>

      {/* Products Grid */}
      <section className="py-8">
        <div className="container mx-auto px-4">
          {filteredAndSortedProducts.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
              {filteredAndSortedProducts.map((product, index) => (
                <ProductCard key={`${product.asin}-${index}`} product={product} />
              ))}
            </div>
          ) : (
            <div className="text-center py-16">
              <h3 className="text-2xl font-semibold mb-4">No products found</h3>
              <p className="text-muted-foreground">
                Try adjusting your filters or browse other categories.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* Chat Button */}
      {!isChatOpen && (
        <Button
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-primary hover:opacity-90 shadow-2xl z-40 animate-scale-in"
          size="lg"
        >
          <MessageCircle className="h-6 w-6" />
        </Button>
      )}

      {/* ChatBot */}
      {isChatOpen && <ChatBot onClose={() => setIsChatOpen(false)} />}
    </div>
  );
};

export default CategoryPage;