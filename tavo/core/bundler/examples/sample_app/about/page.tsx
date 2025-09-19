import React from 'react';

export default function AboutPage() {
  return (
    <div>
      <h1 style={{ color: '#333', marginBottom: '1rem' }}>About Tavo</h1>
      
      <p style={{ fontSize: '1.1rem', lineHeight: '1.6', color: '#666', marginBottom: '2rem' }}>
        Tavo is a modern web framework that combines the power of Python for backend development 
        with React for building interactive user interfaces. It provides a seamless full-stack 
        development experience with built-in support for server-side rendering, routing, and more.
      </p>
      
      <h2 style={{ color: '#333', marginBottom: '1rem', fontSize: '1.4rem' }}>Key Features</h2>
      
      <ul style={{ lineHeight: '1.6', color: '#666', marginBottom: '2rem' }}>
        <li><strong>App Router:</strong> File-based routing system similar to Next.js App Router</li>
        <li><strong>Server-Side Rendering:</strong> Built-in SSR with client-side hydration</li>
        <li><strong>Python Backend:</strong> Async-first Python backend with modern tooling</li>
        <li><strong>TypeScript Support:</strong> Full TypeScript support for type-safe development</li>
        <li><strong>Hot Reloading:</strong> Fast development with automatic reloading</li>
        <li><strong>Caching:</strong> Intelligent build caching for faster compilation</li>
      </ul>
      
      <h2 style={{ color: '#333', marginBottom: '1rem', fontSize: '1.4rem' }}>Architecture</h2>
      
      <p style={{ lineHeight: '1.6', color: '#666', marginBottom: '1rem' }}>
        Tavo uses a bundler written in Python that discovers routes from your file structure,
        compiles React components using SWC, and generates both server and client bundles.
        This approach provides excellent performance while maintaining the flexibility of Python.
      </p>
      
      <div style={{ padding: '1.5rem', backgroundColor: '#f8f9fa', border: '1px solid #e9ecef', borderRadius: '8px' }}>
        <h3 style={{ margin: '0 0 0.5rem 0', color: '#333' }}>Sample App Structure</h3>
        <pre style={{ margin: '0.5rem 0', fontFamily: 'monospace', fontSize: '0.9rem', color: '#666' }}>
{`app/
├── layout.tsx          # Root layout (this file)
├── page.tsx            # Home page
├── about/
│   └── page.tsx        # About page (this page)
└── dashboard/
    ├── layout.tsx      # Dashboard layout
    ├── page.tsx        # Dashboard home
    └── settings/
        └── page.tsx    # Settings page`}
        </pre>
      </div>
    </div>
  );
}