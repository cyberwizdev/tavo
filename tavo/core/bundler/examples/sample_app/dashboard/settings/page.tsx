import React from 'react';

export default function SettingsPage() {
  return (
    <div>
      <h1 style={{ color: '#333', marginBottom: '1rem' }}>Dashboard Settings</h1>
      
      <p style={{ fontSize: '1.1rem', lineHeight: '1.6', color: '#666', marginBottom: '2rem' }}>
        This page demonstrates deep nesting with layouts. It inherits from both the root layout 
        and the dashboard layout, creating a nested structure: Root → Dashboard → Settings.
      </p>
      
      <form style={{ maxWidth: '600px' }}>
        <div style={{ marginBottom: '1.5rem' }}>
          <label 
            htmlFor="siteName" 
            style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#333' }}
          >
            Site Name
          </label>
          <input
            type="text"
            id="siteName"
            defaultValue="Tavo Sample App"
            style={{
              width: '100%',
              padding: '0.75rem',
              border: '1px solid #ccc',
              borderRadius: '4px',
              fontSize: '1rem'
            }}
          />
        </div>
        
        <div style={{ marginBottom: '1.5rem' }}>
          <label 
            htmlFor="description" 
            style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#333' }}
          >
            Description
          </label>
          <textarea
            id="description"
            rows={4}
            defaultValue="A sample application built with the Tavo framework to demonstrate routing, layouts, and server-side rendering capabilities."
            style={{
              width: '100%',
              padding: '0.75rem',
              border: '1px solid #ccc',
              borderRadius: '4px',
              fontSize: '1rem',
              resize: 'vertical'
            }}
          />
        </div>
        
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', color: '#333' }}>
            Features
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', color: '#666' }}>
              <input type="checkbox" defaultChecked style={{ marginRight: '0.5rem' }} />
              Server-Side Rendering
            </label>
            <label style={{ display: 'flex', alignItems: 'center', color: '#666' }}>
              <input type="checkbox" defaultChecked style={{ marginRight: '0.5rem' }} />
              Hot Reloading
            </label>
            <label style={{ display: 'flex', alignItems: 'center', color: '#666' }}>
              <input type="checkbox" defaultChecked style={{ marginRight: '0.5rem' }} />
              TypeScript Support
            </label>
            <label style={{ display: 'flex', alignItems: 'center', color: '#666' }}>
              <input type="checkbox" style={{ marginRight: '0.5rem' }} />
              Database Integration
            </label>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button
            type="submit"
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: '#0066cc',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '1rem',
              cursor: 'pointer'
            }}
          >
            Save Settings
          </button>
          <button
            type="button"
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              fontSize: '1rem',
              cursor: 'pointer'
            }}
          >
            Reset
          </button>
        </div>
      </form>
      
      <div style={{ 
        marginTop: '2rem', 
        padding: '1rem', 
        backgroundColor: '#fff3cd', 
        border: '1px solid #ffeaa7', 
        borderRadius: '4px' 
      }}>
        <strong style={{ color: '#856404' }}>Note:</strong>
        <span style={{ color: '#856404' }}> This is a demo form. Settings are not actually saved.</span>
      </div>
    </div>
  );
}