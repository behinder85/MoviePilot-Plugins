<template>
  <v-card variant="tonal" class="pa-3">
    <div class="d-flex align-center mb-2">
      <v-icon class="mr-2" size="20">mdi-swap-horizontal-bold</v-icon>
      <span class="text-subtitle-2">辅种路径回迁</span>
      <v-spacer />
      <v-chip size="x-small" :color="data.enabled ? 'success' : 'grey'">{{ data.enabled ? '启用' : '停用' }}</v-chip>
    </div>
    <div class="d-flex justify-space-between text-caption">
      <span>待处理</span><b>{{ data.stats?.ready || 0 }}</b>
    </div>
    <div class="d-flex justify-space-between text-caption">
      <span>无源保留</span><b>{{ data.stats?.no_source || 0 }}</b>
    </div>
    <div class="d-flex justify-space-between text-caption">
      <span>累计成功</span><b>{{ data.success_count || 0 }}</b>
    </div>
    <div class="text-caption text-medium-emphasis mt-2">{{ data.last_run?.finished_at || '尚未运行' }}</div>
  </v-card>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { usePluginApi } from '../api'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: false },
  nativeSubscribe: { type: Function, default: null },
})
const client = usePluginApi(props)
const data = reactive({})

onMounted(async () => {
  try {
    Object.assign(data, (await client.get('status')) || {})
  } catch (error) {
    // 仪表盘加载失败时保持静默，不打扰主界面
  }
})
</script>
