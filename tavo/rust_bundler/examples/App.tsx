import React from 'react';
import Header from './components/Header';
import Counter from './components/Counter';

interface AppProps {
  title?: string;
}

export default function App({ title = "MySSR Demo" }: AppProps) {
  return (
    <div className="app">
      <Header title={title} />
      <main className="main-content">
        <h1>Welcome to {title}</h1>
        <p>This content is server-side rendered and then hydrated on the client!</p>
        <Counter />
        <div className="features">
          <h2>Features</h2>
          <ul>
            <li>Server-Side Rendering with Rust + SWC</li>
            <li>Client-side Hydration</li>
            <li>TypeScript Support</li>
            <li>Fast Compilation</li>
          </ul>
        </div>
      </main>
    </div>
  );
}