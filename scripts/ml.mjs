// Runs ML tasks with the services/ml virtual environment, on any OS.
//   npm run test:ml      → pytest
//   npm run lint:ml      → ruff check + ruff format --check
//   npm run backtest:ml  → score the forecasting baselines on synthetic history (extra args pass through)
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
};

runInVenv(mlDir, pickTask("ml.mjs", tasks, process.argv[2]));
