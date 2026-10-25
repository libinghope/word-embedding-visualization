import { defineConfig } from '@playwright/test'
export default defineConfig({ testDir: './tests/e2e', use: { baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 900 }, browserName: 'chromium', channel: process.env.PLAYWRIGHT_CHANNEL || undefined, launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } }, reporter: 'list' })
