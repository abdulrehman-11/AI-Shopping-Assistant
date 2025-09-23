import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Star, ExternalLink } from 'lucide-react';

interface Product {
  title: string;
  asin: string;
  brand?: string;
  stars?: number;
  reviewsCount?: number;
  thumbnailImage: string;
  description?: string;
  price?: {
    value: number;
    currency: string;
  };
  url: string;
  category: string;
}

interface ProductCardProps {
  product: Product;
}

const ProductCard: React.FC<ProductCardProps> = ({ product }) => {
  const handleProductClick = () => {
    window.open(product.url, '_blank', 'noopener,noreferrer');
  };

  const renderStars = (rating?: number) => {
    if (!rating) return null;
    
    const stars = [];
    const fullStars = Math.floor(rating);
    const hasHalfStar = rating % 1 >= 0.5;
    
    for (let i = 0; i < fullStars; i++) {
      stars.push(
        <Star key={i} className="h-4 w-4 fill-yellow-400 text-yellow-400" />
      );
    }
    
    if (hasHalfStar) {
      stars.push(
        <div key="half" className="relative">
          <Star className="h-4 w-4 text-gray-300" />
          <div className="absolute inset-0 overflow-hidden w-1/2">
            <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
          </div>
        </div>
      );
    }
    
    const emptyStars = 5 - stars.length;
    for (let i = 0; i < emptyStars; i++) {
      stars.push(
        <Star key={`empty-${i}`} className="h-4 w-4 text-gray-300" />
      );
    }
    
    return stars;
  };

  return (
    <Card className="group overflow-hidden bg-card shadow-card hover:shadow-hover transition-all duration-300 transform hover:-translate-y-1 cursor-pointer">
      <div className="relative aspect-square overflow-hidden">
        <img
          src={product.thumbnailImage}
          alt={product.title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="lazy"
        />
        {product.brand && (
          <Badge className="absolute top-2 left-2 bg-primary text-primary-foreground">
            {product.brand}
          </Badge>
        )}
      </div>
      
      <CardContent className="p-4">
        <h3 className="font-semibold text-sm line-clamp-2 mb-2 min-h-[2.5rem] leading-tight">
          {product.title}
        </h3>
        
        {product.description && (
          <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
            {product.description}
          </p>
        )}
        
        {product.stars && (
          <div className="flex items-center gap-1 mb-2">
            <div className="flex">
              {renderStars(product.stars)}
            </div>
            <span className="text-xs text-muted-foreground ml-1">
              {product.stars} ({product.reviewsCount?.toLocaleString() || 0})
            </span>
          </div>
        )}
        
        <div className="flex items-center justify-between">
          {product.price ? (
            <span className="text-lg font-bold text-primary">
              {product.price.currency}{product.price.value}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">Price on Amazon</span>
          )}
          
          <Button
            onClick={handleProductClick}
            size="sm"
            className="bg-gradient-primary hover:opacity-90 transition-opacity"
          >
            <ExternalLink className="h-3 w-3 mr-1" />
            View
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default ProductCard;