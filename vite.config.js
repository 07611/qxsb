import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      host: '0.0.0.0',
      port: Number(env.VITE_DEV_PORT || 5173),
      proxy: {
        '/api': { target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
        '/media': { target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
        '/healthz': { target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
        '/s/': { target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ['vue', 'vue-router', 'pinia', 'vue-i18n'],
            element: ['element-plus', '@element-plus/icons-vue'],
          },
        },
      },
    },
    test: {
      environment: 'node',
      include: ['tests/**/*.test.js'],
    },
  }
})
