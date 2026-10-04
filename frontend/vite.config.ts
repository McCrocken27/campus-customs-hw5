import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend (http://localhost:8000) allows requests from this exact origin,
// so always use port 5173 instead of picking another one if it's busy.
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
  },
})
