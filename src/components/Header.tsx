import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, ShoppingCart, User, Menu } from 'lucide-react';

const Header = () => {
  const location = useLocation();

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
              />
              <Button
                size="sm"
                className="absolute right-1 top-1 bottom-1 px-3 bg-gradient-primary hover:opacity-90"
              >
                <Search className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Right side buttons */}
          <div className="flex items-center space-x-4">
            <Button variant="ghost" size="sm" className="flex items-center space-x-2">
              <User className="h-4 w-4" />
              <span className="hidden md:inline">Account</span>
            </Button>
            <Button variant="ghost" size="sm" className="flex items-center space-x-2">
              <ShoppingCart className="h-4 w-4" />
              <span className="hidden md:inline">Cart</span>
            </Button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="py-2 border-t border-border">
          <div className="flex items-center space-x-8 overflow-x-auto">
            <Button
              variant="ghost"
              size="sm"
              className="flex items-center space-x-1"
            >
              <Menu className="h-4 w-4" />
              <span>All</span>
            </Button>
            
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