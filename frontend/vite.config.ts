import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode, command }) => ({
  plugins: [vue(), {
    name: 'explicit-development-mock',
    async configureServer(server) {
      if (command !== 'serve' || loadEnv(mode, process.cwd()).VITE_API_MODE !== 'mock') return
      const { mockApi, resetMock } = await import('./dev/mock-api')
      server.middlewares.use((req, res, next) => {
        if (req.url === '/__dev/reset' && req.method === 'POST') { resetMock(); res.statusCode = 204; return res.end() }
        if (!req.url?.startsWith('/api/')) return next()
        void mockApi(req, res).catch(() => { if (!res.headersSent) { res.statusCode = 500; res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ error: { code: 'internal_error', message: 'Development mock error.' } })) } })
      })
    },
  }],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
}))
