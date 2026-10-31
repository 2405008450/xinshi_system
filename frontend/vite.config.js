import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'
import basicSsl from '@vitejs/plugin-basic-ssl'
import fs from 'fs'         // 👈 新增
import path from 'path'     // 👈 新增

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [
      vue(),
      Components({ resolvers: [
        name => name === 'ElPopover' ? { name: 'default', from: fileURLToPath(new URL('./src/components/common/WindowPopover.vue', import.meta.url)).replaceAll('\\', '/'), sideEffects: 'element-plus/es/components/popover/style/css' } : undefined,
        name => name==='ElInput' ? {name:'default',from:fileURLToPath(new URL('./src/components/common/ScreenshotInput.vue',import.meta.url)).replaceAll('\\','/')} : undefined,
        name => ({ElTableColumn:'ScreenshotTableColumn',ElDescriptions:'ScreenshotDescriptions'}[name]?{name:{ElTableColumn:'ScreenshotTableColumn',ElDescriptions:'ScreenshotDescriptions'}[name],from:fileURLToPath(new URL('./src/components/common/screenshotDisplays.js',import.meta.url)).replaceAll('\\','/'),sideEffects:`element-plus/es/components/${name==='ElTableColumn'?'table':'descriptions'}/style/css`}:undefined),
        name => ({ ElSelect: 'SearchSelect', ElCascader: 'SearchCascader', ElTransfer: 'SearchTransfer' }[name]
          ? { name: { ElSelect: 'SearchSelect', ElCascader: 'SearchCascader', ElTransfer: 'SearchTransfer' }[name], from: fileURLToPath(new URL('./src/components/common/searchableControls.js', import.meta.url)).replaceAll('\\', '/'), sideEffects: `element-plus/es/components/${name.slice(2).toLowerCase()}/style/css` } : undefined),
        ElementPlusResolver(),
      ] }),
//      basicSsl(),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '0.0.0.0', // 本 PC 默认入口；局域网调试时通过命令行显式指定 host
//    https: true,
      port: 3000,
      strictPort: true, // 避免端口被占用时静默改到其他地址
      https: {  // 👈 新增 https 配置
      key: fs.readFileSync(path.resolve(__dirname, '192.168.31.144+2-key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, '192.168.31.144+2.pem')),
    },
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          rewrite: (path) => path.replace(/^\/api/, '')
        }
      }
    },
    build: { manifest: true }
  }
})
