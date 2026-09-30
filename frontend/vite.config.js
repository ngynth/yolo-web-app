import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Expose server to Docker host network
    port: 5173,      // Force port 5173
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://backend:8000', // Docker backend service name
        changeOrigin: true,
      },
      '/static': {
        target: 'http://backend:8000', // Proxy static images/videos
        changeOrigin: true,
      }
    }
  }
})