# Frontend Architecture

The CompassX user interface is a single-page application (SPA) built with **React**, **TypeScript**, and **Vite**.

---

## Directory Structure

```
frontend/
├── src/
│   ├── assets/           # Static icons, logos, and images
│   ├── components/       # Reusable UI component library (buttons, tables, modals)
│   ├── hooks/            # Custom React hooks (auth, websocket, query state)
│   ├── pages/            # View-level page components (Dashboards, Notebooks, Settings)
│   ├── services/         # API clients and HTTP request utilities
│   ├── types/            # TypeScript interface & type definitions
│   ├── App.tsx           # Main application routing and providers
│   └── main.tsx          # DOM entrypoint
├── index.html            # HTML shell
├── package.json          # Node dependencies & build scripts
└── vite.config.ts        # Vite build & proxy configuration
```

---

## Development Scripts

Run the following commands inside `frontend/`:

```bash
# Install dependencies
npm install

# Start local hot-reloading dev server
npm run dev

# Build production bundle
npm run build

# Run linter
npm run lint
```
