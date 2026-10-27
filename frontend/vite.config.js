import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const proxy = {
  '/api': process.env.SITE_API_TARGET || 'http://127.0.0.1:8010',
}
export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', port: 5180, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy },
})
