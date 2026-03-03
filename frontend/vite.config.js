import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import vuetify from 'vite-plugin-vuetify';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const frontendPort = Number(env.FRONTEND_PORT || 5173);

  return {
    plugins: [
      vue(),
      vuetify({ autoImport: true })
    ],
    server: {
      host: '0.0.0.0',
      port: frontendPort,
      strictPort: true,
      hmr: {
        host: env.VITE_HMR_HOST || 'localhost',
        port: Number(env.VITE_HMR_PORT || frontendPort),
        protocol: env.VITE_HMR_PROTOCOL || 'ws'
      }
    }
  };
});
