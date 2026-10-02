// The native launcher replaces this development proxy with the real bridge source.
// Keeping it in the patch tree lets TypeScript resolve the same import in-place.
export * from '../../../../../frontend-bridge/src/index.js'
