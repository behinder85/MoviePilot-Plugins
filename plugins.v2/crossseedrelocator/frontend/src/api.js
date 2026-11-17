// 统一封装宿主注入的 api：props.api 已带 /api/v1 前缀，MP 会自动在插件 path 前加插件 ID。
export function usePluginApi(props) {
  const root = () => `plugin/${props.pluginId}`
  const unwrap = res => (res && res.data !== undefined ? res.data : res)
  return {
    get: async (path, config) => unwrap(await props.api.get(`${root()}/${path}`, config)),
    post: async (path, data) => unwrap(await props.api.post(`${root()}/${path}`, data || {})),
  }
}

export function formatSize(bytes) {
  const value = Number(bytes || 0)
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  let idx = 0
  let size = value
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx += 1
  }
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[idx]}`
}

export function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}
