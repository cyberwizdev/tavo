# App Router Routing Documentation

## Overview

The Tavo bundler implements App Router semantics for automatic route discovery and generation. Routes are determined by the file structure within the `app/` directory.

## Basic Routing

### File-based Routes

Routes are created by adding files to the `app` directory:

```
app/
├── page.tsx              → / (home page)
├── about/
│   └── page.tsx          → /about
├── contact/
│   └── page.tsx          → /contact
└── blog/
    ├── page.tsx          → /blog
    └── [slug]/
        └── page.tsx      → /blog/[slug] (dynamic)
```

### Route Files

#### `page.tsx` / `page.jsx`
Defines the main content for a route. Must have a default export:

```tsx
// app/about/page.tsx
export default function AboutPage() {
  return <div>About Us</div>;
}
```

#### `layout.tsx` / `layout.jsx`
Defines shared layouts for routes. Layouts wrap child routes:

```tsx
// app/dashboard/layout.tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <nav>Dashboard Navigation</nav>
      {children}
    </div>
  );
}
```

#### `loading.tsx` / `loading.jsx`
Defines loading UI for a route segment:

```tsx
// app/dashboard/loading.tsx
export default function DashboardLoading() {
  return <div>Loading dashboard...</div>;
}
```

#### `error.tsx` / `error.jsx`
Defines error boundaries for route segments:

```tsx
// app/dashboard/error.tsx
export default function DashboardError({ error }: { error: Error }) {
  return <div>Error: {error.message}</div>;
}
```

#### `not-found.tsx` / `not-found.jsx`
Custom 404 page for route segments:

```tsx
// app/not-found.tsx
export default function NotFound() {
  return <div>Page not found</div>;
}
```

## Layout Nesting

Layouts are automatically nested from the root to the target route:

```
app/
├── layout.tsx           # Root layout (always applied)
├── page.tsx             # Home page
└── dashboard/
    ├── layout.tsx       # Dashboard layout (wraps all dashboard routes)
    ├── page.tsx         # /dashboard
    └── settings/
        ├── layout.tsx   # Settings layout (wraps settings routes)
        └── page.tsx     # /dashboard/settings
```

Final nesting for `/dashboard/settings`:
```tsx
<RootLayout>
  <DashboardLayout>
    <SettingsLayout>
      <SettingsPage />
    </SettingsLayout>
  </DashboardLayout>
</RootLayout>
```

## Dynamic Routes

### Single Dynamic Segment

Use square brackets to create dynamic route segments:

```
app/
└── blog/
    └── [slug]/
        └── page.tsx     → /blog/hello-world, /blog/another-post
```

```tsx
// app/blog/[slug]/page.tsx
interface BlogPostProps {
  params: { slug: string };
}

export default function BlogPost({ params }: BlogPostProps) {
  return <div>Blog post: {params.slug}</div>;
}
```

### Multiple Dynamic Segments

```
app/
└── shop/
    └── [category]/
        └── [product]/
            └── page.tsx → /shop/clothing/t-shirt, /shop/electronics/phone
```

```tsx
// app/shop/[category]/[product]/page.tsx
interface ProductProps {
  params: { 
    category: string;
    product: string;
  };
}

export default function Product({ params }: ProductProps) {
  return (
    <div>
      Category: {params.category}, Product: {params.product}
    </div>
  );
}
```

## Catch-all Routes

### Catch-all Segments

Use `[...slug]` to catch all route segments:

```
app/
└── docs/
    └── [...slug]/
        └── page.tsx     → /docs/a, /docs/a/b, /docs/a/b/c
```

```tsx
// app/docs/[...slug]/page.tsx
interface DocsProps {
  params: { slug: string[] };
}

export default function Docs({ params }: DocsProps) {
  const path = params.slug.join('/');
  return <div>Documentation: {path}</div>;
}
```

### Optional Catch-all

Use `[[...slug]]` to make the catch-all optional:

```
app/
└── shop/
    └── [[...slug]]/
        └── page.tsx     → /shop, /shop/category, /shop/category/product
```

```tsx
// app/shop/[[...slug]]/page.tsx
interface ShopProps {
  params: { slug?: string[] };
}

export default function Shop({ params }: ShopProps) {
  const segments = params.slug || [];
  return <div>Shop segments: {segments.join(' > ')}</div>;
}
```

## Route Groups

Use parentheses to create route groups that don't affect the URL:

```
app/
├── (marketing)/         # Route group (not in URL)
│   ├── about/
│   │   └── page.tsx     → /about
│   └── contact/
│       └── page.tsx     → /contact
└── (app)/              # Route group (not in URL)
    ├── dashboard/
    │   └── page.tsx     → /dashboard
    └── settings/
        └── page.tsx     → /settings
```

Route groups are useful for:
- Organizing routes without affecting URLs
- Applying different layouts to route groups
- Creating multiple root layouts

## Parallel Routes

Use `@folder` syntax for parallel routes (slots):

```
app/
├── layout.tsx
├── page.tsx
├── @analytics/
│   └── page.tsx         # Analytics slot
└── @team/
    └── page.tsx         # Team slot
```

```tsx
// app/layout.tsx
export default function RootLayout({
  children,
  analytics,
  team,
}: {
  children: React.ReactNode;
  analytics: React.ReactNode;
  team: React.ReactNode;
}) {
  return (
    <html>
      <body>
        {children}
        <div style={{ display: 'flex' }}>
          <div>{analytics}</div>
          <div>{team}</div>
        </div>
      </body>
    </html>
  );
}
```

## Intercepting Routes

Use `(..)` syntax to intercept routes:

```
app/
├── feed/
│   └── page.tsx
├── photo/
│   └── [id]/
│       └── page.tsx     → /photo/123 (regular)
└── (..)photo/
    └── [id]/
        └── page.tsx     → /photo/123 (intercepted from /feed)
```

Intercepting conventions:
- `(.)` same level
- `(..)` one level up  
- `(..)(..)` two levels up
- `(...)` root app directory

## Route Resolution Process

The bundler resolves routes in this order:

1. **Static routes** - exact file matches
2. **Dynamic routes** - `[param]` segments
3. **Catch-all routes** - `[...slug]` segments
4. **Not found** - 404 handling

### Example Resolution

For URL `/blog/hello-world`:

```
app/
├── blog/
│   ├── page.tsx              # /blog (doesn't match)
│   ├── hello-world/
│   │   └── page.tsx          # /blog/hello-world (exact match - wins)
│   └── [slug]/
│       └── page.tsx          # /blog/[slug] (would match but lower priority)
```

## Advanced Patterns

### Nested Dynamic Routes

```
app/
└── [tenant]/
    ├── layout.tsx            # Tenant-specific layout
    ├── page.tsx              # /acme, /company-b
    └── dashboard/
        └── [userId]/
            └── page.tsx      # /acme/dashboard/123
```

### Mixed Static and Dynamic

```
app/
├── blog/
│   ├── page.tsx              # /blog
│   ├── latest/
│   │   └── page.tsx          # /blog/latest
│   └── [slug]/
│       ├── page.tsx          # /blog/dynamic-slug
│       └── edit/
│           └── page.tsx      # /blog/dynamic-slug/edit
```

### API Routes

```
app/
└── api/
    ├── users/
    │   ├── route.ts          # /api/users
    │   └── [id]/
    │       └── route.ts      # /api/users/123
    └── auth/
        └── login/
            └── route.ts      # /api/auth/login
```

```tsx
// app/api/users/route.ts
export async function GET() {
  return Response.json({ users: [] });
}

export async function POST(request: Request) {
  const data = await request.json();
  return Response.json({ success: true });
}
```

## Bundler Integration

The Tavo bundler automatically:

1. **Discovers routes** by scanning the `app/` directory
2. **Builds route tree** with proper nesting and priorities  
3. **Compiles bundles** for each route (client + server)
4. **Generates manifests** for route loading
5. **Handles layouts** with automatic composition

### Route Discovery

```python
from tavo.core.bundler import get_bundler

bundler = get_bundler()
routes = bundler.resolver.resolve_routes()

for route in routes:
    print(f"Route: {route.route_path}")
    print(f"  Page: {route.page_file}")
    print(f"  Layouts: {route.layout_chain}")
    print(f"  All files: {len(route.all_files)}")
```

### Build Output

For each route, the bundler generates:

```
dist/
├── client/
│   ├── index.js              # / route (client bundle)
│   ├── about.js              # /about route
│   └── blog_[slug].js        # /blog/[slug] route
└── server/
    ├── index.js              # / route (SSR bundle)
    ├── about.js              # /about route
    └── blog_[slug].js        # /blog/[slug] route
```

This routing system provides powerful, flexible route organization while maintaining simplicity and convention over configuration.