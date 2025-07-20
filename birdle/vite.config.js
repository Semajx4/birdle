import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import path from "path"

export default defineConfig({
  root: 'src/frontend',
  plugins: [svelte()],
})