// Shared by scripts/api.mjs and scripts/ml.mjs: run Python steps inside a service's .venv on any OS.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

/**
 * Runs each argument list with `<serviceDir>/.venv`'s Python, from `serviceDir`, stopping at the
 * first failure. Exits the process with that step's status.
 */
export function runInVenv(serviceDir, steps) {
  const bin = process.platform === "win32" ? join(serviceDir, ".venv", "Scripts") : join(serviceDir, ".venv", "bin");
  const python = join(bin, process.platform === "win32" ? "python.exe" : "python");

  if (!existsSync(python)) {
    console.error(`No virtual environment in ${join(serviceDir, ".venv")}. See that service's README.md for setup.`);
    process.exit(1);
  }
  for (const args of steps) {
    const { status } = spawnSync(python, args, { cwd: serviceDir, stdio: "inherit" });
    if (status !== 0) process.exit(status ?? 1);
  }
}

/** Looks up `tasks[name]`, or prints usage and exits. */
export function pickTask(script, tasks, name) {
  const steps = tasks[name];
  if (!steps) {
    console.error(`Usage: node scripts/${script} <${Object.keys(tasks).join("|")}>`);
    process.exit(2);
  }
  return steps;
}
