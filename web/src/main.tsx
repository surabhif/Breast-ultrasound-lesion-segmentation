import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import {
  MODEL_VERSION,
  MIN_COMPONENT_AREA,
  SEG_THRESHOLD,
  ensureModelManifest,
} from './lib/constants'
import { postprocessMask, removeSmallComponents } from './lib/morphology'
import { initTheme } from './lib/theme'
import './index.css'

const basename = import.meta.env.BASE_URL.replace(/\/$/, '') || ''

/** Test hook for Playwright parity (Python ONNX vs browser pipeline). */
declare global {
  interface Window {
    __BUSI_PARITY__?: {
      MODEL_VERSION: string
      SEG_THRESHOLD: number
      MIN_COMPONENT_AREA: number
      ensureModelManifest: typeof ensureModelManifest
      // Kept loose so main never statically imports the ONNX client module.
      runInference: (
        source: string | File,
        onProgress?: (p: unknown) => void,
        opts?: { segThreshold?: number },
      ) => Promise<{
        clsProb: number
        maskMean: number
        mask: Float32Array
        maskH: number
        maskW: number
      }>
      postprocessMask: typeof postprocessMask
      removeSmallComponents: typeof removeSmallComponents
    }
  }
}

// Apply theme before first paint of React tree (respects system + saved choice).
initTheme()

/**
 * Parity hooks stay available on every route, but the ONNX client is loaded
 * only when runInference is first called (Demo / Try / parity tests).
 */
window.__BUSI_PARITY__ = {
  MODEL_VERSION,
  SEG_THRESHOLD,
  MIN_COMPONENT_AREA,
  ensureModelManifest,
  runInference: async (source, onProgress, opts) => {
    const { runInference } = await import('./lib/inference')
    return runInference(source, onProgress, opts)
  },
  postprocessMask,
  removeSmallComponents,
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)

/** Register service worker for app-shell + ONNX offline cache (versioned by current.json cache_key). */
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  const swUrl = `${import.meta.env.BASE_URL}sw.js`
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register(swUrl, { scope: import.meta.env.BASE_URL }).catch((err) => {
      console.warn('Service worker registration failed', err)
    })
  })
}
