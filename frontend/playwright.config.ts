import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";
const backend = resolve("..", "backend");
const python = process.env.PYTHON || resolve(backend, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  timeout: 30000,
  outputDir: "../scripts/out/ui-tests",
  use: { baseURL: "http://127.0.0.1:8023", browserName: "chromium" },
  webServer: {
    command: `"${python}" -m uvicorn tests.ui_server:app --app-dir "${backend}" --host 127.0.0.1 --port 8023`,
    url: "http://127.0.0.1:8023/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
