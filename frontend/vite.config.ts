import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: [
        'vue',
        'vue-router',
        'pinia',
        '@vueuse/core'
      ],
      dts: true,
      eslintrc: {
        enabled: true
      }
    }),
    // 自动按需组件导入
    Components({
      resolvers: [ElementPlusResolver()],
      dts: true
    })
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@components': resolve(__dirname, 'src/components'),
      '@views': resolve(__dirname, 'src/views'),
      '@stores': resolve(__dirname, 'src/stores'),
      '@utils': resolve(__dirname, 'src/utils'),
      '@types': resolve(__dirname, 'src/types'),
      '@api': resolve(__dirname, 'src/api')
    }
  },
  server: {
    // fork-local: 端口段位 54300-54309 + 强制 loopback only（个人使用，不对外）
    // 见根目录 CLAUDE.md「端口分配」+「项目特殊约定」段
    host: '127.0.0.1',
    port: 54300,
    strictPort: true,
    hmr: {
      overlay: false,
      host: '127.0.0.1'
    },
    // 允许从项目根目录之外（例如 /docs）导入原始文件
    fs: {
      allow: [resolve(__dirname, '..')]
    },
    proxy: {
      '/api': {
        // 后端在 fork-local :54301（端口段位约定，非上游默认 8000）
        target: 'http://127.0.0.1:54301',
        changeOrigin: true,
        secure: false,
        ws: true  // 🔥 启用 WebSocket 代理支持
      }
    }
  },
  build: {
    target: 'es2020',  // 支持 nullish coalescing operator (??) 和 optional chaining (?.)
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    rollupOptions: {
      output: {
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: '[ext]/[name]-[hash].[ext]'
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables.scss" as *;`
      }
    }
  }
})
