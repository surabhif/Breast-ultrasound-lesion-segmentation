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
import { runInference } from './lib/inference'
import { postprocessMask, removeSmallComponents } from './lib/morphology'
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
      runInference: typeof runInference
      postprocessMask: typeof postprocessMask
      removeSmallComponents: typeof removeSmallComponents
    }
  }
}

window.__BUSI_PARITY__ = {
  MODEL_VERSION,
  SEG_THRESHOLD,
  MIN_COMPONENT_AREA,
  ensureModelManifest,
  runInference,
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
