# Deployment Guide

This guide covers deploying Bino applications to various platforms including Docker, systemd, and cloud providers.

## Prerequisites

Before deploying, ensure your application is production-ready:

1. **Build the application**:
   ```bash
   tavo build
   ```

2. **Test the production build locally**:
   ```bash
   tavo start
   ```

3. **Verify all dependencies are in requirements.txt**

## Docker Deployment

### Dockerfile

Create a `Dockerfile` in your project root:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for build process)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt package.json package-lock.json* ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build the application
RUN tavo build

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start production server
CMD ["tavo", "start", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

For development with services:

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/bino_app
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=bino_app
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Build and Run

```bash
# Build image
docker build -t my-tavo .

# Run container
docker run -p 8000:8000 -e SECRET_KEY=your-secret my-tavo

# Or use docker-compose
docker-compose up -d
```

## Systemd Service (Linux)

### Service File

Create `/etc/systemd/system/tavo.service`:

```ini
[Unit]
Description=Bino Application
After=network.target

[Service]
Type=exec
User=tavo
Group=tavo
WorkingDirectory=/opt/tavo
Environment=PATH=/opt/tavo/.venv/bin
Environment=DATABASE_URL=sqlite:///opt/tavo/app.db
Environment=SECRET_KEY=your-production-secret
ExecStart=/opt/tavo/.venv/bin/python -m tavo start --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/tavo

[Install]
WantedBy=multi-user.target
```

### Setup and Start

```bash
# Create user
sudo useradd --system --shell /bin/false tavo

# Deploy application
sudo mkdir -p /opt/tavo
sudo cp -r . /opt/tavo/
sudo chown -R tavo:tavo /opt/tavo

# Install dependencies and build
cd /opt/tavo
sudo -u tavo python -m venv .venv
sudo -u tavo .venv/bin/pip install -r requirements.txt
sudo -u tavo tavo build

# Enable and start service
sudo systemctl enable tavo
sudo systemctl start tavo
sudo systemctl status tavo
```

## Cloud Platform Deployment

### Heroku

1. **Create `Procfile`**:
   ```
   web: tavo start --host 0.0.0.0 --port $PORT
   ```

2. **Create `runtime.txt`**:
   ```
   python-3.11.7
   ```

3. **Deploy**:
   ```bash
   heroku create my-tavo
   heroku config:set SECRET_KEY=your-secret
   git push heroku main
   ```

### Railway

1. **Create `railway.toml`**:
   ```toml
   [build]
   builder = "nixpacks"
   
   [deploy]
   startCommand = "tavo start --host 0.0.0.0 --port $PORT"
   
   [env]
   NODE_VERSION = "18"
   PYTHON_VERSION = "3.11"
   ```

2. **Deploy**:
   ```bash
   railway login
   railway init
   railway up
   ```

### DigitalOcean App Platform

Create `.do/app.yaml`:

```yaml
name: tavo
services:
- name: web
  source_dir: /
  github:
    repo: your-username/your-repo
    branch: main
  run_command: tavo start --host 0.0.0.0 --port 8080
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  routes:
  - path: /
  envs:
  - key: SECRET_KEY
    value: your-secret-key
    type: SECRET
```

### AWS Lambda (Serverless)

For serverless deployment, use AWS Lambda with API Gateway:

1. **Install serverless dependencies**:
   ```bash
   pip install mangum
   ```

2. **Create `lambda_handler.py`**:
   ```python
   from mangum import Mangum
   from main import app
   
   handler = Mangum(app, lifespan="off")
   ```

3. **Deploy with AWS SAM or Serverless Framework**

## Environment Configuration

### Production Environment Variables

Set these environment variables for production:

```bash
# Required
SECRET_KEY=your-256-bit-secret-key
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Optional
DEBUG=false
LOG_LEVEL=info
WORKERS=4
MAX_REQUESTS=1000
TIMEOUT=30
```

### Security Considerations

1. **Secret Management**:
   - Use environment variables for secrets
   - Never commit secrets to version control
   - Rotate secrets regularly

2. **Database Security**:
   - Use connection pooling
   - Enable SSL for database connections
   - Regular backups

3. **Application Security**:
   - Enable HTTPS in production
   - Set secure headers
   - Implement rate limiting

## Performance Optimization

### Production Build Optimization

```json
// tavo.config.json
{
  "swc": {
    "target": "es2020",
    "minify": true,
    "source_maps": false
  },
  "output": {
    "filename": "[name].[contenthash].js",
    "chunk_filename": "[name].[contenthash].chunk.js"
  }
}
```

### Server Configuration

```bash
# Start with multiple workers
tavo start --workers 4 --host 0.0.0.0 --port 8000

# With custom configuration
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Database Optimization

1. **Connection Pooling**:
   ```python
   # In your database configuration
   DATABASE_CONFIG = {
       "url": os.getenv("DATABASE_URL"),
       "pool_size": 20,
       "max_overflow": 30,
       "pool_timeout": 30
   }
   ```

2. **Migrations**:
   ```bash
   # Apply migrations in production
   python -c "from bino_core.orm.migrations import MigrationRunner; import asyncio; asyncio.run(MigrationRunner('migrations').apply_migrations())"
   ```

## Monitoring and Logging

### Application Logging

Configure structured logging for production:

```python
# main.py
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/app.log')
    ]
)
```

### Health Checks

Add health check endpoint:

```python
# api/routes/health.py
from starlette.requests import Request
from starlette.responses import JSONResponse

async def get(request: Request) -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })
```

### Monitoring Integration

For production monitoring, consider:

- **Application Performance Monitoring (APM)**: New Relic, DataDog, or Sentry
- **Infrastructure Monitoring**: Prometheus + Grafana
- **Log Aggregation**: ELK Stack or cloud logging services

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer Configuration** (Nginx):
   ```nginx
   upstream bino_app {
       server 127.0.0.1:8000;
       server 127.0.0.1:8001;
       server 127.0.0.1:8002;
   }
   
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://bino_app;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **Multiple Workers**:
   ```bash
   tavo start --workers 4 --host 127.0.0.1 --port 8000
   tavo start --workers 4 --host 127.0.0.1 --port 8001
   tavo start --workers 4 --host 127.0.0.1 --port 8002
   ```

### Database Scaling

1. **Read Replicas**: Configure read-only database replicas
2. **Connection Pooling**: Use PgBouncer for PostgreSQL
3. **Caching**: Implement Redis for session and data caching

## Troubleshooting

### Common Issues

1. **Build Failures**:
   ```bash
   # Check Node.js version
   node --version  # Should be 18+
   
   # Clear cache and rebuild
   rm -rf node_modules dist
   tavo install
   tavo build
   ```

2. **Database Connection Issues**:
   ```bash
   # Test database connection
   python -c "import asyncio; from your_db_module import test_connection; asyncio.run(test_connection())"
   ```

3. **Memory Issues**:
   ```bash
   # Monitor memory usage
   ps aux | grep python
   
   # Adjust worker count
   tavo start --workers 2  # Reduce workers if memory constrained
   ```

### Logs and Debugging

```bash
# View application logs
tail -f logs/app.log

# Check systemd service logs
sudo journalctl -u tavo -f

# Docker logs
docker logs -f container-name
```

## Security Checklist

- [ ] Environment variables for all secrets
- [ ] HTTPS enabled in production
- [ ] Database connections use SSL
- [ ] Regular security updates
- [ ] Input validation on all API endpoints
- [ ] Rate limiting implemented
- [ ] CORS configured properly
- [ ] Security headers set

## Performance Checklist

- [ ] Production build optimized
- [ ] Static assets served with CDN
- [ ] Database queries optimized
- [ ] Caching strategy implemented
- [ ] Monitoring and alerting configured
- [ ] Load testing completed

For more advanced deployment scenarios and platform-specific guides, see the [Advanced Deployment](advanced-deployment.md) documentation.