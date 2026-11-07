import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Vite's dev pre-bundling breaks maplibre-gl's worker URL ("Worker failed to load"); checked 7 Nov 2026.
  optimizeDeps: { exclude: ['maplibre-gl'] },
})
