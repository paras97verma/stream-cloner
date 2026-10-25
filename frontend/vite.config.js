import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  base: './',
  build: {
    outDir: path.resolve(import.meta.dirname, '../src/stream_cloner/web/dist'),
    emptyOutDir: true,
  },
})
