<template>
  <div>
    <!-- 主操作台：状态、预演、执行、回滚 -->
    <RelocatorConsole
      :api="api"
      :pluginId="pluginId"
      :sourcePluginId="sourcePluginId"
      :nativeSubscribe="nativeSubscribe"
      @action="onAction"
    />

    <v-card flat class="mt-3">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-history</v-icon>
        <span>运行明细与清理</span>
        <v-spacer />
        <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="loadAll">刷新</v-btn>
      </v-card-title>
      <v-card-text>
        <v-tabs v-model="tab" density="compact" class="mb-3">
          <v-tab value="runs">运行历史</v-tab>
          <v-tab value="entries">逐种子明细</v-tab>
          <v-tab value="nosource">无源清单</v-tab>
          <v-tab value="cleanup">链接目录清理</v-tab>
          <v-tab value="logs">运行日志</v-tab>
        </v-tabs>

        <v-window v-model="tab">
          <v-window-item value="runs">
            <v-table density="compact">
              <thead><tr><th>时间</th><th>模式</th><th>可回迁</th><th>成功</th><th>失败</th><th>跳过</th><th>无源</th><th>清理删除</th></tr></thead>
              <tbody>
                <tr v-for="(run, idx) in journal.runs" :key="idx">
                  <td>{{ formatTime(run.finished_at || run.started_at) }}</td>
                  <td>{{ run.mode }}</td>
                  <td>{{ run.stats?.ready ?? '-' }}</td>
                  <td>{{ run.moved_count ?? run.stats?.moved ?? '-' }}</td>
                  <td>{{ run.failed_count ?? '-' }}</td>
                  <td>{{ run.skipped_count ?? '-' }}</td>
                  <td>{{ run.stats?.no_source ?? '-' }}</td>
                  <td>{{ run.cleanup?.deleted_files ?? '-' }}</td>
                </tr>
                <tr v-if="!journal.runs?.length"><td colspan="8">暂无运行记录</td></tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="entries">
            <v-table density="compact" fixed-header height="420">
              <thead><tr><th>ID</th><th>名称</th><th>状态</th><th>旧路径</th><th>新路径</th><th>更新时间</th></tr></thead>
              <tbody>
                <tr v-for="entry in journal.entries" :key="entry.id">
                  <td>{{ entry.id }}</td>
                  <td class="text-truncate" style="max-width: 200px">{{ entry.name }}</td>
                  <td><v-chip size="x-small" :color="statusColor(entry.status)" variant="flat">{{ statusText(entry.status) }}</v-chip></td>
                  <td class="text-truncate" style="max-width: 220px">{{ entry.old_dir }}</td>
                  <td class="text-truncate" style="max-width: 220px">{{ entry.new_dir }}</td>
                  <td>{{ formatTime(entry.updated_at) }}</td>
                </tr>
                <tr v-if="!journal.entries?.length"><td colspan="6">暂无明细</td></tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="nosource">
            <v-alert type="info" variant="tonal" density="compact" class="mb-3">
              这些种子在链接目录下找不到同内容的源（季包聚合或源已删除），保持原位并保留 cross-seed 标签。
            </v-alert>
            <v-table density="compact">
              <thead><tr><th>ID</th><th>名称</th><th>体积</th><th>当前路径</th><th>原因</th></tr></thead>
              <tbody>
                <tr v-for="entry in journal.no_source" :key="entry.id">
                  <td>{{ entry.id }}</td>
                  <td class="text-truncate" style="max-width: 240px">{{ entry.name }}</td>
                  <td>{{ formatSize(entry.size) }}</td>
                  <td class="text-truncate" style="max-width: 220px">{{ entry.current_dir }}</td>
                  <td>{{ entry.reason }}</td>
                </tr>
                <tr v-if="!journal.no_source?.length"><td colspan="5">暂无无源种子</td></tr>
              </tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="cleanup">
            <div class="d-flex flex-wrap ga-2 mb-3">
              <v-btn color="primary" variant="flat" prepend-icon="mdi-eye" :loading="cleanupLoading" @click="runCleanup(true)">预演清理</v-btn>
              <v-btn color="error" variant="flat" prepend-icon="mdi-delete" :loading="cleanupLoading" @click="runCleanup(false)">实际清理</v-btn>
            </div>
            <v-alert v-if="cleanup.message" type="info" variant="tonal" density="compact" class="mb-3">{{ cleanup.message }}</v-alert>
            <v-row dense v-if="cleanup.cs_root">
              <v-col cols="6" md="3"><v-card variant="tonal" class="pa-3"><div class="text-caption">扫描文件</div><div class="text-h6">{{ cleanup.scanned_files }}</div></v-card></v-col>
              <v-col cols="6" md="3"><v-card variant="tonal" class="pa-3"><div class="text-caption">受保护</div><div class="text-h6">{{ cleanup.protected_files }}</div></v-card></v-col>
              <v-col cols="6" md="3"><v-card variant="tonal" color="warning" class="pa-3"><div class="text-caption">可删除</div><div class="text-h6">{{ cleanup.deletable_files }}</div><div class="text-caption">{{ cleanup.deletable_human }}</div></v-card></v-col>
              <v-col cols="6" md="3"><v-card variant="tonal" color="success" class="pa-3"><div class="text-caption">已删除</div><div class="text-h6">{{ cleanup.deleted_files }}</div><div class="text-caption">{{ cleanup.deleted_human }}</div></v-card></v-col>
            </v-row>
            <v-table density="compact" class="mt-3" v-if="cleanup.sample?.length">
              <thead><tr><th>可删除文件示例</th></tr></thead>
              <tbody><tr v-for="path in cleanup.sample" :key="path"><td class="text-caption">{{ path }}</td></tr></tbody>
            </v-table>
          </v-window-item>

          <v-window-item value="logs">
            <v-sheet class="pa-3" color="grey-darken-4" rounded>
              <pre class="text-caption" style="white-space: pre-wrap; color: #e0e0e0">{{ logs }}</pre>
            </v-sheet>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import RelocatorConsole from './Page.vue'
import { usePluginApi, formatSize, formatTime } from '../api'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  navKey: { type: String, default: 'main' },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['action'])
const client = usePluginApi(props)

const loading = ref(false)
const tab = ref('runs')
const journal = reactive({ runs: [], entries: [], no_source: [] })
const cleanup = reactive({ sample: [] })
const cleanupLoading = ref(false)
const logs = ref('加载中…')

function statusColor(value) {
  return { success: 'success', failed: 'error', relocating: 'info', rolled_back: 'warning', no_source: 'secondary' }[value] || 'grey'
}
function statusText(value) {
  return { success: '成功', failed: '失败', relocating: '处理中', rolled_back: '已回滚' }[value] || value
}

async function loadAll() {
  loading.value = true
  try {
    Object.assign(journal, (await client.get('journal?limit=200')) || {})
    const logData = await client.get('logs?lines=200')
    logs.value = (logData?.lines || []).join('\n') || '暂无日志'
  } catch (error) {
    logs.value = '加载失败：' + (error?.message || error)
  } finally {
    loading.value = false
  }
}

async function runCleanup(dryRun) {
  cleanupLoading.value = true
  try {
    const payload = dryRun ? {} : { dry_run: false }
    Object.assign(cleanup, (await client.post(dryRun ? 'cleanup_preview' : 'cleanup_run', payload)) || {})
  } catch (error) {
    cleanup.message = '清理失败：' + (error?.message || error)
  } finally {
    cleanupLoading.value = false
  }
}

function onAction(payload) {
  emit('action', payload)
  loadAll()
}

onMounted(loadAll)
</script>