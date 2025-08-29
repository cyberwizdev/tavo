# Getting Started with Tavo

Tavo is a full-stack framework that combines Python backends with Rust/SWC-powered React SSR for fast, modern web applications.

## Prerequisites

Before getting started, ensure you have the following installed:

- **Python 3.11+** - For the backend server
- **Node.js 18+** - For frontend dependencies
- **Rust 1.70+** - For the bundler (optional, pre-built binaries available)

## Installation

### 1. Install Tavo CLI

```bash
pip install tavo
```

### 2. Verify Installation

```bash
tavo --version
```

## Creating Your First Project

### 1. Create a New Project

```bash
tavo create my-app
cd my-app
```

This creates a new Tavo project with the following structure:

```
my-app/
├── app/                 # React components and pages
│   ├── layout.tsx       # Root layout component
│   ├── page.tsx         # Home page component
│   └── components/      # Reusable components
├── api/                 # Python API routes
│   ├── models/          # Database models
│   └── routes/          # API endpoints
├── static/              # Static assets
├── main.py              # ASGI application entry point
├── requirements.txt     # Python dependencies
├── package.json         # Node.js dependencies
└── tavo.config.json     # Bundler configuration
```

### 2. Install Dependencies

```bash
tavo install
```

This command:
- Creates a Python virtual environment (`.venv`)
- Installs Python dependencies via pip
- Installs Node.js dependencies via npm/yarn/pnpm

## Development

### Start Development Server

```bash
tavo dev
```

This starts:
- Python ASGI server (default: http://localhost:3000)
- Rust bundler in watch mode
- HMR WebSocket server for hot reloading

The development server includes:
- **Hot Module Replacement (HMR)** - Instant updates without page refresh
- **Server-Side Rendering** - Fast initial page loads
- **API Auto-reload** - Python API changes trigger automatic restart

### Development Features

#### File-based Routing

**App Routes (React SSR):**
- `app/page.tsx` → `/`
- `app/about/page.tsx` → `/about`
- `app/users/[id]/page.tsx` → `/users/{id}`

**API Routes (Python):**
- `api/routes/hello.py` → `/api/hello`
- `api/routes/users/profile.py` → `/api/users/profile`

#### Hot Module Replacement

Changes to React components are instantly reflected in the browser without losing state:

```tsx
// app/components/Counter.tsx
export default function Counter() {
  const [count, setCount] = useState(0);
  
  return (
    <button onClick={() => setCount(count + 1)}>
      Count: {count} {/* Changes here update instantly */}
    </button>
  );
}
```

#### API Development

Create API endpoints by adding Python files to the `api/routes` directory:

```python
# api/routes/users.py
from starlette.requests import Request
from starlette.responses import JSONResponse

async def get(request: Request) -> JSONResponse:
    return JSONResponse({"users": []})

async def post(request: Request) -> JSONResponse:
    data = await request.json()
    # Process user creation
    return JSONResponse({"created": True})
```

## Building for Production

### Build the Project

```bash
tavo build
```

This creates optimized bundles in the `dist/` directory:
- Minified JavaScript and CSS
- Server-side rendering bundle
- Asset manifest for production serving

### Start Production Server

```bash
tavo start
```

Starts the production server with:
- Pre-built assets serving
- Optimized SSR performance
- Production logging and monitoring

## Configuration

### Bundler Configuration

Customize the build process in `tavo.config.json`:

```json
{
  "entry": {
    "client": "app/page.tsx",
    "server": "app/layout.tsx"
  },
  "output": {
    "dir": "dist",
    "filename": "[name].[hash].js"
  },
  "swc": {
    "target": "es2020",
    "minify": true,
    "jsx": {
      "runtime": "automatic"
    }
  },
  "dev": {
    "port": 3000,
    "hmr_port": 3001
  }
}
```

### Environment Variables

Create a `.env` file for environment-specific configuration:

```env
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key-here
DEBUG=true
```

## Database Integration

Tavo includes a built-in ORM for database operations:

```python
# api/models/user.py
from tavo_core.orm import BaseModel
from tavo_core.orm.fields import StringField, DateTimeField

class User(BaseModel):
    _table_name = "users"
    
    name = StringField(max_length=100, null=False)
    email = StringField(unique=True, null=False)
    created_at = DateTimeField(auto_now_add=True)

# Usage in API routes
async def get(request: Request):
    users = await User.all()
    return JSONResponse([user.to_dict() for user in users])
```

## Next Steps

1. **Explore the Examples** - Check out `examples/blog/` for a complete blog implementation
2. **Read the API Documentation** - Learn about advanced features and configuration
3. **Deploy Your App** - See the [deployment guide](deployment.md) for production deployment options

## Getting Help

- **Documentation**: [https://tavo-framework.dev/docs](https://tavo-framework.dev/docs)
- **GitHub Issues**: [https://github.com/tavo-framework/tavo](https://github.com/tavo-framework/tavo)
- **Discord Community**: [https://discord.gg/tavo](https://discord.gg/tavo)

## Common Commands Reference

```bash
# Project management
tavo create <project-name>    # Create new project
tavo install                  # Install dependencies

# Development
tavo dev                      # Start development server
tavo dev --port 8000         # Start on custom port

# Production
tavo build                    # Build for production
tavo build --output build    # Custom output directory
tavo start                    # Start production server
tavo start --workers 4       # Start with multiple workers
```

Welcome to Tavo! 🚀