import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [
      vue(),
      Components({ resolvers: [
        name => name==='ElInput' ? {name:'default',from:fileURLToPath(new URL('./src/components/common/ScreenshotInput.vue',import.meta.url)).replaceAll('\\','/')} : undefined,
        name => ({ElTableColumn:'ScreenshotTableColumn',ElDescriptionsItem:'ScreenshotDescriptionsItem'}[name]?{name:{ElTableColumn:'ScreenshotTableColumn',ElDescriptionsItem:'ScreenshotDescriptionsItem'}[name],from:fileURLToPath(new URL('./src/components/common/screenshotDisplays.js',import.meta.url)).replaceAll('\\','/'),sideEffects:`element-plus/es/components/${name==='ElTableColumn'?'table':'descriptions'}/style/css`}:undefined),
        name => ({ ElSelect: 'SearchSelect', ElCascader: 'SearchCascader', ElTransfer: 'SearchTransfer' }[name]
          ? { name: { ElSelect: 'SearchSelect', ElCascader: 'SearchCascader', ElTransfer: 'SearchTransfer' }[name], from: fileURLToPath(new URL('./src/components/common/searchableControls.js', import.meta.url)).replaceAll('\\', '/'), sideEffects: `element-plus/es/components/${name.slice(2).toLowerCase()}/style/css` } : undefined),
        ElementPlusResolver(),
      ] })
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '127.0.0.1', // 本 PC 默认入口；局域网调试时通过命令行显式指定 host
      port: 3000,
      strictPort: true, // 避免端口被占用时静默改到其他地址
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          ws: true,
          rewrite: (path) => path.replace(/^\/api/, '')
        }
      }
    },
    build: { manifest: true }
  }
})
