import React from 'react';

export default function DashboardPage() {
  return (
    <div>
      <h1 style={{ color: '#333', marginBottom: '1rem' }}>Dashboard Overview</h1>
      
      <p style={{ fontSize: '1.1rem', lineHeight: '1.6', color: '#666', marginBottom: '2rem' }}>
        Welcome to the dashboard! This demonstrates nested layouts in Tavo. 
        The dashboard layout wraps all dashboard pages with shared navigation.
      </p>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ 
          padding: '1.5rem', 
          backgroundColor: '#e7f3ff', 
          border: '1px solid #b8daff', 
          borderRadius: '8px',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#004085', fontSize: '2rem' }}>42</h3>
          <p style={{ margin: 0, color: '#004085' }}>Total Users</p>
        </div>
        
        <div style={{ 
          padding: '1.5rem', 
          backgroundColor: '#d1ecf1', 
          border: '1px solid #b8daff', 
          borderRadius: '8px',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#0c5460', fontSize: '2rem' }}>128</h3>
          <p style={{ margin: 0, color: '#0c5460' }}>Page Views</p>
        </div>
        
        <div style={{ 
          padding: '1.5rem', 
          backgroundColor: '#d4edda', 
          border: '1px solid #c3e6cb', 
          borderRadius: '8px',
          textAlign: 'center'
        }}>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#155724', fontSize: '2rem' }}>96%</h3>
          <p style={{ margin: 0, color: '#155724' }}>Uptime</p>
        </div>
      </div>
      
      <div style={{ padding: '1.5rem', border: '1px solid #e9ecef', borderRadius: '8px', backgroundColor: '#fff' }}>
        <h3 style={{ margin: '0 0 1rem 0', color: '#333' }}>Recent Activity</h3>
        <ul style={{ margin: 0, paddingLeft: '1.5rem', lineHeight: '1.6', color: '#666' }}>
          <li>User john@example.com registered</li>
          <li>Dashboard settings updated</li>
          <li>New page created: /about</li>
          <li>Cache cleared for better performance</li>
          <li>Server restarted successfully</li>
        </ul>
      </div>
    </div>
  );
}