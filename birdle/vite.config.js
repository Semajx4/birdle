import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import path from "path"

export default defineConfig({
  root: 'src/frontend',
  plugins: [svelte()],
    server: {
        proxy: {
            "/api": process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        },
    }
})
