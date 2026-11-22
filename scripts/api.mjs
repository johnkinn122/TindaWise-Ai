// Runs API tasks with the services/api virtual environment, on any OS.
//   npm run dev:api   → uvicorn with reload on :8000
//   npm run test:api  → pytest
//   npm run lint:api  → ruff check + ruff format --check
import { join } from "node:path";
import { pickTask, runInVenv } from "./python-venv.mjs";

const apiDir = join(import.meta.dirname, "..", "services", "api");

const tasks = {
  // --reload-dir app: watch only source code. Watching the whole folder also watches .venv,
  // which pytest writes to, and on Windows those reloads can hang with the old code running.
  dev: [["-m", "uvicorn", "app.main:app", "--reload", "--reload-dir", "app", "--port", "8000"]],
  test: [["-m", "pytest", ...process.argv.slice(3)]],
  lint: [
    ["-m", "ruff", "check", "."],
    ["-m", "ruff", "format", "--check", "."],
  ],
};

runInVenv(apiDir, pickTask("api.mjs", tasks, process.argv[2]));
