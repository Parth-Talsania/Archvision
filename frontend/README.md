# ArchVision — Frontend

React + TypeScript single-page app for ArchVision. It handles login, floor plan upload, and the interactive results views. All analysis is done by the FastAPI backend in [`../backend`](../backend).

## Stack

React 18 · Vite 5 · TypeScript · Tailwind CSS · shadcn/ui (Radix) · TanStack Query · Recharts · Framer Motion · Axios

## Getting started

```bash
npm install
npm run dev        # http://localhost:8080
```

The dev server proxies `/api` to the backend at `http://127.0.0.1:8000` (see `vite.config.ts`), so start the backend first.

| Script | What it does |
|---|---|
| `npm run dev` | Start the dev server with hot reload |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint |
| `npm test` | Vitest unit tests |

## Structure

```
src/
├── api/client.ts        Axios instance — attaches the JWT, redirects to /login on 401
├── contexts/            AuthContext (email/password + OAuth token login)
├── pages/               Landing, Login, Register, Dashboard, Upload, AnalysisView,
│                        History, Compare, ProjectIntro, Founders, OAuthCallback
├── components/
│   ├── FloorPlanViewer  Interactive SVG room polygons with zoom/pan and selection
│   ├── RoomDetailPanel  Dimensions, area and confidence for the selected room
│   ├── AnalyticsDashboard  KPIs, space allocation, balance radar, room-size ranking
│   ├── SpatialReport    Printable spatial audit report
│   ├── CostEstimator    Per-room construction cost estimate
│   ├── WifiMapper       Wi-Fi dead-zone simulator built on room centroids
│   ├── PipelineOverlay  Animated processing stepper shown during analysis
│   └── ui/              shadcn/ui primitives
└── hooks/, lib/
```

The design system ("Deep Blue Galaxy": dark glassmorphism with cyan accents) lives in `tailwind.config.ts` and `src/index.css`.
