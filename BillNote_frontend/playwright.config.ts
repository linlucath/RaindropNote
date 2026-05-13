import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/smoke',
  timeout: 60_000,
  use: {
    baseURL: 'http://127.0.0.1:3015',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'pnpm dev --host 127.0.0.1 --port 3015 --strictPort',
    port: 3015,
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
