import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { a as formatSize, u as usePluginApi } from './api-Bew_unR_.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref} = await importShared('vue');


const _hoisted_1 = { class: "text-h5" };
const _hoisted_2 = { class: "text-caption" };
const _hoisted_3 = { class: "text-h5" };
const _hoisted_4 = { class: "text-h5" };
const _hoisted_5 = { class: "text-h5" };
const _hoisted_6 = { class: "d-flex flex-wrap ga-2 my-3" };
const _hoisted_7 = { class: "d-flex align-center mb-2" };
const _hoisted_8 = { class: "text-caption text-medium-emphasis" };
const _hoisted_9 = {
  class: "text-truncate",
  style: {"max-width":"240px"}
};
const _hoisted_10 = {
  class: "text-truncate",
  style: {"max-width":"220px"}
};
const _hoisted_11 = {
  class: "text-truncate",
  style: {"max-width":"220px"}
};
const _hoisted_12 = {
  class: "text-truncate",
  style: {"max-width":"200px"}
};

const {onMounted,reactive,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Page',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['action', 'switch', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const client = usePluginApi(props);

const loading = ref(false);
const previewing = ref(false);
const running = ref(false);
const rollbacking = ref(false);
const testing = ref(false);
const message = ref('');
const messageType = ref('info');
const status = reactive({ config: {}, stats: {}, progress: {} });
const plan = reactive({ items: [], stats: {}, fs_checked: false });
const stats = reactive({});

function toast(text, type = 'info') {
  message.value = text;
  messageType.value = type;
}

function statusColor(value) {
  return { ready: 'primary', no_source: 'secondary', waiting: 'warning', success: 'success', failed: 'error' }[value] || 'grey'
}
function statusText(value) {
  return { ready: '可回迁', no_source: '无源保留', waiting: '等待', success: '成功', failed: '失败' }[value] || value
}

async function loadStatus() {
  loading.value = true;
  try {
    const data = await client.get('status');
    Object.assign(status, data || {});
    Object.assign(stats, data?.stats || {});
    if (data?.plan_items?.length) {
      plan.items = data.plan_items;
      plan.fs_checked = Boolean(data?.last_result?.fs_checked);
    }
  } catch (error) {
    toast('读取状态失败：' + (error?.message || error), 'error');
  } finally {
    loading.value = false;
  }
}

async function preview() {
  previewing.value = true;
  plan.items = [];
  try {
    const data = await client.post('preview', {});
    plan.items = data?.items || [];
    plan.fs_checked = Boolean(data?.fs_checked);
    Object.assign(stats, data?.stats || {});
    toast('预演完成：可回迁 ' + (plan.stats?.ready || 0) + ' 个，无源 ' + (plan.stats?.no_source || 0) + ' 个', 'success');
  } catch (error) {
    toast('预演失败：' + (error?.message || error), 'error');
  } finally {
    previewing.value = false;
  }
}

async function runApply() {
  running.value = true;
  try {
    const data = await client.post('run', { mode: 'apply' });
    toast(data?.message || '已提交执行任务，可在运行明细中查看进度', 'info');
    emit('action', { action: 'run' });
    setTimeout(loadStatus, 2000);
  } catch (error) {
    toast('执行失败：' + (error?.message || error), 'error');
  } finally {
    running.value = false;
  }
}

async function rollbackAll() {
  rollbacking.value = true;
  try {
    const data = await client.post('rollback', { all: true });
    toast(data?.message || '已提交回滚任务', 'warning');
  } catch (error) {
    toast('回滚失败：' + (error?.message || error), 'error');
  } finally {
    rollbacking.value = false;
  }
}

async function testConn() {
  testing.value = true;
  try {
    const data = await client.post('test', {});
    const info = data?.info || {};
    toast('连接成功：' + (info.version || data?.client || 'Transmission') + ' / ' + (info.torrent_count ?? '-') + ' 个种子', 'success');
  } catch (error) {
    toast('连接失败：' + (error?.message || error), 'error');
  } finally {
    testing.value = false;
  }
}

onMounted(loadStatus);

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_table = _resolveComponent("v-table");
  const _component_v_card_text = _resolveComponent("v-card-text");

  return (_openBlock(), _createBlock(_component_v_card, { flat: "" }, {
    default: _withCtx(() => [
      _createVNode(_component_v_card_title, { class: "d-flex align-center flex-wrap" }, {
        default: _withCtx(() => [
          _createVNode(_component_v_icon, { class: "mr-2" }, {
            default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
              _createTextVNode("mdi-swap-horizontal-bold", -1)
            ]))]),
            _: 1
          }),
          _cache[2] || (_cache[2] = _createElementVNode("span", { class: "mr-3" }, "CrossSeed辅种路径回迁", -1)),
          _createVNode(_component_v_chip, {
            size: "small",
            color: status.enabled ? 'success' : 'grey',
            class: "mr-2"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(status.enabled ? '已启用' : '已停用'), 1)
            ]),
            _: 1
          }, 8, ["color"]),
          (status.running)
            ? (_openBlock(), _createBlock(_component_v_chip, {
                key: 0,
                size: "small",
                color: "info",
                class: "mr-2"
              }, {
                default: _withCtx(() => [
                  _createTextVNode("运行中：" + _toDisplayString(status.progress?.phase || '处理中'), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_v_spacer),
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-refresh",
            loading: loading.value,
            onClick: loadStatus
          }, {
            default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          }, 8, ["loading"])
        ]),
        _: 1
      }),
      _createVNode(_component_v_card_text, null, {
        default: _withCtx(() => [
          (!status.config?._cs_root_exists)
            ? (_openBlock(), _createBlock(_component_v_alert, {
                key: 0,
                type: "warning",
                variant: "tonal",
                density: "compact",
                class: "mb-4"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 链接目录 " + _toDisplayString(status.config?.cs_root) + " 当前不可访问：如果容器没有挂载该目录，清理会跳过。 ", 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_v_row, {
            dense: "",
            class: "mb-2"
          }, {
            default: _withCtx(() => [
              _createVNode(_component_v_col, {
                cols: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    color: "primary",
                    class: "pa-3"
                  }, {
                    default: _withCtx(() => [
                      _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-caption" }, "待处理（上次预演）", -1)),
                      _createElementVNode("div", _hoisted_1, _toDisplayString(stats.ready || 0), 1),
                      _createElementVNode("div", _hoisted_2, "共 " + _toDisplayString(stats.targets || 0) + " 个在链接目录下", 1)
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    color: "secondary",
                    class: "pa-3"
                  }, {
                    default: _withCtx(() => [
                      _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-caption" }, "无源保留", -1)),
                      _createElementVNode("div", _hoisted_3, _toDisplayString(stats.no_source || 0), 1),
                      _cache[5] || (_cache[5] = _createElementVNode("div", { class: "text-caption" }, "季包/源已删除", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    color: "success",
                    class: "pa-3"
                  }, {
                    default: _withCtx(() => [
                      _cache[6] || (_cache[6] = _createElementVNode("div", { class: "text-caption" }, "历史已回迁", -1)),
                      _createElementVNode("div", _hoisted_4, _toDisplayString(status.success_count || 0), 1),
                      _cache[7] || (_cache[7] = _createElementVNode("div", { class: "text-caption" }, "累计成功", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              }),
              _createVNode(_component_v_col, {
                cols: "6",
                md: "3"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_v_card, {
                    variant: "tonal",
                    color: "error",
                    class: "pa-3"
                  }, {
                    default: _withCtx(() => [
                      _cache[8] || (_cache[8] = _createElementVNode("div", { class: "text-caption" }, "失败", -1)),
                      _createElementVNode("div", _hoisted_5, _toDisplayString(status.failed_count || 0), 1),
                      _cache[9] || (_cache[9] = _createElementVNode("div", { class: "text-caption" }, "可单独回滚", -1))
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            _: 1
          }),
          _createElementVNode("div", _hoisted_6, [
            _createVNode(_component_v_btn, {
              color: "primary",
              variant: "flat",
              loading: previewing.value,
              "prepend-icon": "mdi-eye",
              onClick: preview
            }, {
              default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
                _createTextVNode("预演一轮", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_btn, {
              color: "warning",
              variant: "flat",
              loading: running.value,
              "prepend-icon": "mdi-play",
              onClick: runApply,
              disabled: status.running
            }, {
              default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                _createTextVNode("实际执行本轮", -1)
              ]))]),
              _: 1
            }, 8, ["loading", "disabled"]),
            _createVNode(_component_v_btn, {
              variant: "outlined",
              "prepend-icon": "mdi-undo",
              loading: rollbacking.value,
              onClick: rollbackAll
            }, {
              default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
                _createTextVNode("回滚全部", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_btn, {
              variant: "text",
              "prepend-icon": "mdi-lan-connect",
              loading: testing.value,
              onClick: testConn
            }, {
              default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
                _createTextVNode("测试连接", -1)
              ]))]),
              _: 1
            }, 8, ["loading"])
          ]),
          (message.value)
            ? (_openBlock(), _createBlock(_component_v_alert, {
                key: 1,
                type: messageType.value,
                variant: "tonal",
                density: "compact",
                class: "mb-4"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(message.value), 1)
                ]),
                _: 1
              }, 8, ["type"]))
            : _createCommentVNode("", true),
          _createElementVNode("div", _hoisted_7, [
            _cache[14] || (_cache[14] = _createElementVNode("div", { class: "text-subtitle-1" }, "预演结果", -1)),
            _createVNode(_component_v_spacer),
            _createElementVNode("div", _hoisted_8, "文件系统校验：" + _toDisplayString(plan.fs_checked ? '已校验文件存在' : '未校验（容器看不到该目录）'), 1)
          ]),
          (plan.items?.length)
            ? (_openBlock(), _createBlock(_component_v_table, {
                key: 2,
                density: "compact",
                "fixed-header": "",
                height: "360"
              }, {
                default: _withCtx(() => [
                  _cache[15] || (_cache[15] = _createElementVNode("thead", null, [
                    _createElementVNode("tr", null, [
                      _createElementVNode("th", null, "状态"),
                      _createElementVNode("th", null, "ID"),
                      _createElementVNode("th", null, "名称"),
                      _createElementVNode("th", null, "体积"),
                      _createElementVNode("th", null, "当前路径"),
                      _createElementVNode("th", null, "目标路径"),
                      _createElementVNode("th", null, "原因")
                    ])
                  ], -1)),
                  _createElementVNode("tbody", null, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(plan.items, (item) => {
                      return (_openBlock(), _createElementBlock("tr", {
                        key: item.id
                      }, [
                        _createElementVNode("td", null, [
                          _createVNode(_component_v_chip, {
                            size: "x-small",
                            color: statusColor(item.status),
                            variant: "flat"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(statusText(item.status)), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        _createElementVNode("td", null, _toDisplayString(item.id), 1),
                        _createElementVNode("td", _hoisted_9, _toDisplayString(item.name), 1),
                        _createElementVNode("td", null, _toDisplayString(_unref(formatSize)(item.size)), 1),
                        _createElementVNode("td", _hoisted_10, _toDisplayString(item.current_dir), 1),
                        _createElementVNode("td", _hoisted_11, _toDisplayString(item.target_dir || '-'), 1),
                        _createElementVNode("td", _hoisted_12, _toDisplayString(item.reason || '-'), 1)
                      ]))
                    }), 128))
                  ])
                ]),
                _: 1
              }))
            : (_openBlock(), _createBlock(_component_v_alert, {
                key: 3,
                type: "success",
                variant: "tonal",
                density: "compact"
              }, {
                default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                  _createTextVNode("没有需要处理的种子（链接目录下没有待回迁种子）。", -1)
                ]))]),
                _: 1
              }))
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
