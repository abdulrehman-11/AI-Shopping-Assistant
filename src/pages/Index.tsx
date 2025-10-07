import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import Header from '@/components/Header';
import CategoryCard from '@/components/CategoryCard';
import ChatBot from '@/components/ChatBot';
import { Button } from '@/components/ui/button';
import { MessageCircle, ShoppingBag, Users, Shield, Truck } from 'lucide-react';
import productsData from '@/data/products.json';

// Import category images
import menBagsImage from '@/assets/men-bags.jpg';
import menJewelryImage from '@/assets/men-jewelry.jpg';
import menShoesImage from '@/assets/men-shoes.jpg';
import menClothingImage from '@/assets/men-clothing.jpg';
import nikeShoesImage from '@/assets/nike-shoes.jpg';
import womenClothingImage from '@/assets/women-clothing.jpg';

const Index = () => {
  const [isChatOpen, setIsChatOpen] = useState(false);

  // Category data with product counts
  const categories = [
    {
      title: "Men's Bags",
      slug: "men-bags",
      image: menBagsImage,
      productCount: productsData.filter(p => p.category === 'Men Bags').length,
      description: "Premium bags, briefcases, and backpacks for the modern man"
    },
    {
      title: "Men's Jewelry",  
      slug: "men-jewelry",
      image: menJewelryImage,
      productCount: productsData.filter(p => p.category === 'Men Jwelerry').length,
      description: "Elegant watches, rings, and accessories to complete your style"
    },
    {
      title: "Men's Shoes",
      slug: "men-shoes", 
      image: menShoesImage,
      productCount: productsData.filter(p => p.category === 'Men Shoes').length,
      description: "From casual sneakers to formal dress shoes"
    },
    {
      title: "Men's Clothing",
      slug: "men-clothing",
      image: menClothingImage,
      productCount: productsData.filter(p => p.category === 'Men Clothing').length,
      description: "Stylish apparel for every occasion and season"
    },
    {
      title: "Nike Shoes",
      slug: "nike-shoes",
      image: nikeShoesImage,
      productCount: productsData.filter(p => p.category === 'Nike Shoes').length,
      description: "Iconic Nike sneakers and athletic footwear"
    },
    {
      title: "Women's Clothing",
      slug: "women-clothing",
      image: womenClothingImage,
      productCount: productsData.filter(p => p.category === 'Women Clothing').length,
      description: "Fashion-forward clothing for the modern woman"
    }
  ];

  const features = [
    {
      icon: ShoppingBag,
      title: "Curated Selection",
      description: "Hand-picked products from trusted Amazon sellers"
    },
    {
      icon: Users,
      title: "AI-Powered",
      description: "Smart recommendations tailored to your preferences"
    },
    {
      icon: Shield,
      title: "Secure Shopping",
      description: "Safe and secure transactions through Amazon"
    },
    {
      icon: Truck,
      title: "Fast Delivery",
      description: "Quick shipping with Amazon Prime benefits"
    }
  ];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      {/* Hero Section */}
      <section className="bg-gradient-hero text-white py-20">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-5xl font-bold mb-6 animate-fade-in">
            Discover Amazing Products with AI
          </h1>
          <p className="text-xl mb-8 max-w-2xl mx-auto opacity-90 animate-fade-in">
            Shop smarter with our AI-powered shopping assistant. Find the perfect products 
            from thousands of options, get personalized recommendations, and enjoy seamless Amazon shopping.
          </p>
          <div className="flex justify-center animate-fade-in">
            <Button 
              size="lg" 
              className="backdrop-blur-md bg-white/20 border border-white/30 text-white hover:bg-white/30 hover:scale-105 hover:shadow-2xl px-12 py-3 text-lg font-semibold transition-all duration-300 ease-in-out"
              onClick={() => setIsChatOpen(true)}
            >
              Try AI Assistant
            </Button>
          </div>
        </div>
      </section>

      {/* Categories Section */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">Shop by Category</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Browse our carefully curated categories featuring thousands of products from Amazon
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {categories.map((category) => (
              <CategoryCard
                key={category.slug}
                title={category.title}
                slug={category.slug}
                image={category.image}
                productCount={category.productCount}
                description={category.description}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">Why Shop With Us?</h2>
            <p className="text-xl text-muted-foreground">
              Experience the future of online shopping with our AI-powered platform
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div key={index} className="text-center p-6 bg-card rounded-lg shadow-card">
                <div className="w-16 h-16 bg-gradient-primary rounded-full flex items-center justify-center mx-auto mb-4">
                  <feature.icon className="h-8 w-8 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-primary text-primary-foreground">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-4xl font-bold mb-4">Ready to Start Shopping?</h2>
          <p className="text-xl mb-8 opacity-90 max-w-2xl mx-auto">
            Join thousands of satisfied customers who trust our AI-powered shopping experience
          </p>
          <Button 
            size="lg" 
            className="bg-white text-primary hover:bg-gray-100 px-8 py-3 text-lg font-semibold"
            onClick={() => setIsChatOpen(true)}
          >
            Get Started Now
          </Button>
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

export default Index;