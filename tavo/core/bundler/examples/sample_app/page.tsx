import React from 'react';

export default function HomePage() {
  return (
    <div>
      <h1 style={{ color: '#333', marginBottom: '1rem' }}>
        Welcome to Tavo
      </h1>
      
      <p style={{ fontSize: '1.1rem', lineHeight: '1.6', color: '#666', marginBottom: '2rem' }}>
        This is a sample application built with the Tavo framework. 
        Tavo provides a modern, Python-first approach to building full-stack web applications 
        with React components and server-side rendering.
      </p>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ padding: '1.5rem', border: '1px solid #e9ecef', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#333' }}>App Router</h3>
          <p style={{ margin: 0, color: '#666' }}>
            File-based routing with layouts, pages, and dynamic routes. 
            Just create files in the app directory to define routes.
          </p>
        </div>
        
        <div style={{ padding: '1.5rem', border: '1px solid #e9ecef', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#333' }}>Server-Side Rendering</h3>
          <p style={{ margin: 0, color: '#666' }}>
            Built-in SSR support with hydration for interactive client-side features.
            Fast initial page loads with full interactivity.
          </p>
        </div>
        
        <div style={{ padding: '1.5rem', border: '1px solid #e9ecef', borderRadius: '8px', backgroundColor: '#f8f9fa' }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#333' }}>Python Backend</h3>
          <p style={{ margin: 0, color: '#666' }}>
            Powerful Python backend with modern async support, 
            database integration, and API development tools.
          </p>
        </div>
      </div>
      
      <div style={{ padding: '1.5rem', backgroundColor: '#e7f3ff', border: '1px solid #b8daff', borderRadius: '8px' }}>
        <h3 style={{ margin: '0 0 0.5rem 0', color: '#004085' }}>Getting Started</h3>
        <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', color: '#004085' }}>
          <li>Create pages in the <code style={{ backgroundColor: '#fff', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>app/</code> directory</li>
          <li>Add layouts to wrap multiple pages with shared UI</li>
          <li>Use dynamic routes with <code style={{ backgroundColor: '#fff', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>[param]</code> syntax</li>
          <li>Build with <code style={{ backgroundColor: '#fff', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>tavo build</code> for production</li>
        </ul>
      </div>
    </div>
  );
}