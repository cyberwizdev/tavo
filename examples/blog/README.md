# Bino Blog Example

This example demonstrates a complete blog application built with the Bino framework, showcasing:

- **Server-Side Rendering** with React components
- **Python API** for blog post management
- **Database integration** with the built-in ORM
- **File-based routing** for both app and API routes
- **Hot Module Replacement** for development

## Features

- 📝 **Blog Post Management** - Create, edit, and delete blog posts
- 🏷️ **Tagging System** - Organize posts with tags
- 💬 **Comments** - User comments on blog posts
- 🔍 **Search** - Full-text search across posts
- 📱 **Responsive Design** - Mobile-friendly interface
- ⚡ **Fast Performance** - SSR + client-side hydration

## Project Structure

```
blog/
├── app/                          # React SSR components
│   ├── layout.tsx               # Root layout with navigation
│   ├── page.tsx                 # Home page with post list
│   ├── posts/
│   │   ├── page.tsx            # Posts listing page
│   │   └── [slug]/
│   │       └── page.tsx        # Individual post page
│   ├── admin/
│   │   ├── page.tsx            # Admin dashboard
│   │   └── posts/
│   │       ├── page.tsx        # Manage posts
│   │       ├── new/
│   │       │   └── page.tsx    # Create new post
│   │       └── [id]/
│   │           └── edit/
│   │               └── page.tsx # Edit post
│   └── components/
│       ├── PostCard.tsx        # Blog post preview card
│       ├── PostContent.tsx     # Full post content
│       ├── CommentList.tsx     # Comments display
│       └── SearchBox.tsx       # Search functionality
├── api/                         # Python API routes
│   ├── models/
│   │   ├── post.py             # Blog post model
│   │   ├── comment.py          # Comment model
│   │   └── tag.py              # Tag model
│   └── routes/
│       ├── posts/
│       │   ├── index.py        # GET /api/posts, POST /api/posts
│       │   └── [id].py         # GET/PUT/DELETE /api/posts/{id}
│       ├── comments/
│       │   └── index.py        # Comment CRUD operations
│       └── search.py           # Search endpoint
├── static/                      # Static assets
│   ├── images/
│   └── uploads/
├── migrations/                  # Database migrations
│   ├── 001_create_posts.sql
│   ├── 002_create_comments.sql
│   └── 003_create_tags.sql
├── main.py                      # ASGI application
├── requirements.txt             # Python dependencies
├── package.json                 # Node.js dependencies
└── tavo.config.json            # Bundler configuration
```

## Getting Started

### 1. Create the Blog Project

```bash
# Create from blog template
tavo create my-blog --template blog
cd my-blog
```

### 2. Install Dependencies

```bash
# Install Python and Node.js dependencies
tavo install
```

### 3. Set Up Database

```bash
# Apply database migrations
python -c "
from bino_core.orm.migrations import MigrationRunner
import asyncio
runner = MigrationRunner('migrations')
asyncio.run(runner.apply_migrations())
"
```

### 4. Start Development Server

```bash
tavo dev
```

Visit http://localhost:3000 to see your blog!

## Key Components

### Blog Post Model

```python
# api/models/post.py
from bino_core.orm import BaseModel
from bino_core.orm.fields import StringField, TextField, DateTimeField, BooleanField

class Post(BaseModel):
    _table_name = "posts"
    
    title = StringField(max_length=200, null=False)
    slug = StringField(max_length=200, unique=True, null=False)
    content = TextField(null=False)
    excerpt = StringField(max_length=500)
    published = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
    
    @classmethod
    async def get_published_posts(cls):
        return await cls.filter(published=True)
    
    def generate_slug(self):
        # Auto-generate slug from title
        import re
        slug = re.sub(r'[^\w\s-]', '', self.title.lower())
        return re.sub(r'[-\s]+', '-', slug)
```

### Post List Component

```tsx
// app/components/PostCard.tsx
interface PostCardProps {
  post: {
    id: number;
    title: string;
    excerpt: string;
    slug: string;
    created_at: string;
  };
}

export default function PostCard({ post }: PostCardProps) {
  return (
    <article className="post-card">
      <h2>
        <a href={`/posts/${post.slug}`}>{post.title}</a>
      </h2>
      <p className="excerpt">{post.excerpt}</p>
      <time className="date">
        {new Date(post.created_at).toLocaleDateString()}
      </time>
    </article>
  );
}
```

### API Routes

```python
# api/routes/posts/index.py
from starlette.requests import Request
from starlette.responses import JSONResponse
from api.models.post import Post

async def get(request: Request) -> JSONResponse:
    """Get all published blog posts."""
    posts = await Post.get_published_posts()
    return JSONResponse([post.to_dict() for post in posts])

async def post(request: Request) -> JSONResponse:
    """Create a new blog post."""
    data = await request.json()
    
    post = Post(
        title=data['title'],
        content=data['content'],
        excerpt=data.get('excerpt', ''),
        published=data.get('published', False)
    )
    
    # Auto-generate slug
    post.slug = post.generate_slug()
    
    await post.save()
    return JSONResponse(post.to_dict(), status_code=201)
```

## Development Workflow

### 1. Adding New Features

The HMR system makes feature development fast and interactive:

```tsx
// Add a new component - see changes instantly
export default function ShareButton({ postId }: { postId: number }) {
  const handleShare = () => {
    // Add share logic here - updates appear immediately
    navigator.share({
      title: 'Check out this blog post',
      url: window.location.href
    });
  };
  
  return (
    <button onClick={handleShare} className="share-btn">
      Share Post 📤
    </button>
  );
}
```

### 2. Styling Changes

CSS changes update instantly without losing component state:

```css
/* Update styles and see immediate feedback */
.post-card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s; /* Add hover effect */
}

.post-card:hover {
  transform: translateY(-2px); /* See this change instantly */
}
```

### 3. API Development

Python API changes trigger a quick server restart:

```python
# api/routes/posts/[id].py
async def put(request: Request) -> JSONResponse:
    """Update a blog post."""
    post_id = request.path_params['id']
    data = await request.json()
    
    post = await Post.get(id=post_id)
    if not post:
        return JSONResponse({'error': 'Post not found'}, status_code=404)
    
    # Update fields - server restarts automatically on save
    post.title = data.get('title', post.title)
    post.content = data.get('content', post.content)
    await post.save()
    
    return JSONResponse(post.to_dict())
```

## Database Schema

The blog uses these main tables:

### Posts Table
```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    excerpt VARCHAR(500),
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Comments Table
```sql
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
);
```

### Tags Table
```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE post_tags (
    post_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, tag_id),
    FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);
```

## Customization

### Theming

Customize the blog appearance by modifying the layout:

```tsx
// app/layout.tsx - Update theme colors
const theme = {
  primary: '#2563eb',
  secondary: '#64748b', 
  accent: '#f59e0b',
  background: '#ffffff',
  text: '#1f2937'
};
```

### Adding Features

1. **User Authentication**:
   - Add user model and authentication API
   - Protect admin routes
   - Add user-specific content

2. **Rich Text Editor**:
   - Integrate a WYSIWYG editor
   - Add image upload functionality
   - Support for markdown

3. **SEO Optimization**:
   - Add meta tags for each post
   - Generate sitemap
   - Implement structured data

## Deployment

### Build for Production

```bash
tavo build
```

### Deploy to Production

```bash
# Start production server
tavo start --workers 4

# Or use Docker
docker build -t my-blog .
docker run -p 8000:8000 my-blog
```

## Performance Considerations

### Database Optimization

1. **Indexes**:
   ```sql
   CREATE INDEX idx_posts_published ON posts(published);
   CREATE INDEX idx_posts_created_at ON posts(created_at);
   CREATE INDEX idx_comments_post_id ON comments(post_id);
   ```

2. **Query Optimization**:
   ```python
   # Efficient post loading with pagination
   async def get_posts_page(page: int = 1, per_page: int = 10):
       offset = (page - 1) * per_page
       return await Post.filter(published=True).order_by('-created_at').limit(per_page).offset(offset)
   ```

### Caching Strategy

```python
# Add caching for frequently accessed data
from functools import lru_cache

@lru_cache(maxsize=100)
async def get_popular_tags():
    # Cache popular tags for 5 minutes
    return await Tag.get_popular()
```

## Testing

Run the test suite:

```bash
# Python tests
python -m pytest tests/

# Frontend tests (if added)
npm test
```

## Contributing

To contribute to this example:

1. Fork the repository
2. Create a feature branch
3. Make your changes with HMR feedback
4. Add tests for new functionality
5. Submit a pull request

## Learn More

- [Bino Documentation](../docs/getting-started.md)
- [API Development Guide](../docs/api-development.md)
- [Deployment Guide](../docs/deployment.md)
- [HMR Documentation](../docs/hmr.md)

This blog example demonstrates the power of Bino's integrated development experience with instant feedback and modern web development practices.