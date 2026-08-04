import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Explicit IPv4 loopback, not the default "localhost" string - that
    // resolves ambiguously to ::1 vs 127.0.0.1 depending on the machine,
    // which caused real (not just test-environment) connection failures.
    host: '127.0.0.1',
  },
})
