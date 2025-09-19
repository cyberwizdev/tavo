import React from 'react';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div style={{ display: 'flex', gap: '2rem' }}>
      <aside style={{ 
        minWidth: '200px',
        padding: '1rem',
        backgroundColor: '#f8f9fa',
        border: '1px solid #e9ecef',
        borderRadius: '8px',
        height: 'fit-content'
      }}>
        <h3 style={{ margin: '0 0 1rem 0', color: '#333', fontSize: '1.1rem' }}>Dashboard</h3>
        <nav>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li style={{ marginBottom: '0.5rem' }}>
              <a 
                href="/dashboard" 
                style={{ 
                  textDecoration: 'none', 
                  color: '#0066cc',
                  display: 'block',
                  padding: '0.5rem',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#e7f3ff'}
                onMouseOut={(e) => e.target.style.backgroundColor = 'transparent'}
              >
                Overview
              </a>
            </li>
            <li style={{ marginBottom: '0.5rem' }}>
              <a 
                href="/dashboard/settings"
                style={{ 
                  textDecoration: 'none', 
                  color: '#0066cc',
                  display: 'block',
                  padding: '0.5rem',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#e7f3ff'}
                onMouseOut={(e) => e.target.style.backgroundColor = 'transparent'}
              >
                Settings
              </a>
            </li>
          </ul>
        </nav>
      </aside>
      
      <div style={{ flex: 1 }}>
        {children}
      </div>
    </div>
  );
}