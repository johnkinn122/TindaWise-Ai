// Runs API tasks with the services/api virtual environment, on any OS.
//   npm run dev:api   → uvicorn with reload on :8000
//   npm run test:api  → pytest
//   npm run lint:api  → ruff check + ruff format --check
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const apiDir = join(import.meta.dirname, "..", "services", "api");
const bin = process.platform === "win32" ? join(apiDir, ".venv", "Scripts") : join(apiDir, ".venv", "bin");
const python = join(bin, process.platform === "win32" ? "python.exe" : "python");

if (!existsSync(python)) {
  console.error("No virtual environment in services/api/.venv. See services/api/README.md for setup.");
  process.exit(1);
}

const tasks = {
  dev: [["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"]],
  test: [["-m", "pytest", ...process.argv.slice(3)]],
  lint: [
    ["-m", "ruff", "check", "."],
    ["-m", "ruff", "format", "--check", "."],
  ],
};

const steps = tasks[process.argv[2]];
if (!steps) {
  console.error(`Usage: node scripts/api.mjs <${Object.keys(tasks).join("|")}>`);
  process.exit(2);
}
for (const args of steps) {
  const { status } = spawnSync(python, args, { cwd: apiDir, stdio: "inherit" });
  if (status !== 0) process.exit(status ?? 1);
}
