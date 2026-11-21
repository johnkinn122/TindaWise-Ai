// Starts the FastAPI dev server with the project's virtual environment, on any OS.
// Usage: npm run dev:api
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const apiDir = join(import.meta.dirname, "..", "services", "api");
const python =
  process.platform === "win32"
    ? join(apiDir, ".venv", "Scripts", "python.exe")
    : join(apiDir, ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error("No virtual environment found in services/api/.venv. See services/api/README.md for setup.");
  process.exit(1);
}

const child = spawn(python, ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], {
  cwd: apiDir,
  stdio: "inherit",
});
child.on("exit", (code) => process.exit(code ?? 0));
