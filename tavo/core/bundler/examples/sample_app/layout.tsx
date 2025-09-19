import React from 'react';

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Tavo Sample App</title>
      </head>
      <body>
        <header style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderBottom: '1px solid #e9ecef' }}>
          <nav>
            <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Tavo Sample App</h1>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0 0 0', display: 'flex', gap: '1rem' }}>
              <li><a href="/" style={{ textDecoration: 'none', color: '#0066cc' }}>Home</a></li>
              <li><a href="/about" style={{ textDecoration: 'none', color: '#0066cc' }}>About</a></li>
              <li><a href="/dashboard" style={{ textDecoration: 'none', color: '#0066cc' }}>Dashboard</a></li>
            </ul>
          </nav>
        </header>
        
        <main style={{ padding: '2rem', minHeight: 'calc(100vh - 200px)' }}>
          {children}
        </main>
        
        <footer style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderTop: '1px solid #e9ecef', textAlign: 'center' }}>
          <p style={{ margin: 0, color: '#6c757d' }}>
            Built with Tavo Framework &copy; 2025
          </p>
        </footer>
      </body>
    </html>
  );
}