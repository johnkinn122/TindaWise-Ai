# Tindawise — web app

Next.js frontend for Tindawise AI. See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) for structure and decisions,
and [`design-system/tindawise-ai/MASTER.md`](../../design-system/tindawise-ai/MASTER.md) for design rules.

## Run it

From the repository root:

```bash
npm install          # once
npm run dev:web      # http://localhost:3000
```

## Checks

```bash
npm run typecheck:web
npm run lint:web
npm run build:web
```

## Notes

- The Overview screen uses **sample data** from `src/lib/sample-data.ts`. It is labeled in the UI and is not real.
- shadcn components live in `src/components/ui/`. Add more with `npx shadcn@latest add <name>` from this folder.
