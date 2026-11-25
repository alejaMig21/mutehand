import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base: the built editor is served by the Python app from any path, with no Node at runtime.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
})
