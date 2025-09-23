import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';

interface CategoryCardProps {
  title: string;
  slug: string;
  image: string;
  productCount: number;
  description: string;
}

const CategoryCard: React.FC<CategoryCardProps> = ({ 
  title, 
  slug, 
  image, 
  productCount, 
  description 
}) => {
  return (
    <Card className="group overflow-hidden bg-gradient-card shadow-card hover:shadow-hover transition-all duration-300 transform hover:-translate-y-2">
      <div className="relative h-48 overflow-hidden">
        <img
          src={image}
          alt={title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
        <div className="absolute bottom-4 left-4 text-white">
          <h3 className="text-xl font-bold mb-1">{title}</h3>
          <p className="text-sm opacity-90">{productCount} products</p>
        </div>
      </div>
      
      <CardContent className="p-6">
        <p className="text-muted-foreground mb-4 line-clamp-2">{description}</p>
        
        <Link to={`/category/${slug}`}>
          <Button className="w-full bg-gradient-primary hover:opacity-90 transition-opacity group">
            Shop Now
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
};

export default CategoryCard;