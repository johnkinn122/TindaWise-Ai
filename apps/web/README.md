# Tindawise — web app

Next.js frontend for Tindawise AI. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for structure and decisions,
and [`design-system/tindawise-ai/MASTER.md`](../../design-system/tindawise-ai/MASTER.md) for design rules.

## Run it

From the repository root:

```bash
npm install                                    # once
cp apps/web/.env.example apps/web/.env.local   # once
npm run dev:api      # API on http://localhost:8000 (see services/api/README.md for first-time setup)
npm run dev:web      # web on http://localhost:3000
```

The Products pages need the API and its database running. Without them, they show a
"Can't load products" message with a retry button.

## Checks

```bash
npm run typecheck:web
npm run lint:web
npm run build:web
```

## Notes

- The Overview screen still uses **sample data** from `src/lib/sample-data.ts`. It is labeled in the UI and is not real.
- shadcn components live in `src/components/ui/`. Add more with `npx shadcn@latest add <name>` from this folder.
