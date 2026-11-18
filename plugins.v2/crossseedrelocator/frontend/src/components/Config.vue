<template>
  <v-card flat>
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-swap-horizontal-bold</v-icon>
      {{ pluginName }}
      <v-spacer />
      <v-chip size="small" variant="tonal" class="ml-2">v{{ VERSION }}</v-chip>
      <v-chip size="small" :color="config.enabled ? 'success' : 'grey'" variant="flat" class="ml-2">
        {{ config.enabled ? '已启用' : '已停用' }}
      </v-chip>
    </v-card-title>
    <v-card-subtitle>自动把 cross-seed 注入的种子改回原始保存路径，并清理不再做种的链接文件。</v-card-subtitle>

    <v-card-text>
      <v-row dense>
        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-4 h-100">
            <div class="text-subtitle-2 mb-3">执行计划</div>
            <v-switch v-model="config.enabled" label="启用定时任务" density="compact" hide-details color="primary" />
            <v-text-field v-model="config.cron" label="cron 表达式（5 段）" density="compact" class="mt-3"
              hint="默认 0 3 */7 * *：每月 1/8/15/22/29 日 03:00" persistent-hint />
            <v-select v-model="config.apply_mode" :items="applyModes" item-title="title" item-value="value"
              label="定时任务动作" density="compact" class="mt-3"
              hint="仅预演只出报告不动数据；实际执行才会改路径/去标签" persistent-hint />
            <v-text-field v-model.number="config.single_timeout_min" type="number" label="单种子校验超时（分钟）"
              density="compact" class="mt-3"
              hint="改路径后 TR 会重新校验该种子，这里是等待单个种子校验完成并恢复做种的最长时间。太小会让大种子被误判失败并回滚；太大则卡住的种子会拖长整轮（可用单轮上限兜底）。建议 30~120。"
              persistent-hint />
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-4 h-100">
            <div class="d-flex align-center mb-3">
              <div class="text-subtitle-2">下载器</div>
              <v-spacer />
              <v-btn size="x-small" variant="text" prepend-icon="mdi-refresh" :loading="loadingDownloaders" @click="loadDownloaders">
                刷新列表
              </v-btn>
            </div>
            <v-select v-model="config.tr_name" :items="downloaderOptions" item-title="title" item-value="value"
              :item-props="itemProps" :loading="loadingDownloaders" clearable density="compact"
              label="Transmission 下载器" :no-data-text="downloaderError || '未读取到已配置的下载器'"
              hint="直接复用 MoviePilot「设置 → 下载器」里已配好的 Transmission，无需重复填地址与密码。"
              persistent-hint />
            <v-alert v-if="downloaderError" type="warning" variant="tonal" density="compact" class="mt-3 text-caption">
              {{ downloaderError }}
            </v-alert>
            <v-alert v-else type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              只列出类型为 transmission 的下载器；留空则自动使用第一个启用的 Transmission。
            </v-alert>
          </v-card>
        </v-col>
      </v-row>

      <v-row dense class="mt-2">
        <v-col cols="12">
          <v-card variant="outlined" class="pa-4">
            <div class="text-subtitle-2 mb-3">路径规则</div>
            <v-text-field v-model="config.cs_root" label="cross-seed 链接根目录" density="compact"
              hint="Transmission 中 downloadDir 落在这个目录下的种子才会被当作待回迁对象"
              persistent-hint />
            <v-textarea v-model="config.path_priority" label="目标路径优先级（每行一个，自上而下）" rows="4" auto-grow
              density="compact" class="mt-6"
              hint="回迁目标必须落在这些前缀下；越靠前优先级越高" persistent-hint />
            <v-textarea v-model="config.path_exclude" label="排除目录（每行一个，绝不作为目标）" rows="4" auto-grow
              density="compact" class="mt-6"
              hint="例如刷流目录：源种子保存路径命中这些前缀时不会被选为目标" persistent-hint />
            <v-divider class="my-4" />
            <v-switch v-model="config.keep_label_on_no_source" label="无源时保留 cross-seed 标签（标记为 CS 专属数据）"
              density="compact" hide-details color="primary" />
          </v-card>
        </v-col>
      </v-row>

      <v-row dense class="mt-2">
        <v-col cols="12" md="4">
          <v-card variant="outlined" class="pa-4 h-100">
            <div class="text-subtitle-2 mb-3">单轮上限（0 表示不限制）</div>
            <v-text-field v-model.number="config.cap_count" type="number" label="最多处理种子数" density="compact" hide-details />
            <v-text-field v-model.number="config.cap_size_gb" type="number" label="最多处理体积（GB）" density="compact" class="mt-3" hide-details />
            <v-text-field v-model.number="config.cap_minutes" type="number" label="单轮最长运行（分钟）" density="compact" class="mt-3" hide-details />
            <v-alert type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              改路径会触发重新校验，日注入量通常只有个位数；担心 IO 高峰时可用这三项兜底。
            </v-alert>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card variant="outlined" class="pa-4 h-100">
            <div class="text-subtitle-2 mb-3">链接目录清理</div>
            <v-switch v-model="config.cleanup_enabled" label="随定时任务清理链接目录" density="compact" hide-details color="primary" />
            <v-switch v-model="config.cleanup_dry_run" label="只预演不删除" density="compact" hide-details color="primary" class="mt-1" />
            <v-text-field v-model.number="config.cleanup_min_age_hours" type="number" label="跳过最近 N 小时内修改的文件"
              density="compact" hide-details class="mt-3" />
            <v-alert type="warning" variant="tonal" density="compact" class="mt-3 text-caption">
              只删除「不被任何做种种子引用」的文件；预演结果可在「运行明细」页查看。
            </v-alert>
          </v-card>
        </v-col>

        <v-col cols="12" md="4">
          <v-card variant="outlined" class="pa-4 h-100">
            <div class="text-subtitle-2 mb-3">通知</div>
            <v-switch v-model="config.notify_success" label="有回迁成功时通知" density="compact" hide-details color="primary" />
            <v-switch v-model="config.notify_failure" label="有失败时通知" density="compact" hide-details color="primary" />
            <v-switch v-model="config.notify_rollback" label="有回滚时通知" density="compact" hide-details color="primary" />
            <v-alert type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              走 MoviePilot 自带通知渠道；没有对应事件时不会推送。
            </v-alert>
          </v-card>
        </v-col>
      </v-row>
      <div class="text-caption text-medium-emphasis mt-3">
        前端版本 v{{ VERSION }}。若此处版本号与插件版本不一致，说明浏览器缓存了旧前端，请按 Ctrl+F5 强制刷新。
      </div>
    </v-card-text>

    <v-card-actions>
      <v-btn color="primary" variant="flat" :loading="saving" @click="save">保存</v-btn>
      <v-btn variant="text" @click="$emit('close')">关闭</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { usePluginApi } from '../api'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const client = usePluginApi(props)
const pluginName = computed(() => 'CrossSeed辅种路径回迁')
const VERSION = '1.1.2'
const saving = ref(false)
const applyModes = [
  { title: '仅预演（只出报告）', value: 'preview' },
  { title: '实际执行', value: 'apply' },
]
const defaults = {
  enabled: true,
  cron: '0 3 */7 * *',
  cs_root: '/机械/Cross-Seed',
  apply_mode: 'preview',
  path_priority: '/机械/download\n/机械/不可说保种',
  path_exclude: '/机械/刷流',
  cap_count: 0,
  cap_size_gb: 0,
  cap_minutes: 0,
  single_timeout_min: 60,
  keep_label_on_no_source: true,
  cleanup_enabled: false,
  cleanup_dry_run: true,
  cleanup_min_age_hours: 12,
  notify_success: true,
  notify_failure: true,
  notify_rollback: true,
  tr_name: '',
}

const config = reactive({ ...defaults, ...(props.initialConfig || {}) })
watch(
  () => props.initialConfig,
  value => Object.assign(config, defaults, value || {}),
  { deep: true }
)

// ---------------- 下载器列表（读取 MoviePilot 已配置的下载器） ----------------
const loadingDownloaders = ref(false)
const downloaders = ref([])
const downloaderError = ref('')

const downloaderOptions = computed(() => {
  const items = [{ value: '', title: '自动选择（第一个启用的 Transmission）', disabled: false, subtitle: '' }]
  for (const item of downloaders.value) {
    const suffix = []
    if (item.type && item.enabled) suffix.push(item.type)
    if (!item.enabled) suffix.push('未启用')
    items.push({
      value: item.name,
      title: suffix.length ? item.name + '（' + suffix.join('，') + '）' : item.name,
      disabled: item.type !== 'transmission' || !item.enabled,
      subtitle: item.host ? item.host + (item.port ? ':' + item.port : '') : '',
    })
  }
  return items
})

function itemProps(item) {
  return { disabled: item.disabled, subtitle: item.subtitle }
}

async function loadDownloaders() {
  loadingDownloaders.value = true
  downloaderError.value = ''
  try {
    const data = await client.get('downloaders')
    const items = (data && data.items) || []
    downloaders.value = items.filter(item => item.type === 'transmission')
    if (!data || data.ok === false) {
      downloaderError.value = (data && data.message) || '读取下载器失败'
    } else if (!downloaders.value.length) {
      downloaderError.value = 'MoviePilot 里还没有配置 Transmission 下载器，请先到「设置 → 下载器」添加。'
    }
  } catch (error) {
    downloaderError.value = '读取下载器失败：' + ((error && error.message) || error)
  } finally {
    loadingDownloaders.value = false
  }
}

onMounted(loadDownloaders)

function save() {
  saving.value = true
  const payload = { ...config }
  payload.cap_count = Number(payload.cap_count) || 0
  payload.cap_size_gb = Number(payload.cap_size_gb) || 0
  payload.cap_minutes = Number(payload.cap_minutes) || 0
  payload.single_timeout_min = Number(payload.single_timeout_min) || 60
  payload.cleanup_min_age_hours = Number(payload.cleanup_min_age_hours) || 12
  payload.tr_name = String(payload.tr_name || '').trim()
  emit('save', payload)
  setTimeout(() => (saving.value = false), 800)
}
</script>