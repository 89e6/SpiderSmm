# SpiderSmm

Arabic social media marketing service panel imported from the attached Python application.

## Run & Operate

- `pnpm --filter @workspace/spider-smm run dev` — run the SpiderSmm web panel
- `pnpm --filter @workspace/api-server run dev` — run the shared API server
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- The SpiderSmm panel stores its local JSON data beside `main.py` and listens on the workflow-provided `PORT`.

## Stack

- pnpm workspaces, Node.js 24, Python 3
- SpiderSmm: Python standard-library HTTP server with Arabic RTL HTML/CSS UI
- Shared API: Express 5
- DB libraries: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild for the shared API and Python bytecode validation for SpiderSmm

## Where things live

- `artifacts/spider-smm/main.py` — imported SpiderSmm application and page/router behavior
- `artifacts/spider-smm/requirements.txt` — original Python dependency list
- `artifacts/api-server/` — shared Express API service
- `lib/api-spec/openapi.yaml` — API contract source of truth
- `lib/db/src/schema/` — database schema source of truth

## Architecture decisions

- The attached Python application remains the source of truth for the SpiderSmm user experience.
- The web artifact launches the Python HTTP server directly so its existing forms, sessions, and routes work without a frontend rewrite.
- The artifact root path is reserved for SpiderSmm so the preview opens directly to the login experience.

## Product

- Arabic RTL social media marketing service panel
- User registration and login
- Service catalog and order placement
- Order history and account settings
- Admin panel for services, balances, users, and site status

## User preferences

No additional preferences recorded.

## Gotchas

- Run the SpiderSmm workflow rather than the shared API workflow when previewing the user-facing panel.
- The imported app uses its own JSON file for local persistence and initializes its data on startup.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
