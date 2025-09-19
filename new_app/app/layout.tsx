/**
 * Root Layout Component
 *
 * Root layout for React app with head tags and body wrapper.
 */

import React from "react";

interface LayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: LayoutProps) {
  return (
    <>
      {/* Global styles */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            * {
              box-sizing: border-box;
              margin: 0;
              padding: 0;
            }
            
            body {
              font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
              line-height: 1.6;
              color: #333;
              background-color: #fff;
            }
            
            #root {
              min-height: 100vh;
              display: flex;
              flex-direction: column;
            }
          `,
        }}
      />
      {/* Navigation */}
      <nav className="navbar">
        <div className="nav-container">
          <a href="/" className="nav-brand">
            Tavo
          </a>

          <div className="nav-links">
            <a href="/" className="nav-link">
              Home
            </a>
            <a href="/about" className="nav-link">
              About
            </a>
            <a href="/api/hello" className="nav-link">
              API
            </a>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="main-content">{children}</main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-container">
          <p>&copy; 2025 Tavo Framework. Built with Python + Rust + React.</p>
        </div>
      </footer>

      {/* Navigation styles */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
            .navbar {
              background: #fff;
              border-bottom: 1px solid #e5e7eb;
              padding: 0 1rem;
            }
            
            .nav-container {
              max-width: 1200px;
              margin: 0 auto;
              display: flex;
              justify-content: space-between;
              align-items: center;
              height: 64px;
            }
            
            .nav-brand {
              font-size: 1.5rem;
              font-weight: 700;
              color: #2563eb;
              text-decoration: none;
            }
            
            .nav-links {
              display: flex;
              gap: 2rem;
            }
            
            .nav-link {
              color: #6b7280;
              text-decoration: none;
              font-weight: 500;
              transition: color 0.2s;
            }
            
            .nav-link:hover {
              color: #2563eb;
            }
            
            .main-content {
              flex: 1;
              padding: 2rem 1rem;
              max-width: 1200px;
              margin: 0 auto;
              width: 100%;
            }
            
            .footer {
              background: #f9fafb;
              border-top: 1px solid #e5e7eb;
              padding: 1rem;
              margin-top: auto;
            }
            
            .footer-container {
              max-width: 1200px;
              margin: 0 auto;
              text-align: center;
              color: #6b7280;
              font-size: 0.875rem;
            }
            
            @media (max-width: 768px) {
              .nav-container {
                flex-direction: column;
                height: auto;
                padding: 1rem 0;
              }
              
              .nav-links {
                margin-top: 1rem;
                gap: 1rem;
              }
              
              .main-content {
                padding: 1rem;
              }
            }
          `,
        }}
      />
    </>
  );
}

// Type definitions for better TypeScript support
// export interface PageProps {
//   params?: Record<string, string>;
//   searchParams?: Record<string, string>;
// }

// export interface LayoutContext {
//   pathname: string;
//   query: Record<string, string>;
//   user?: {
//     id: number;
//     name: string;
//     email: string;
//   };
// }

// /*
// Unit tests as comments:
// 1. test_layout_renders_children() - verify children are rendered correctly
// 2. test_layout_title_prop() - test custom title prop is applied
// 3. test_responsive_navigation() - verify navigation works on mobile devices
// */
