# RupAI frontend

React + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui (Radix). Dark only.

## Run locally against the mock backend

Two terminals. Start the backend first (see `../backend/README.md`), then:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/?key=devkey (the key you gave the mock backend).
Vite forwards `/api` and `/images` to the backend, so the session cookie works on one origin.

## Use the real Colab backend while developing

Create `frontend/.env.local`:

```
VITE_BACKEND_URL=https://<your-tunnel>.trycloudflare.com
```

Restart `npm run dev`, then open http://localhost:5173/?key=<your key>.

## Checks

```powershell
npm run typecheck
npm run lint          # oxlint
npm run format:check  # prettier
npm run build         # -> dist/
```

## Structure

```
src/
├── components/ui/      shadcn/ui components (button, card, input, label, textarea, toggle-group, badge, sonner)
├── features/
│   ├── auth/           useSession (key, cookie, health polling) + KeyScreen
│   ├── generate/       GenerateForm, ResultPanel, useGenerate, formValues
│   └── status/         StatusScreen (connecting / backend offline / engine not ready / blocked)
├── lib/                api client, types (mirror of backend models), utils
├── App.tsx             layout: header + 360px sticky form + results
└── index.css           theme tokens (#0f0f10 / #18181b / #8b5cf6), Inter + Noto Sans Khmer
```
