import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Dev: /api and /images go to VITE_BACKEND_URL (mock backend or the Colab URL), same-origin for the cookie
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_BACKEND_URL || 'http://localhost:8000'
  const proxy = { target, changeOrigin: true, secure: true }
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': `${import.meta.dirname}/src` } },
    server: { proxy: { '/api': { ...proxy, ws: true }, '/images': proxy } },
  }
})
