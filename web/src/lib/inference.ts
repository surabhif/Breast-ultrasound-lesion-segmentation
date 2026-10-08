/** Compatibility re-export — inference runs in a Web Worker via inferenceClient. */
export {
  preloadModel,
  runInference,
  runInferenceTta,
  cancelInference,
  rethreshold,
  type InferenceResult,
  type LoadProgress,
} from './inferenceClient'
