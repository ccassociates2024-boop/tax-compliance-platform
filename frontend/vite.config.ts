import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // Dev proxy — avoids CORS when running `npm run dev` locally
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // VITE_ prefixed env vars are automatically exposed to client code
  // No extra config needed — import.meta.env.VITE_DEMO_MODE works out of the box
})
