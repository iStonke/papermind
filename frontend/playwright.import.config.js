import { defineConfig } from '@playwright/test';
import base from './playwright.config.js';

// Dedicated matrix keeps the everyday browser suite fast while making the
// import regression/stress suite repeatable on all three browser engines.
export default defineConfig({
  ...base,
  testMatch: /(?:importWorkflow|scannerPreviewTransition|importTechnical|importRetention|importStartLayout)\.spec\.js$/,
  use: { ...base.use, channel: undefined },
  projects: ['chromium', 'firefox', 'webkit'].map(browserName => ({ name: browserName, use: { browserName } })),
});
