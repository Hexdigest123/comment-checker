import { defineConfig } from 'astro/config';
import next from '@astrojs/next';
import tailwind from '@astrojs/tailwind';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  adapter: next({
    mode: 'standalone',
  }),
  integrations: [
    tailwind(),
    next(),
  ],
  server: {
    port: 3000,
    host: true,
  },
  vite: {
    server: {
      watch: {
        usePolling: true,
      },
    },
  },
});
