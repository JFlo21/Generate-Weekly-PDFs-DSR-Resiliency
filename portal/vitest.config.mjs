import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      include: ['services/**', 'routes/**', 'middleware/**'],
    },
  },
});
