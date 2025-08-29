# Hot Module Replacement (HMR)

Bino's Hot Module Replacement system provides instant feedback during development by updating your application in the browser without losing state or requiring a full page reload.

## How HMR Works

Bino's HMR system consists of three main components:

1. **File Watcher** - Monitors your source files for changes
2. **Rust Bundler** - Recompiles changed modules incrementally  
3. **WebSocket Server** - Pushes updates to connected browsers

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ File Change │───▶│ Rust Bundler │───▶│ Browser     │
│ Detection   │    │ Recompile    │    │ Hot Update  │
└─────────────┘    └──────────────┘    └─────────────┘
       │                    │                   │
       │                    │                   │
       ▼                    ▼                   ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Python      │    │ WebSocket    │    │ State       │
│ File Watch  │───▶│ Notification │───▶│ Preserved   │
└─────────────┘    └──────────────┘    └─────────────┘
```

## Supported File Types

HMR supports different update strategies based on file type:

### React Components (.tsx, .jsx)
- **Hot Update**: Component updates without losing state
- **Fast Refresh**: Preserves component state when possible
- **Error Recovery**: Shows errors in overlay, recovers on fix

```tsx
// app/components/Counter.tsx
export default function Counter() {
  const [count, setCount] = useState(0);
  
  return (
    <div>
      <p>Count: {count}</p> {/* Changes here update instantly */}
      <button onClick={() => setCount(count + 1)}>
        Increment
      </button>
    </div>
  );
}
```

### Stylesheets (.css, .scss)
- **Hot Update**: Styles update without page reload
- **No State Loss**: Component state is preserved
- **Instant Feedback**: See style changes immediately

### Python API Routes (.py)
- **Server Restart**: Python changes trigger server restart
- **Quick Recovery**: Fast restart with minimal downtime
- **Error Display**: API errors shown in browser console

### Configuration Files
- **Full Reload**: Config changes require full page reload
- **Build Restart**: Bundler configuration triggers rebuild

## Configuration

### HMR Settings

Configure HMR behavior in `bino.config.json`:

```json
{
  "dev": {
    "port": 3000,
    "hmr_port": 3001,
    "hmr": true,
    "hmr_options": {
      "overlay": true,
      "reload_on_error": false,
      "debounce_delay": 100
    }
  }
}
```

### Environment Variables

Control HMR with environment variables:

```bash
# Disable HMR completely
BINO_HMR_ENABLED=false bino dev

# Custom HMR port
BINO_HMR_PORT=4001 bino dev

# Verbose HMR logging
BINO_HMR_DEBUG=true bino dev
```

## Debugging HMR Issues

### Connection Problems

If HMR isn't working, check the browser console for WebSocket connection errors:

```javascript
// Browser console should show:
🔥 HMR connected

// If you see connection errors:
WebSocket connection to 'ws://localhost:3001/' failed
```

**Solutions:**

1. **Check HMR server is running**:
   ```bash
   # HMR server should start with dev server
   bino dev --verbose
   # Look for: "HMR WebSocket server started on port 3001"
   ```

2. **Verify port availability**:
   ```bash
   # Check if port is in use
   lsof -i :3001
   
   # Use different port if needed
   bino dev --hmr-port 4001
   ```

3. **Firewall/Network issues**:
   ```bash
   # Test WebSocket connection
   curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
        http://localhost:3001/
   ```

### File Change Detection

If file changes aren't being detected:

1. **Check watched directories**:
   ```bash
   # Verify your files are in watched directories
   # Default: app/, api/, components/, lib/
   ```

2. **File system limitations**:
   ```bash
   # Increase inotify limits on Linux
   echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

3. **Editor compatibility**:
   - Some editors use atomic writes that can break file watching
   - Configure your editor to use normal file writes
   - VS Code: Set `"files.watcherExclude"` appropriately

### Performance Issues

If HMR is slow or causing performance problems:

1. **Reduce watched files**:
   ```json
   // bino.config.json
   {
     "dev": {
       "watch_ignore": [
         "node_modules/**",
         "dist/**",
         "*.log",
         "coverage/**"
       ]
     }
   }
   ```

2. **Adjust debounce delay**:
   ```json
   {
     "dev": {
       "hmr_options": {
         "debounce_delay": 300  // Increase for slower systems
       }
     }
   }
   ```

## Advanced HMR Features

### Custom HMR Handlers

Add custom HMR handling in your components:

```tsx
// app/components/CustomComponent.tsx
import { useEffect } from 'react';

export default function CustomComponent() {
  useEffect(() => {
    // Custom HMR handling
    if (module.hot) {
      module.hot.accept('./CustomComponent', () => {
        console.log('CustomComponent updated');
      });
    }
  }, []);
  
  return <div>Custom Component</div>;
}
```

### HMR API

Access HMR functionality programmatically:

```typescript
// Client-side HMR API
declare global {
  interface Window {
    __BINO_HMR__: {
      connect(): void;
      disconnect(): void;
      on(event: string, callback: Function): void;
      reload(): void;
    };
  }
}

// Usage
window.__BINO_HMR__.on('file-change', (data) => {
  console.log('File changed:', data.file);
});
```

### Error Overlay

The HMR error overlay shows compilation and runtime errors:

```css
/* Customize error overlay */
.bino-error-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  color: white;
  font-family: monospace;
  z-index: 9999;
}
```

## Best Practices

### 1. Component Design for HMR

Write components that work well with HMR:

```tsx
// ✅ Good: Pure component with minimal side effects
export default function UserCard({ user }) {
  return (
    <div className="user-card">
      <h3>{user.name}</h3>
      <p>{user.email}</p>
    </div>
  );
}

// ❌ Avoid: Components with complex side effects
export default function ProblematicComponent() {
  useEffect(() => {
    // Complex setup that's hard to clean up
    const interval = setInterval(() => {
      // This might cause issues during HMR
    }, 1000);
    
    // Missing cleanup
  }, []);
}
```

### 2. State Management

Design state to survive HMR updates:

```tsx
// ✅ Good: Local state that can be preserved
const [formData, setFormData] = useState({
  name: '',
  email: ''
});

// ✅ Good: External state management
import { useStore } from './store';
const { user, updateUser } = useStore();

// ❌ Avoid: Module-level state
let moduleState = {}; // This will be reset on HMR
```

### 3. API Integration

Handle API changes gracefully:

```tsx
// ✅ Good: Error boundaries for API changes
function ApiComponent() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchData().catch(setError);
  }, []);
  
  if (error) {
    return <div>Error: {error.message}</div>;
  }
  
  return <div>{/* Render data */}</div>;
}
```

## Troubleshooting Checklist

When HMR isn't working properly:

- [ ] Check browser console for WebSocket connection
- [ ] Verify HMR server is running on correct port
- [ ] Ensure files are in watched directories
- [ ] Check for file system permission issues
- [ ] Verify no firewall blocking WebSocket connections
- [ ] Test with a simple file change (add a comment)
- [ ] Check for conflicting development servers
- [ ] Restart development server completely

## HMR vs Full Reload

Understanding when HMR triggers vs full reload:

| File Type | Change Type | HMR Behavior |
|-----------|-------------|--------------|
| `.tsx/.jsx` | Component edit | Hot update |
| `.tsx/.jsx` | Export change | Full reload |
| `.css` | Style change | Hot update |
| `.py` | API route | Server restart |
| `package.json` | Dependency | Full reload |
| `bino.config.json` | Config | Build restart |

## Performance Impact

HMR is designed to be fast, but large projects may experience:

- **Initial startup time**: First build takes longer
- **Memory usage**: File watchers consume memory
- **CPU usage**: Continuous file monitoring

Monitor performance with:

```bash
# Check HMR server memory usage
ps aux | grep bino

# Monitor file watcher performance
bino dev --verbose --hmr-debug
```

For optimal performance:
- Exclude unnecessary directories from watching
- Use `.gitignore` patterns to reduce file count
- Consider disabling HMR for very large projects during intensive development

## Next Steps

- Learn about [API development](api-development.md)
- Explore [component patterns](component-patterns.md)
- Read about [production deployment](deployment.md)