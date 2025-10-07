import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Menu } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";


const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  const handleSearch = () => {
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className="bg-background border-b border-border sticky top-0 z-50">
      <div className="container mx-auto px-4">
        {/* Top bar */}
        <div className="flex items-center justify-between py-3">
          <Link to="/" className="flex items-center space-x-2">
            <div className="text-2xl font-bold bg-gradient-primary bg-clip-text text-transparent">
              ShopSmart
            </div>
          </Link>

          {/* Search bar */}
          <div className="flex-1 max-w-2xl mx-8">
          <div className="relative">
           <Input
            type="text"
            placeholder="Search products..."
            className="w-full pl-4 pr-12 py-2 rounded-lg border-2 border-muted focus:border-primary transition-colors"
            value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
                <Button
                size="sm"
                  className="absolute right-1 top-1 bottom-1 px-3 bg-gradient-primary hover:opacity-90"
                  onClick={handleSearch}
                >
                <Search className="h-4 w-4" />
                </Button>
                     </div>
                     </div>

          {/* Right side kept minimal intentionally */}
          <div className="flex items-center space-x-4" />
        </div>

        {/* Navigation */}
        <nav className="py-2 border-t border-border">
          <div className="flex items-center space-x-8 overflow-x-auto">
            <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
  <SheetTrigger asChild>
    <Button
      variant="ghost"
      size="sm"
      className="flex items-center space-x-1"
    >
      <Menu className="h-4 w-4" />
      <span>All</span>
    </Button>
  </SheetTrigger>
  <SheetContent side="left" className="w-80">
    <div className="py-6">
      <h3 className="text-lg font-semibold mb-4">All Categories</h3>
      <p className="text-sm text-muted-foreground mb-6">Browse all product categories</p>
      
      <div className="space-y-2">
        {/* Category links */}
        <Link to="/category/men-bags" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">👜</div>
            <div>
              <p className="font-medium">Men's Bags</p>
              <p className="text-sm text-muted-foreground">Premium bags, briefcases, and backpacks</p>
            </div>
          </div>
        </Link>

        <Link to="/category/men-jewelry" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">💍</div>
            <div>
              <p className="font-medium">Men's Jewelry</p>
              <p className="text-sm text-muted-foreground">Elegant watches, rings, and accessories</p>
            </div>
          </div>
        </Link>

        <Link to="/category/men-shoes" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">👟</div>
            <div>
              <p className="font-medium">Men's Shoes</p>
              <p className="text-sm text-muted-foreground">From casual sneakers to formal dress shoes</p>
            </div>
          </div>
        </Link>

        <Link to="/category/men-clothing" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">👕</div>
            <div>
              <p className="font-medium">Men's Clothing</p>
              <p className="text-sm text-muted-foreground">Stylish apparel for every occasion</p>
            </div>
          </div>
        </Link>

        <Link to="/category/nike-shoes" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">👟</div>
            <div>
              <p className="font-medium">Nike Shoes</p>
              <p className="text-sm text-muted-foreground">Iconic Nike sneakers and athletic footwear</p>
            </div>
          </div>
        </Link>

        <Link to="/category/women-clothing" className="block" onClick={() => setIsSheetOpen(false)}>
          <div className="flex items-center space-x-3 p-3 rounded-lg hover:bg-muted transition-colors border border-primary/20">
            <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">👗</div>
            <div>
              <p className="font-medium">Women's Clothing</p>
              <p className="text-sm text-muted-foreground">Fashion-forward clothing for the modern woman</p>
            </div>
          </div>
        </Link>
      </div>

      <div className="mt-8 pt-6 border-t">
        <h4 className="font-medium mb-2">Need Help?</h4>
        <p className="text-sm text-muted-foreground mb-3">Use our AI assistant to find the perfect products</p>
        <Button className="w-full bg-gradient-primary">Ask AI Assistant</Button>
      </div>
    </div>
  </SheetContent>
</Sheet>

            
            <Link to="/category/men-bags">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/men-bags' ? 'text-primary font-semibold' : ''}`}
              >
                Men's Bags
              </Button>
            </Link>
            
            <Link to="/category/men-jewelry">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/men-jewelry' ? 'text-primary font-semibold' : ''}`}
              >
                Men's Jewelry
              </Button>
            </Link>
            
            <Link to="/category/men-shoes">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/men-shoes' ? 'text-primary font-semibold' : ''}`}
              >
                Men's Shoes
              </Button>
            </Link>
            
            <Link to="/category/men-clothing">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/men-clothing' ? 'text-primary font-semibold' : ''}`}
              >
                Men's Clothing
              </Button>
            </Link>
            
            <Link to="/category/nike-shoes">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/nike-shoes' ? 'text-primary font-semibold' : ''}`}
              >
                Nike Shoes
              </Button>
            </Link>
            
            <Link to="/category/women-clothing">
              <Button 
                variant="ghost" 
                size="sm"
                className={`whitespace-nowrap ${location.pathname === '/category/women-clothing' ? 'text-primary font-semibold' : ''}`}
              >
                Women's Clothing
              </Button>
            </Link>
          </div>
        </nav>
      </div>
    </header>
  );
};

export default Header;