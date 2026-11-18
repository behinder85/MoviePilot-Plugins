import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as usePluginApi } from './api-Bew_unR_.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "d-flex align-center mb-3" };

const {computed,onMounted,reactive,ref,watch} = await importShared('vue');

const VERSION = '1.1.1';

const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  initialConfig: { type: Object, default: () => ({}) },
},
  emits: ['save', 'close', 'switch'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;

const client = usePluginApi(props);
const pluginName = computed(() => 'CrossSeed辅种路径回迁');
const saving = ref(false);
const applyModes = [
  { title: '仅预演（只出报告）', value: 'preview' },
  { title: '实际执行', value: 'apply' },
];
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
};

const config = reactive({ ...defaults, ...(props.initialConfig || {}) });
watch(
  () => props.initialConfig,
  value => Object.assign(config, defaults, value || {}),
  { deep: true }
);

// ---------------- 下载器列表（读取 MoviePilot 已配置的下载器） ----------------
const loadingDownloaders = ref(false);
const downloaders = ref([]);
const downloaderError = ref('');

const downloaderOptions = computed(() => {
  const items = [{ value: '', title: '自动选择（第一个启用的 Transmission）', disabled: false, subtitle: '' }];
  for (const item of downloaders.value) {
    const suffix = [];
    if (item.type && item.enabled) suffix.push(item.type);
    if (!item.enabled) suffix.push('未启用');
    items.push({
      value: item.name,
      title: suffix.length ? item.name + '（' + suffix.join('，') + '）' : item.name,
      disabled: item.type !== 'transmission' || !item.enabled,
      subtitle: item.host ? item.host + (item.port ? ':' + item.port : '') : '',
    });
  }
  return items
});

function itemProps(item) {
  return { disabled: item.disabled, subtitle: item.subtitle }
}

async function loadDownloaders() {
  loadingDownloaders.value = true;
  downloaderError.value = '';
  try {
    const data = await client.get('downloaders');
    const items = (data && data.items) || [];
    downloaders.value = items.filter(item => item.type === 'transmission');
    if (!data || data.ok === false) {
      downloaderError.value = (data && data.message) || '读取下载器失败';
    } else if (!downloaders.value.length) {
      downloaderError.value = 'MoviePilot 里还没有配置 Transmission 下载器，请先到「设置 → 下载器」添加。';
    }
  } catch (error) {
    downloaderError.value = '读取下载器失败：' + ((error && error.message) || error);
  } finally {
    loadingDownloaders.value = false;
  }
}

onMounted(loadDownloaders);

function save() {
  saving.value = true;
  const payload = { ...config };
  payload.cap_count = Number(payload.cap_count) || 0;
  payload.cap_size_gb = Number(payload.cap_size_gb) || 0;
  payload.cap_minutes = Number(payload.cap_minutes) || 0;
  payload.single_timeout_min = Number(payload.single_timeout_min) || 60;
  payload.cleanup_min_age_hours = Number(payload.cleanup_min_age_hours) || 12;
  payload.tr_name = String(payload.tr_name || '').trim();
  emit('save', payload);
  setTimeout(() => (saving.value = false), 800);
}

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_card_subtitle = _resolveComponent("v-card-subtitle");
  const _component_v_switch = _resolveComponent("v-switch");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_textarea = _resolveComponent("v-textarea");
  const _component_v_divider = _resolveComponent("v-divider");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card_actions = _resolveComponent("v-card-actions");

  return (_openBlock(), _createBlock(_component_v_card, { flat: "" }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
        default: _withCtx(() => [
          _createVNode(_component_v_icon, { class: "mr-2" }, {
            default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
              _createTextVNode("mdi-swap-horizontal-bold", -1)
            ]))]),
            _: 1
          }),
          _createTextVNode(" " + _toDisplayString(pluginName.value) + " ", 1),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_chip, {
            size: "small",
            variant: "tonal",
            class: "ml-2"
          }, {
            default: _withCtx(() => [
              _createTextVNode("v" + _toDisplayString(VERSION))
            ]),
            _: 1
          }),
          _createVNode(_component_v_chip, {
            size: "small",
            color: config.enabled ? 'success' : 'grey',
            variant: "flat",
            class: "ml-2"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(config.enabled ? '已启用' : '已停用'), 1)
            ]),
            _: 1
          }, 8, ["color"])
        ]),
        _: 1
      }),
      _createVNode(_component_v_card_subtitle, null, {
        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
          _createTextVNode("自动把 cross-seed 注入的种子改回原始保存路径，并清理不再做种的链接文件。", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_v_card_text, null, {
        default: _withCtx(() => [
          _createVNode(_component_v_row, { dense: "" }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                md: "6"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4 h-100"
                  }, {
                    default: _withCtx(() => [
                      _cache[21] || (_cache[21] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "执行计划", -1)),
                      _createVNode(_component_v_switch, {
                        modelValue: config.enabled,
                        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((config.enabled) = $event)),
                        label: "启用定时任务",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cron,
                        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((config.cron) = $event)),
                        label: "cron 表达式（5 段）",
                        density: "compact",
                        class: "mt-3",
                        hint: "默认 0 3 */7 * *：每月 1/8/15/22/29 日 03:00",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_select, {
                        modelValue: config.apply_mode,
                        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((config.apply_mode) = $event)),
                        items: applyModes,
                        "item-title": "title",
                        "item-value": "value",
                        label: "定时任务动作",
                        density: "compact",
                        class: "mt-3",
                        hint: "仅预演只出报告不动数据；实际执行才会改路径/去标签",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.single_timeout_min,
                        "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((config.single_timeout_min) = $event)),
                        modelModifiers: { number: true },
                        type: "number",
                        label: "单种子校验超时（分钟）",
                        density: "compact",
                        class: "mt-3",
                        hint: "改路径后 TR 会重新校验该种子，这里是等待单个种子校验完成并恢复做种的最长时间。太小会让大种子被误判失败并回滚；太大则卡住的种子会拖长整轮（可用单轮上限兜底）。建议 30~120。",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                md: "6"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4 h-100"
                  }, {
                    default: _withCtx(() => [
                      _createElementVNode("div", _hoisted_1, [
                        _cache[23] || (_cache[23] = _createElementVNode("div", { class: "text-subtitle-2" }, "下载器", -1)),
                        _createVNode(_component_v_spacer),
                        _createVNode(_component_v_btn, {
                          size: "x-small",
                          variant: "text",
                          "prepend-icon": "mdi-refresh",
                          loading: loadingDownloaders.value,
                          onClick: loadDownloaders
                        }, {
                          default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                            _createTextVNode(" 刷新列表 ", -1)
                          ]))]),
                          _: 1
                        }, 8, ["loading"])
                      ]),
                      _createVNode(_component_v_select, {
                        modelValue: config.tr_name,
                        "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((config.tr_name) = $event)),
                        items: downloaderOptions.value,
                        "item-title": "title",
                        "item-value": "value",
                        "item-props": itemProps,
                        loading: loadingDownloaders.value,
                        clearable: "",
                        density: "compact",
                        label: "Transmission 下载器",
                        "no-data-text": downloaderError.value || '未读取到已配置的下载器',
                        hint: "直接复用 MoviePilot「设置 → 下载器」里已配好的 Transmission，无需重复填地址与密码。",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue", "items", "loading", "no-data-text"]),
                      (downloaderError.value)
                        ? (_openBlock(), _createBlock(_component_v_alert, {
                            key: 0,
                            type: "warning",
                            variant: "tonal",
                            density: "compact",
                            class: "mt-3 text-caption"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(downloaderError.value), 1)
                            ]),
                            _: 1
                          }))
                        : (_openBlock(), _createBlock(_component_v_alert, {
                            key: 1,
                            type: "info",
                            variant: "tonal",
                            density: "compact",
                            class: "mt-3 text-caption"
                          }, {
                            default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
                              _createTextVNode(" 只列出类型为 transmission 的下载器；留空则自动使用第一个启用的 Transmission。 ", -1)
                            ]))]),
                            _: 1
                          }))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_v_row, {
            dense: "",
            class: "mt-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, { cols: "12" }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4"
                  }, {
                    default: _withCtx(() => [
                      _cache[25] || (_cache[25] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "路径规则", -1)),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cs_root,
                        "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((config.cs_root) = $event)),
                        label: "cross-seed 链接根目录",
                        density: "compact",
                        hint: "Transmission 中 downloadDir 落在这个目录下的种子才会被当作待回迁对象",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_textarea, {
                        modelValue: config.path_priority,
                        "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((config.path_priority) = $event)),
                        label: "目标路径优先级（每行一个，自上而下）",
                        rows: "4",
                        "auto-grow": "",
                        density: "compact",
                        class: "mt-6",
                        hint: "回迁目标必须落在这些前缀下；越靠前优先级越高",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_textarea, {
                        modelValue: config.path_exclude,
                        "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((config.path_exclude) = $event)),
                        label: "排除目录（每行一个，绝不作为目标）",
                        rows: "4",
                        "auto-grow": "",
                        density: "compact",
                        class: "mt-6",
                        hint: "例如刷流目录：源种子保存路径命中这些前缀时不会被选为目标",
                        "persistent-hint": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_divider, { class: "my-4" }),
                      _createVNode(_component_v_switch, {
                        modelValue: config.keep_label_on_no_source,
                        "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((config.keep_label_on_no_source) = $event)),
                        label: "无源时保留 cross-seed 标签（标记为 CS 专属数据）",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createVNode(_component_v_row, {
            dense: "",
            class: "mt-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "12",
                md: "4"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4 h-100"
                  }, {
                    default: _withCtx(() => [
                      _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "单轮上限（0 表示不限制）", -1)),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cap_count,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((config.cap_count) = $event)),
                        modelModifiers: { number: true },
                        type: "number",
                        label: "最多处理种子数",
                        density: "compact",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cap_size_gb,
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((config.cap_size_gb) = $event)),
                        modelModifiers: { number: true },
                        type: "number",
                        label: "最多处理体积（GB）",
                        density: "compact",
                        class: "mt-3",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cap_minutes,
                        "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((config.cap_minutes) = $event)),
                        modelModifiers: { number: true },
                        type: "number",
                        label: "单轮最长运行（分钟）",
                        density: "compact",
                        class: "mt-3",
                        "hide-details": ""
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_alert, {
                        type: "info",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-3 text-caption"
                      }, {
                        default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
                          _createTextVNode(" 改路径会触发重新校验，日注入量通常只有个位数；担心 IO 高峰时可用这三项兜底。 ", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                md: "4"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4 h-100"
                  }, {
                    default: _withCtx(() => [
                      _cache[29] || (_cache[29] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "链接目录清理", -1)),
                      _createVNode(_component_v_switch, {
                        modelValue: config.cleanup_enabled,
                        "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((config.cleanup_enabled) = $event)),
                        label: "随定时任务清理链接目录",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_switch, {
                        modelValue: config.cleanup_dry_run,
                        "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((config.cleanup_dry_run) = $event)),
                        label: "只预演不删除",
                        density: "compact",
                        "hide-details": "",
                        color: "primary",
                        class: "mt-1"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_text_field, {
                        modelValue: config.cleanup_min_age_hours,
                        "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((config.cleanup_min_age_hours) = $event)),
                        modelModifiers: { number: true },
                        type: "number",
                        label: "跳过最近 N 小时内修改的文件",
                        density: "compact",
                        "hide-details": "",
                        class: "mt-3"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_alert, {
                        type: "warning",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-3 text-caption"
                      }, {
                        default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                          _createTextVNode(" 只删除「不被任何做种种子引用」的文件；预演结果可在「运行明细」页查看。 ", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "12",
                md: "4"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "outlined",
                    class: "pa-4 h-100"
                  }, {
                    default: _withCtx(() => [
                      _cache[31] || (_cache[31] = _createElementVNode("div", { class: "text-subtitle-2 mb-3" }, "通知", -1)),
                      _createVNode(_component_v_switch, {
                        modelValue: config.notify_success,
                        "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((config.notify_success) = $event)),
                        label: "有回迁成功时通知",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_switch, {
                        modelValue: config.notify_failure,
                        "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((config.notify_failure) = $event)),
                        label: "有失败时通知",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_switch, {
                        modelValue: config.notify_rollback,
                        "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((config.notify_rollback) = $event)),
                        label: "有回滚时通知",
                        density: "compact",
                        "hide-details": "",
                        color: "primary"
                      }, null, 8, ["modelValue"]),
                      _createVNode(_component_v_alert, {
                        type: "info",
                        variant: "tonal",
                        density: "compact",
                        class: "mt-3 text-caption"
                      }, {
                        default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                          _createTextVNode(" 走 MoviePilot 自带通知渠道；没有对应事件时不会推送。 ", -1)
                        ]))]),
                        _: 1
                      })
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createElementVNode("div", { class: "text-caption text-medium-emphasis mt-3" }, " 前端版本 v" + _toDisplayString(VERSION) + "。若此处版本号与插件版本不一致，说明浏览器缓存了旧前端，请按 Ctrl+F5 强制刷新。 ")
        ]),
        _: 1
      }),
      _createVNode(_component_v_card_actions, null, {
        default: _withCtx(() => [
          _createVNode(_component_v_btn, {
            color: "primary",
            variant: "flat",
            loading: saving.value,
            onClick: save
          }, {
            default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
              _createTextVNode("保存", -1)
            ]))]),
            _: 1
          }, 8, ["loading"]),
          _createVNode(_component_v_btn, {
            variant: "text",
            onClick: _cache[18] || (_cache[18] = $event => (_ctx.$emit('close')))
          }, {
            default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
              _createTextVNode("关闭", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};

export { _sfc_main as default };
