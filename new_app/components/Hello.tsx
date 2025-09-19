/**
 * Hello Component
 * 
 * Small working React component to import into pages.
 */

import { useState, useEffect } from 'react';

interface HelloProps {
  name?: string;
  showTime?: boolean;
  className?: string;
}

export default function Hello({ 
  name = "World", 
  showTime = true,
  className = "" 
}: HelloProps) {
  const [currentTime, setCurrentTime] = useState<string>("");
  const [clickCount, setClickCount] = useState(0);
  
  // Update time every second
  useEffect(() => {
    if (!showTime) return;
    
    const updateTime = () => {
      setCurrentTime(new Date().toLocaleTimeString());
    };
    
    updateTime(); // Initial time
    const interval = setInterval(updateTime, 1000);
    
    return () => clearInterval(interval);
  }, [showTime]);
  
  const handleClick = () => {
    setClickCount(prev => prev + 1);
  };
  
  return (
    <div className={`hello-component ${className}`}>
      <div className="hello-content">
        <h2 className="hello-title">
          Hello, {name}! 👋
        </h2>
        
        <p className="hello-description">
          This is a React component rendered by the Tavo framework.
        </p>
        
        {showTime && (
          <div className="time-display">
            <span className="time-label">Current time:</span>
            <span className="time-value">{currentTime}</span>
          </div>
        )}
        
        <div className="interaction-demo">
          <button 
            onClick={handleClick}
            className="click-button"
          >
            Click me! ({clickCount})
          </button>
          
          {clickCount > 0 && (
            <p className="click-message">
              {clickCount === 1 
                ? "Thanks for clicking!" 
                : `You've clicked ${clickCount} times!`
              }
            </p>
          )}
        </div>
        
        <div className="tech-stack">
          <h3>Tech Stack:</h3>
          <ul>
            <li>⚛️ React with TypeScript</li>
            <li>🐍 Python backend (Starlette)</li>
            <li>🦀 Rust bundler (SWC)</li>
            <li>🔥 Hot Module Replacement</li>
          </ul>
        </div>
      </div>
      
      {/* Component styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          .hello-component {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border-radius: 12px;
            padding: 2rem;
            margin: 1rem 0;
            border: 1px solid #e0f2fe;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          }
          
          .hello-content {
            max-width: 600px;
            margin: 0 auto;
            text-align: center;
          }
          
          .hello-title {
            color: #0c4a6e;
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 1rem;
          }
          
          .hello-description {
            color: #0369a1;
            font-size: 1.1rem;
            margin-bottom: 2rem;
            line-height: 1.6;
          }
          
          .time-display {
            background: rgba(255, 255, 255, 0.8);
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border: 1px solid #bae6fd;
          }
          
          .time-label {
            color: #0369a1;
            font-weight: 500;
            margin-right: 0.5rem;
          }
          
          .time-value {
            color: #0c4a6e;
            font-weight: 600;
            font-family: 'Monaco', 'Menlo', monospace;
          }
          
          .interaction-demo {
            margin: 2rem 0;
          }
          
          .click-button {
            background: #2563eb;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
          }
          
          .click-button:hover {
            background: #1d4ed8;
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(37, 99, 235, 0.3);
          }
          
          .click-button:active {
            transform: translateY(0);
          }
          
          .click-message {
            margin-top: 1rem;
            color: #059669;
            font-weight: 500;
            animation: fadeIn 0.3s ease-in;
          }
          
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
          }
          
          .tech-stack {
            background: rgba(255, 255, 255, 0.9);
            padding: 1.5rem;
            border-radius: 8px;
            margin-top: 2rem;
            text-align: left;
            border: 1px solid #bae6fd;
          }
          
          .tech-stack h3 {
            color: #0c4a6e;
            margin-bottom: 1rem;
            text-align: center;
          }
          
          .tech-stack ul {
            list-style: none;
            padding: 0;
          }
          
          .tech-stack li {
            color: #0369a1;
            padding: 0.5rem 0;
            border-bottom: 1px solid #e0f2fe;
          }
          
          .tech-stack li:last-child {
            border-bottom: none;
          }
          
          @media (max-width: 768px) {
            .hello-component {
              padding: 1.5rem;
              margin: 0.5rem 0;
            }
            
            .hello-title {
              font-size: 1.5rem;
            }
            
            .hello-description {
              font-size: 1rem;
            }
            
            .tech-stack {
              text-align: center;
            }
          }
        `
      }} />
    </div>
  );
}

// Props interface for better type safety
export interface HelloComponentProps extends HelloProps {
  // Additional props can be added here
}

// Helper function for formatting time
function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: true,
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit'
  });
}

// Custom hook for API data fetching
export function useApiData(endpoint: string) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fetch failed');
    } finally {
      setLoading(false);
    }
  };
  
  return { data, loading, error, fetchData };
}

/*
Unit tests as comments:
1. test_hello_component_renders() - verify component renders with default props
2. test_time_display_updates() - test that time display updates correctly
3. test_click_interaction() - verify click counter works and shows messages
*/