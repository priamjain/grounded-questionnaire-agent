import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Single deployable: the build lands where FastAPI serves it from.
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
