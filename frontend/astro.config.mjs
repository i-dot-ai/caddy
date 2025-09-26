// @ts-check
import 'dotenv/config';
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';
import sentry from '@sentry/astro';
import tailwindcss from '@tailwindcss/vite';


// https://astro.build/config
export default defineConfig({
  // host: true enables astro to work in Docker
  server: { port: 4322, host: true },
  output: 'server',

  adapter: node({
    mode: 'standalone',
  }),

  devToolbar: {
    enabled: false,
  },

  integrations: [
    sentry({
      dsn: process.env.SENTRY_DSN?.replaceAll('"', ''),
      tracesSampleRate: 0,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,

      /*
       * Setting this option to true will send default PII data to Sentry.
       * For example, automatic IP address collection on events
       */
      sendDefaultPii: true,
      sourceMapsUploadOptions: {
        project: 'caddy',
        authToken: process.env.SENTRY_AUTH_TOKEN?.replaceAll('"', ''),
      },
    }),
  ],

  vite: {
    plugins: [tailwindcss()],
  },
});
