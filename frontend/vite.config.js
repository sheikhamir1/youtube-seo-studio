import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Development: the Vite dev server proxies /api to the FastAPI backend so the
// browser never needs a hardcoded backend origin. Production: Nginx proxies /api.
export default defineConfig({
  plugins: [react()],
  server: {
    // Bind on all interfaces so the dev server is reachable from outside the
    // container/VM, and accept the proxied preview host used during hosted
    // development (the browser never talks to the backend directly).
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Server-Sent Events must not be buffered.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform';
            }
          });
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.{js,jsx}'],
    css: false,
  },
});
