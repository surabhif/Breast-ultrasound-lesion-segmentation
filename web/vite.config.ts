import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const buildDate = new Date().toISOString().slice(0, 10)

// GitHub Pages project site needs the repo name as base.
// Locally and on preview, use '/'. CI sets VITE_BASE.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE || '/',
  assetsInclude: ['**/*.onnx'],
  define: {
    // Injected at build time for the footer “Last updated” line.
    __BUILD_DATE__: JSON.stringify(buildDate),
  },
  optimizeDeps: {
    exclude: ['onnxruntime-web'],
  },
  build: {
    // Let React.lazy + dynamic import('./lib/inference') create natural async
    // chunks. Avoid manualChunks for app pages — forcing them pulled shared
    // router/constants into a “page” chunk that the shell then eagerly loaded.
    modulePreload: {
      resolveDependencies: (_filename, deps) =>
        // Never preload the ONNX client / worker from the app shell.
        deps.filter(
          (d) =>
            !d.includes('inference') &&
            !d.includes('onnxruntime') &&
            !d.includes('ort-'),
        ),
    },
  },
})
