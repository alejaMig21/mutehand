import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base: the built editor is served by the Python app from any path, with no Node at runtime.
export default defineConfig({
  plugins: [react()],
  base: './',
  // the built editor goes inside the Python package, so a wheel carries it
  build: { outDir: '../src/workflow_factory/web', emptyOutDir: true },
})
