/**
 * Home Page Component
 * 
 * Example home page component for SSR/hydration demo.
 */

import React, { useState, useEffect } from 'react';
// import Hello from './components/Hello';

interface HomePageProps {
  initialData?: {
    message?: string;
    timestamp?: string;
  };
}

export default function HomePage({ initialData }: HomePageProps) {
  const [apiData, setApiData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Fetch data from API
  const fetchHelloData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/hello?name=Tavo');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      setApiData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch data on component mount (client-side only)
  useEffect(() => {
    fetchHelloData();
  }, []);
  
  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-title">
            Welcome to <span className="brand">Tavo</span>
          </h1>
          <p className="hero-subtitle">
            Full-stack framework combining Python backends with Rust/SWC-powered React SSR from Cyberwizdev Team
          </p>
          
          <div className="hero-features">
            <div className="feature">
              <div className="feature-icon">🐍</div>
              <h3>Python Backend</h3>
              <p>Powerful async Python with Starlette</p>
            </div>
            
            <div className="feature">
              <div className="feature-icon">⚡</div>
              <h3>Rust Bundler</h3>
              <p>Lightning-fast builds with SWC</p>
            </div>
            
            <div className="feature">
              <div className="feature-icon">⚛️</div>
              <h3>React SSR</h3>
              <p>Server-side rendering with hydration</p>
            </div>
          </div>
        </div>
      </section>
      
      {/* Demo Section */}
      <section className="demo">
        <div className="demo-content">
          <h2>Live Demo</h2>
          
          {/* Hello Component */}
          <div className="demo-card">
            <h3>Component Demo</h3>
            {/* <Hello name="Tavo Developer" /> */}
          </div>
          
          {/* API Demo */}
          <div className="demo-card">
            <h3>API Demo</h3>
            
            <button 
              onClick={fetchHelloData} 
              disabled={loading}
              className="api-button"
            >
              {loading ? 'Loading...' : 'Fetch from API'}
            </button>
            
            {error && (
              <div className="error-message">
                Error: {error}
              </div>
            )}
            
            {apiData && (
              <div className="api-response">
                <h4>API Response:</h4>
                <pre>{JSON.stringify(apiData, null, 2)}</pre>
              </div>
            )}
          </div>
          
          {/* SSR Info */}
          <div className="demo-card">
            <h3>SSR Information</h3>
            <p>This page was server-side rendered and then hydrated on the client.</p>
            {initialData && (
              <div className="ssr-data">
                <h4>Initial SSR Data:</h4>
                <pre>{JSON.stringify(initialData, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      </section>
      
      {/* Styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          .home-page {
            min-height: 100vh;
          }
          
          .hero {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4rem 2rem;
            text-align: center;
          }
          
          .hero-content {
            max-width: 800px;
            margin: 0 auto;
          }
          
          .hero-title {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 1rem;
            line-height: 1.2;
          }
          
          .brand {
            color: #fbbf24;
          }
          
          .hero-subtitle {
            font-size: 1.25rem;
            margin-bottom: 3rem;
            opacity: 0.9;
          }
          
          .hero-features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 2rem;
            margin-top: 3rem;
          }
          
          .feature {
            text-align: center;
          }
          
          .feature-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
          }
          
          .feature h3 {
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
          }
          
          .feature p {
            opacity: 0.8;
          }
          
          .demo {
            padding: 4rem 2rem;
            background: #f9fafb;
          }
          
          .demo-content {
            max-width: 800px;
            margin: 0 auto;
          }
          
          .demo h2 {
            text-align: center;
            font-size: 2rem;
            margin-bottom: 3rem;
            color: #1f2937;
          }
          
          .demo-card {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem;
          }
          
          .demo-card h3 {
            margin-bottom: 1rem;
            color: #1f2937;
          }
          
          .api-button {
            background: #2563eb;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.2s;
          }
          
          .api-button:hover:not(:disabled) {
            background: #1d4ed8;
          }
          
          .api-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }
          
          .error-message {
            color: #dc2626;
            margin-top: 1rem;
            padding: 0.75rem;
            background: #fef2f2;
            border-radius: 4px;
            border: 1px solid #fecaca;
          }
          
          .api-response, .ssr-data {
            margin-top: 1rem;
          }
          
          .api-response h4, .ssr-data h4 {
            margin-bottom: 0.5rem;
            color: #374151;
          }
          
          .api-response pre, .ssr-data pre {
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.875rem;
            border: 1px solid #e5e7eb;
          }
          
          @media (max-width: 768px) {
            .hero {
              padding: 2rem 1rem;
            }
            
            .hero-title {
              font-size: 2rem;
            }
            
            .hero-features {
              grid-template-columns: 1fr;
              gap: 1.5rem;
            }
            
            .demo {
              padding: 2rem 1rem;
            }
            
            .demo-card {
              padding: 1.5rem;
            }
          }
        `
      }} />
    </div>
  );
}

// Server-side data fetching (would be called during SSR)
export async function getServerSideProps() {
  // This function would be called during server-side rendering
  // to fetch initial data for the page
  
  return {
    props: {
      initialData: {
        message: "Server-side rendered at " + new Date().toISOString(),
        timestamp: new Date().toISOString()
      }
    }
  };
}

// Client-side hydration helper
export function hydrateHomePage() {
  // This would be called after the page is hydrated on the client
  console.log('🚀 Home page hydrated');
  
  // Add any client-side initialization here
  if (typeof window !== 'undefined') {
    // Client-side only code
    console.log('Client-side JavaScript loaded');
  }
}

/*
Unit tests as comments:
1. test_layout_renders_correctly() - verify layout renders with proper HTML structure
2. test_api_data_fetching() - test API data fetching and error handling
3. test_responsive_design() - verify layout works on different screen sizes
*/