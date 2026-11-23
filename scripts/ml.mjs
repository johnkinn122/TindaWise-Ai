// Runs ML tasks with the services/ml virtual environment, on any OS.
//   npm run test:ml      → pytest
//   npm run lint:ml      → ruff check + ruff format --check
//   npm run backtest:ml  → score the forecasters on the test period of synthetic history (extra args pass through)
//   npm run tune:ml      → score LightGBM settings on the validation period (a few minutes)
//   npm run policies:ml  → replay the test period with reorder policies (a few minutes)
//   npm run anomalies:ml → plant labelled anomalies and score the detectors
//   npm run shrinkage:ml → simulate stock counts with planted losses and score the detectors
import { join } from "node:path";
import { pickTask, runInVenv } from "./python-venv.mjs";

const mlDir = join(import.meta.dirname, "..", "services", "ml");
const extra = process.argv.slice(3);

const tasks = {
  test: [["-m", "pytest", ...extra]],
  lint: [
    ["-m", "ruff", "check", "."],
    ["-m", "ruff", "format", "--check", "."],
  ],
  backtest: [["-m", "tindawise_ml", "backtest", ...extra]],
  tune: [["-m", "tindawise_ml", "tune", ...extra]],
  policies: [["-m", "tindawise_ml", "policies", ...extra]],
  anomalies: [["-m", "tindawise_ml", "anomalies", ...extra]],
  shrinkage: [["-m", "tindawise_ml", "shrinkage", ...extra]],
};

runInVenv(mlDir, pickTask("ml.mjs", tasks, process.argv[2]));
