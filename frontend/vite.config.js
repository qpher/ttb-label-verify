import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // Served by FastAPI in production — see backend/app/main.py.
    // (The Dockerfile overrides outDir for the container layout.)
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
