import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import vuetify from 'vite-plugin-vuetify';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(process.cwd(), '..'), '');
  const frontendEnv = loadEnv(mode, process.cwd(), '');
  const env = { ...rootEnv, ...frontendEnv };
  const frontendPort = Number(env.FRONTEND_PORT || 5173);
  const apiTarget = String(env.VITE_API_BASE_URL || `http://localhost:${env.BACKEND_PORT || 8040}`).replace(/\/$/, '');

  return {
    plugins: [
      vue(),
      vuetify({ autoImport: true })
    ],
    build: {
      rollupOptions: {
        output: {
          // Schwere, selten geänderte Vendor-Libs in eigene Chunks → besseres
          // Browser-Caching + paralleles Laden. pdfjs bleibt im lazy PdfPreview-Chunk.
          manualChunks(id) {
            if (id.includes('node_modules/vuetify')) return 'vuetify';
            if (/node_modules\/(@vue|vue|vue-router|pinia)\//.test(id)) return 'vue-core';
            // pdfjs wird von mehreren lazy Chunks (PdfPreview, ImportStaging)
            // genutzt → eigener gemeinsamer Chunk statt Duplizierung.
            if (id.includes('node_modules/pdfjs-dist')) return 'pdfjs';
            return undefined;
          }
        }
      }
    },
    server: {
      host: '0.0.0.0',
      port: frontendPort,
      strictPort: true,
      hmr: {
        host: env.VITE_HMR_HOST || 'localhost',
        port: Number(env.VITE_HMR_PORT || frontendPort),
        protocol: env.VITE_HMR_PROTOCOL || 'ws'
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true
        }
      }
    }
  };
});
