<template>
  <v-card flat>
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-swap-horizontal-bold</v-icon>
      {{ pluginName }}
      <v-spacer />
      <v-chip size="small" :color="config.enabled ? 'success' : 'grey'" variant="flat">
        {{ config.enabled ? '已启用' : '已停用' }}
      </v-chip>
    </v-card-title>
    <v-card-subtitle>自动把 cross-seed 注入的种子改回原始保存路径，并清理不再做种的链接文件。</v-card-subtitle>

    <v-card-text>
      <v-row dense>
        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">执行计划</div>
            <v-switch v-model="config.enabled" label="启用定时任务" density="compact" hide-details color="primary" />
            <v-text-field v-model="config.cron" label="cron 表达式（5 段）" density="compact" class="mt-2"
              hint="默认 0 3 */7 * *：每月 1/8/15/22/29 日 03:00" persistent-hint />
            <v-select v-model="config.apply_mode" :items="applyModes" item-title="title" item-value="value"
              label="定时任务动作" density="compact" class="mt-2"
              hint="仅预演只出报告不动数据；实际执行才会改路径/去标签" persistent-hint />
            <v-text-field v-model="config.single_timeout_min" type="number" label="单种子校验超时（分钟）"
              density="compact" class="mt-2" hide-details />
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">单轮上限（0 表示不限制）</div>
            <v-text-field v-model.number="config.cap_count" type="number" label="最多处理种子数" density="compact" hide-details />
            <v-text-field v-model.number="config.cap_size_gb" type="number" label="最多处理体积（GB）" density="compact" class="mt-2" hide-details />
            <v-text-field v-model.number="config.cap_minutes" type="number" label="单轮最长运行（分钟）" density="compact" class="mt-2" hide-details />
            <v-alert type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              改路径会触发重新校验，日注入量通常只有个位数；如担心 IO 高峰，可设数量/体积/时长上限。
            </v-alert>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">路径规则</div>
            <v-text-field v-model="config.cs_root" label="cross-seed 链接根目录" density="compact" hide-details />
            <v-textarea v-model="config.path_priority" label="目标路径优先级（每行一个，自上而下）" rows="3"
              density="compact" class="mt-2" />
            <v-textarea v-model="config.path_exclude" label="排除目录（每行一个，绝不作为目标）" rows="2"
              density="compact" />
            <v-switch v-model="config.keep_label_on_no_source" label="无源时保留 cross-seed 标签（标记为 CS 专属数据）"
              density="compact" hide-details color="primary" />
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">链接目录清理</div>
            <v-switch v-model="config.cleanup_enabled" label="随定时任务清理链接目录" density="compact" hide-details color="primary" />
            <v-switch v-model="config.cleanup_dry_run" label="只预演不删除" density="compact" hide-details color="primary" class="mt-1" />
            <v-text-field v-model.number="config.cleanup_min_age_hours" type="number" label="跳过最近 N 小时内修改的文件"
              density="compact" hide-details class="mt-2" />
            <v-alert type="warning" variant="tonal" density="compact" class="mt-3 text-caption">
              只删除「不被任何做种种子引用」的文件；预演结果可在「运行明细」页查看。
            </v-alert>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">通知</div>
            <v-switch v-model="config.notify_success" label="有回迁成功时通知" density="compact" hide-details color="primary" />
            <v-switch v-model="config.notify_failure" label="有失败时通知" density="compact" hide-details color="primary" />
            <v-switch v-model="config.notify_rollback" label="有回滚时通知" density="compact" hide-details color="primary" />
            <v-alert type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              走 MoviePilot 自带通知渠道；没有对应事件时不会推送。
            </v-alert>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="pa-3 h-100">
            <div class="text-subtitle-2 mb-2">下载器</div>
            <v-text-field v-model="config.tr_name" label="Transmission 配置名（留空自动选择）" density="compact" hide-details />
            <v-alert type="info" variant="tonal" density="compact" class="mt-3 text-caption">
              复用 MoviePilot 中已配置的 Transmission，无需重复填地址与密码。
            </v-alert>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-actions>
      <v-btn color="primary" variant="flat" :loading="saving" @click="save">保存</v-btn>
      <v-btn variant="text" @click="$emit('close')">关闭</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close', 'switch'])

const pluginName = computed(() => 'CrossSeed辅种路径回迁')
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
  single_timeout_min: 30,
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

function save() {
  saving.value = true
  const payload = { ...config }
  payload.cap_count = Number(payload.cap_count) || 0
  payload.cap_size_gb = Number(payload.cap_size_gb) || 0
  payload.cap_minutes = Number(payload.cap_minutes) || 0
  payload.single_timeout_min = Number(payload.single_timeout_min) || 30
  payload.cleanup_min_age_hours = Number(payload.cleanup_min_age_hours) || 12
  emit('save', payload)
  setTimeout(() => (saving.value = false), 800)
}
</script>
