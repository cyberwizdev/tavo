# 🚀 Tavo

**Tavo** is a modern **full-stack framework CLI** that combines:

- ⚡ **Python** backend (FastAPI/Starlette base)  
- 🦀 **Rust + SWC** powered SSR for React (with App Router support)  
- 🔥 **Client hydration & HMR** with no Node.js required  
- 🛠️ CLI scaffolding for apps, routes, components, and APIs  

Think of it as **Laravel Breeze + React + Python** but lighter, faster, and developer-friendly.

---

## ✨ Features

- **SSR with React App Router** (layouts, nested routes, `use client`)  
- **Hydration scripts compiled with SWC** (no Node.js needed)  
- **File-based routing** for both backend and frontend  
- **Hot Module Replacement (HMR)** via inline WebSocket  
- **One CLI (`tavo`) to rule them all** — scaffold projects, run dev server, and build  
- **Python backend** with Starlette/FastAPI style APIs out of the box  
- **Template system** for rapidly creating new apps  

---

## 📦 Installation

```bash
pip install tavo
````

Or from source:

```bash
git clone https://github.com/cyberwizdev/tavo
cd tavo
pip install -e .
```

---

## ⚡ Quick Start

### 1. Create a new project

```bash
tavo create myapp
```

This sets up a project with:

* Python backend (`tavo_core`)
* React frontend with SSR
* HMR + WebSocket inline dev server
* Preconfigured templates

---

### 2. Run dev server

```bash
cd myapp
tavo dev
```

Visit: [http://localhost:3000](http://localhost:3000)
Changes reload instantly ⚡.

---

### 3. Build for production

```bash
tavo build
```

This generates:

* ✅ Compiled backend (Python)
* ✅ Optimized frontend bundle (SWC)
* ✅ Static + SSR-ready HTML

---

## 🗂️ Project Structure

A new `tavo` project looks like this:

```
myapp/
│── app/                  # React components (App Router)
│   ├── layout.tsx
│   ├── page.tsx
│   └── ...
│── backend/              # Python backend (APIs, DB, services)
│   ├── main.py
│   └── routes/
│── public/               # Static assets
│── templates/            # Scaffolding templates
│── package.json          # For frontend deps (optional, only if needed)
│── pyproject.toml        # Python project config
│── tavo.config.json      # Tavo project config
```

---

## 🛠️ CLI Commands

| Command           | Description                             |
| ----------------- | --------------------------------------- |
| `tavo new <name>` | Create a new project                    |
| `tavo dev`        | Run development server with HMR         |
| `tavo build`      | Build backend + frontend for production |
| `tavo add <name>` | Add a component, page, or API route     |
| `tavo doctor`     | Check environment & setup               |

---

## ⚙️ Configuration

Tavo uses a `tavo.config.json` file:

```json
{
  "name": "myapp",
  "backend": "fastapi",
  "frontend": "react",
  "ssr": true,
  "hmr": true
}
```

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/foo`)
3. Commit changes (`git commit -m 'Add foo'`)
4. Push to branch (`git push origin feature/foo`)
5. Open a PR 🚀

---

## 📜 License

MIT © [CyberwizDev](https://github.com/cyberwizdev)

---

## 🌟 Why the name **Tavo**?

Short, catchy, and inspired by **“Tabula Volans”** — “a flying tablet/page” in Latin.
Just like how Tavo makes **pages fly from Python to React** ⚡.
