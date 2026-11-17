// 插件联邦构建入口。MoviePilot 宿主负责通过 remoteEntry 加载各组件并挂载，
// 这里只需要把组件暴露给 rollup 图，所以统一在此 re-export。
export { default as Page } from './components/Page.vue'
export { default as Config } from './components/Config.vue'
export { default as Dashboard } from './components/Dashboard.vue'
export { default as AppPage } from './components/AppPage.vue'
