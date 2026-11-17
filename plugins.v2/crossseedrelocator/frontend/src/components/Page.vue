<template>
  <v-card flat>
    <v-card-title class="d-flex align-center flex-wrap">
      <v-icon class="mr-2">mdi-swap-horizontal-bold</v-icon>
      <span class="mr-3">CrossSeed辅种路径回迁</span>
      <v-chip size="small" :color="status.enabled ? 'success' : 'grey'" class="mr-2">{{ status.enabled ? '已启用' : '已停用' }}</v-chip>
      <v-chip v-if="status.running" size="small" color="info" class="mr-2">运行中：{{ status.progress?.phase || '处理中' }}</v-chip>
      <v-spacer />
      <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="loadStatus">刷新</v-btn>
    </v-card-title>

    <v-card-text>
      <v-alert v-if="!status.config?._cs_root_exists" type="warning" variant="tonal" density="compact" class="mb-4">
        链接目录 {{ status.config?.cs_root }} 当前不可访问：如果容器没有挂载该目录，清理会跳过。
      </v-alert>

      <v-row dense class="mb-2">
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="primary" class="pa-3">
            <div class="text-caption">待处理（上次预演）</div>
            <div class="text-h5">{{ stats.ready || 0 }}</div>
            <div class="text-caption">共 {{ stats.targets || 0 }} 个在链接目录下</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="secondary" class="pa-3">
            <div class="text-caption">无源保留</div>
            <div class="text-h5">{{ stats.no_source || 0 }}</div>
            <div class="text-caption">季包/源已删除</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="success" class="pa-3">
            <div class="text-caption">历史已回迁</div>
            <div class="text-h5">{{ status.success_count || 0 }}</div>
            <div class="text-caption">累计成功</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card variant="tonal" color="error" class="pa-3">
            <div class="text-caption">失败</div>
            <div class="text-h5">{{ status.failed_count || 0 }}</div>
            <div class="text-caption">可单独回滚</div>
          </v-card>
        </v-col>
      </v-row>

      <div class="d-flex flex-wrap ga-2 my-3">
        <v-btn color="primary" variant="flat" :loading="previewing" prepend-icon="mdi-eye" @click="preview">预演一轮</v-btn>
        <v-btn color="warning" variant="flat" :loading="running" prepend-icon="mdi-play" @click="runApply"
          :disabled="status.running">实际执行本轮</v-btn>
        <v-btn variant="outlined" prepend-icon="mdi-undo" :loading="rollbacking" @click="rollbackAll">回滚全部</v-btn>
        <v-btn variant="text" prepend-icon="mdi-lan-connect" :loading="testing" @click="testConn">测试连接</v-btn>
      </div>

      <v-alert v-if="message" :type="messageType" variant="tonal" density="compact" class="mb-4">{{ message }}</v-alert>

      <div class="d-flex align-center mb-2">
        <div class="text-subtitle-1">预演结果</div>
        <v-spacer />
        <div class="text-caption text-medium-emphasis">文件系统校验：{{ plan.fs_checked ? '已校验文件存在' : '未校验（容器看不到该目录）' }}</div>
      </div>
      <v-table density="compact" fixed-header height="360" v-if="plan.items?.length">
        <thead>
          <tr>
            <th>状态</th>
            <th>ID</th>
            <th>名称</th>
            <th>体积</th>
            <th>当前路径</th>
            <th>目标路径</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in plan.items" :key="item.id">
            <td><v-chip size="x-small" :color="statusColor(item.status)" variant="flat">{{ statusText(item.status) }}</v-chip></td>
            <td>{{ item.id }}</td>
            <td class="text-truncate" style="max-width: 240px">{{ item.name }}</td>
            <td>{{ formatSize(item.size) }}</td>
            <td class="text-truncate" style="max-width: 220px">{{ item.current_dir }}</td>
            <td class="text-truncate" style="max-width: 220px">{{ item.target_dir || '-' }}</td>
            <td class="text-truncate" style="max-width: 200px">{{ item.reason || '-' }}</td>
          </tr>
        </tbody>
      </v-table>
      <v-alert v-else type="success" variant="tonal" density="compact">没有需要处理的种子（链接目录下没有待回迁种子）。</v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { usePluginApi, formatSize } from '../api'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
})
const emit = defineEmits(['action', 'switch', 'close'])
const client = usePluginApi(props)

const loading = ref(false)
const previewing = ref(false)
const running = ref(false)
const rollbacking = ref(false)
const testing = ref(false)
const message = ref('')
const messageType = ref('info')
const status = reactive({ config: {}, stats: {}, progress: {} })
const plan = reactive({ items: [], stats: {}, fs_checked: false })
const stats = reactive({})

function toast(text, type = 'info') {
  message.value = text
  messageType.value = type
}

function statusColor(value) {
  return { ready: 'primary', no_source: 'secondary', waiting: 'warning', success: 'success', failed: 'error' }[value] || 'grey'
}
function statusText(value) {
  return { ready: '可回迁', no_source: '无源保留', waiting: '等待', success: '成功', failed: '失败' }[value] || value
}

async function loadStatus() {
  loading.value = true
  try {
    const data = await client.get('status')
    Object.assign(status, data || {})
    Object.assign(stats, data?.stats || {})
    if (data?.plan_items?.length) {
      plan.items = data.plan_items
      plan.fs_checked = Boolean(data?.last_result?.fs_checked)
    }
  } catch (error) {
    toast('读取状态失败：' + (error?.message || error), 'error')
  } finally {
    loading.value = false
  }
}

async function preview() {
  previewing.value = true
  plan.items = []
  try {
    const data = await client.post('preview', {})
    plan.items = data?.items || []
    plan.fs_checked = Boolean(data?.fs_checked)
    Object.assign(stats, data?.stats || {})
    toast('预演完成：可回迁 ' + (plan.stats?.ready || 0) + ' 个，无源 ' + (plan.stats?.no_source || 0) + ' 个', 'success')
  } catch (error) {
    toast('预演失败：' + (error?.message || error), 'error')
  } finally {
    previewing.value = false
  }
}

async function runApply() {
  running.value = true
  try {
    const data = await client.post('run', { mode: 'apply' })
    toast(data?.message || '已提交执行任务，可在运行明细中查看进度', 'info')
    emit('action', { action: 'run' })
    setTimeout(loadStatus, 2000)
  } catch (error) {
    toast('执行失败：' + (error?.message || error), 'error')
  } finally {
    running.value = false
  }
}

async function rollbackAll() {
  rollbacking.value = true
  try {
    const data = await client.post('rollback', { all: true })
    toast(data?.message || '已提交回滚任务', 'warning')
  } catch (error) {
    toast('回滚失败：' + (error?.message || error), 'error')
  } finally {
    rollbacking.value = false
  }
}

async function testConn() {
  testing.value = true
  try {
    const data = await client.post('test', {})
    const info = data?.info || {}
    toast('连接成功：' + (info.version || data?.client || 'Transmission') + ' / ' + (info.torrent_count ?? '-') + ' 个种子', 'success')
  } catch (error) {
    toast('连接失败：' + (error?.message || error), 'error')
  } finally {
    testing.value = false
  }
}

onMounted(loadStatus)
</script>
