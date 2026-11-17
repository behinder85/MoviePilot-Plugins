import { fileURLToPath } from 'node:url'

import vue from '@vitejs/plugin-vue'
import federation from '@originjs/vite-plugin-federation'
import { defineConfig, type Plugin } from 'vite'

// 与 MoviePilot v2.15.6 宿主保持一致：originjs 联邦插件（宿主 devDependencies 也是 ^1.4.1）。
//
// 关键约束（照抄 GitHub 上已在 v2.15.6 实际运行的 Vue 插件工程做法）：
// 1. 入口用 src/main.ts（不是 index.html），产物 outDir = frontend/dist；
// 2. base 保持默认 '/'：originjs 生成暴露模块引用时 base 为 './' 会拼成
//    "./assets/xxx.js"（相对 remoteEntry 所在目录就成了 assets/assets/xxx.js，404）；
//    base 为 '/' 时走 "./xxx.js" 分支，正好与 remoteEntry 同目录；
// 3. shared 里 vue / vuetify / vuetify/styles 用 generate:false —— 由宿主提供单例，
//    插件不再重复打包一份，否则体积巨大且可能出现两份 Vuetify 实例；
// 4. 插件 get_render_mode 必须返回 ("vue","frontend/dist/assets")。
// generate:false 时 originjs 仍会把 Vuetify 的样式抽成独立 css bundle（宿主已提供样式，
// 重复加载会污染宿主）。这里在产物里直接丢弃。
function dropSharedVuetifyCss(): Plugin {
  return {
    name: 'drop-shared-vuetify-css',
    enforce: 'post',
    generateBundle(_options, bundle) {
      for (const fileName of Object.keys(bundle)) {
        if (fileName.includes('__federation_shared_vuetify')) delete bundle[fileName]
      }
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    federation({
      name: 'CrossSeedRelocator',
      filename: 'remoteEntry.js',
      exposes: {
        './Page': './src/components/Page.vue',
        './Config': './src/components/Config.vue',
        './Dashboard': './src/components/Dashboard.vue',
        './AppPage': './src/components/AppPage.vue',
      },
      shared: {
        vue: { requiredVersion: false, generate: false },
        vuetify: { requiredVersion: false, generate: false },
        'vuetify/styles': { requiredVersion: false, generate: false },
      },
    }),
    dropSharedVuetifyCss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    dedupe: ['vue', 'vuetify'],
  },
  build: {
    target: 'esnext',
    minify: false,
    cssCodeSplit: true,
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/main.ts',
    },
  },
})