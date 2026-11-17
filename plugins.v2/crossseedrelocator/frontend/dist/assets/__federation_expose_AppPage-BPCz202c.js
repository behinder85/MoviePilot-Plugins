import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import _sfc_main$1 from './__federation_expose_Page-CEqzwq2y.js';
import { f as formatTime, a as formatSize, u as usePluginApi } from './api-Bew_unR_.js';

const {createVNode:_createVNode,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,unref:_unref,toDisplayString:_toDisplayString,createCommentVNode:_createCommentVNode,createBlock:_createBlock} = await importShared('vue');


const _hoisted_1 = { key: 0 };
const _hoisted_2 = {
  class: "text-truncate",
  style: {"max-width":"200px"}
};
const _hoisted_3 = {
  class: "text-truncate",
  style: {"max-width":"220px"}
};
const _hoisted_4 = {
  class: "text-truncate",
  style: {"max-width":"220px"}
};
const _hoisted_5 = { key: 0 };
const _hoisted_6 = {
  class: "text-truncate",
  style: {"max-width":"240px"}
};
const _hoisted_7 = {
  class: "text-truncate",
  style: {"max-width":"220px"}
};
const _hoisted_8 = { key: 0 };
const _hoisted_9 = { class: "d-flex flex-wrap ga-2 mb-3" };
const _hoisted_10 = { class: "text-h6" };
const _hoisted_11 = { class: "text-h6" };
const _hoisted_12 = { class: "text-h6" };
const _hoisted_13 = { class: "text-caption" };
const _hoisted_14 = { class: "text-h6" };
const _hoisted_15 = { class: "text-caption" };
const _hoisted_16 = { class: "text-caption" };
const _hoisted_17 = {
  class: "text-caption",
  style: {"white-space":"pre-wrap","color":"#e0e0e0"}
};

const {onMounted,reactive,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  navKey: { type: String, default: 'main' },
  nativeSubscribe: { type: Function, default: null },
},
  emits: ['action'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const client = usePluginApi(props);

const loading = ref(false);
const tab = ref('runs');
const journal = reactive({ runs: [], entries: [], no_source: [] });
const cleanup = reactive({ sample: [] });
const cleanupLoading = ref(false);
const logs = ref('加载中…');

function statusColor(value) {
  return { success: 'success', failed: 'error', relocating: 'info', rolled_back: 'warning', no_source: 'secondary' }[value] || 'grey'
}
function statusText(value) {
  return { success: '成功', failed: '失败', relocating: '处理中', rolled_back: '已回滚' }[value] || value
}

async function loadAll() {
  loading.value = true;
  try {
    Object.assign(journal, (await client.get('journal?limit=200')) || {});
    const logData = await client.get('logs?lines=200');
    logs.value = (logData?.lines || []).join('\n') || '暂无日志';
  } catch (error) {
    logs.value = '加载失败：' + (error?.message || error);
  } finally {
    loading.value = false;
  }
}

async function runCleanup(dryRun) {
  cleanupLoading.value = true;
  try {
    const payload = dryRun ? {} : { dry_run: false };
    Object.assign(cleanup, (await client.post(dryRun ? 'cleanup_preview' : 'cleanup_run', payload)) || {});
  } catch (error) {
    cleanup.message = '清理失败：' + (error?.message || error);
  } finally {
    cleanupLoading.value = false;
  }
}

function onAction(payload) {
  emit('action', payload);
  loadAll();
}

onMounted(loadAll);

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_tab = _resolveComponent("v-tab");
  const _component_v_tabs = _resolveComponent("v-tabs");
  const _component_v_table = _resolveComponent("v-table");
  const _component_v_window_item = _resolveComponent("v-window-item");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_sheet = _resolveComponent("v-sheet");
  const _component_v_window = _resolveComponent("v-window");
  const _component_v_card_text = _resolveComponent("v-card-text");

  return (_openBlock(), _createElementBlock("div", null, [
    _createVNode(_sfc_main$1, {
      api: __props.api,
      pluginId: __props.pluginId,
      sourcePluginId: __props.sourcePluginId,
      nativeSubscribe: __props.nativeSubscribe,
      onAction: onAction
    }, null, 8, ["api", "pluginId", "sourcePluginId", "nativeSubscribe"]),
    _createVNode(_component_v_card, {
      flat: "",
      class: "mt-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
          default: _withCtx(() => [
            _createVNode(_component_v_icon, { class: "mr-2" }, {
              default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
                _createTextVNode("mdi-history", -1)
              ]))]),
              _: 1
            }),
            _cache[6] || (_cache[6] = _createElementVNode("span", null, "运行明细与清理", -1)),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_btn, {
              size: "small",
              variant: "text",
              "prepend-icon": "mdi-refresh",
              loading: loading.value,
              onClick: loadAll
            }, {
              default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                _createTextVNode("刷新", -1)
              ]))]),
              _: 1
            }, 8, ["loading"])
          ]),
          _: 1
        }),
        _createVNode(_component_v_card_text, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_tabs, {
              modelValue: tab.value,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((tab).value = $event)),
              density: "compact",
              class: "mb-3"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_tab, { value: "runs" }, {
                  default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                    _createTextVNode("运行历史", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_tab, { value: "entries" }, {
                  default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                    _createTextVNode("逐种子明细", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_tab, { value: "nosource" }, {
                  default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
                    _createTextVNode("无源清单", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_tab, { value: "cleanup" }, {
                  default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
                    _createTextVNode("链接目录清理", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_v_tab, { value: "logs" }, {
                  default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                    _createTextVNode("运行日志", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["modelValue"]),
            _createVNode(_component_v_window, {
              modelValue: tab.value,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((tab).value = $event))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_window_item, { value: "runs" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_table, { density: "compact" }, {
                      default: _withCtx(() => [
                        _cache[13] || (_cache[13] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "时间"),
                            _createElementVNode("th", null, "模式"),
                            _createElementVNode("th", null, "可回迁"),
                            _createElementVNode("th", null, "成功"),
                            _createElementVNode("th", null, "失败"),
                            _createElementVNode("th", null, "跳过"),
                            _createElementVNode("th", null, "无源"),
                            _createElementVNode("th", null, "清理删除")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(journal.runs, (run, idx) => {
                            return (_openBlock(), _createElementBlock("tr", { key: idx }, [
                              _createElementVNode("td", null, _toDisplayString(_unref(formatTime)(run.finished_at || run.started_at)), 1),
                              _createElementVNode("td", null, _toDisplayString(run.mode), 1),
                              _createElementVNode("td", null, _toDisplayString(run.stats?.ready ?? '-'), 1),
                              _createElementVNode("td", null, _toDisplayString(run.moved_count ?? run.stats?.moved ?? '-'), 1),
                              _createElementVNode("td", null, _toDisplayString(run.failed_count ?? '-'), 1),
                              _createElementVNode("td", null, _toDisplayString(run.skipped_count ?? '-'), 1),
                              _createElementVNode("td", null, _toDisplayString(run.stats?.no_source ?? '-'), 1),
                              _createElementVNode("td", null, _toDisplayString(run.cleanup?.deleted_files ?? '-'), 1)
                            ]))
                          }), 128)),
                          (!journal.runs?.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_1, [...(_cache[12] || (_cache[12] = [
                                _createElementVNode("td", { colspan: "8" }, "暂无运行记录", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_window_item, { value: "entries" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_table, {
                      density: "compact",
                      "fixed-header": "",
                      height: "420"
                    }, {
                      default: _withCtx(() => [
                        _cache[15] || (_cache[15] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "ID"),
                            _createElementVNode("th", null, "名称"),
                            _createElementVNode("th", null, "状态"),
                            _createElementVNode("th", null, "旧路径"),
                            _createElementVNode("th", null, "新路径"),
                            _createElementVNode("th", null, "更新时间")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(journal.entries, (entry) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: entry.id
                            }, [
                              _createElementVNode("td", null, _toDisplayString(entry.id), 1),
                              _createElementVNode("td", _hoisted_2, _toDisplayString(entry.name), 1),
                              _createElementVNode("td", null, [
                                _createVNode(_component_v_chip, {
                                  size: "x-small",
                                  color: statusColor(entry.status),
                                  variant: "flat"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(statusText(entry.status)), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ]),
                              _createElementVNode("td", _hoisted_3, _toDisplayString(entry.old_dir), 1),
                              _createElementVNode("td", _hoisted_4, _toDisplayString(entry.new_dir), 1),
                              _createElementVNode("td", null, _toDisplayString(_unref(formatTime)(entry.updated_at)), 1)
                            ]))
                          }), 128)),
                          (!journal.entries?.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_5, [...(_cache[14] || (_cache[14] = [
                                _createElementVNode("td", { colspan: "6" }, "暂无明细", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_window_item, { value: "nosource" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_alert, {
                      type: "info",
                      variant: "tonal",
                      density: "compact",
                      class: "mb-3"
                    }, {
                      default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
                        _createTextVNode(" 这些种子在链接目录下找不到同内容的源（季包聚合或源已删除），保持原位并保留 cross-seed 标签。 ", -1)
                      ]))]),
                      _: 1
                    }),
                    _createVNode(_component_v_table, { density: "compact" }, {
                      default: _withCtx(() => [
                        _cache[18] || (_cache[18] = _createElementVNode("thead", null, [
                          _createElementVNode("tr", null, [
                            _createElementVNode("th", null, "ID"),
                            _createElementVNode("th", null, "名称"),
                            _createElementVNode("th", null, "体积"),
                            _createElementVNode("th", null, "当前路径"),
                            _createElementVNode("th", null, "原因")
                          ])
                        ], -1)),
                        _createElementVNode("tbody", null, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(journal.no_source, (entry) => {
                            return (_openBlock(), _createElementBlock("tr", {
                              key: entry.id
                            }, [
                              _createElementVNode("td", null, _toDisplayString(entry.id), 1),
                              _createElementVNode("td", _hoisted_6, _toDisplayString(entry.name), 1),
                              _createElementVNode("td", null, _toDisplayString(_unref(formatSize)(entry.size)), 1),
                              _createElementVNode("td", _hoisted_7, _toDisplayString(entry.current_dir), 1),
                              _createElementVNode("td", null, _toDisplayString(entry.reason), 1)
                            ]))
                          }), 128)),
                          (!journal.no_source?.length)
                            ? (_openBlock(), _createElementBlock("tr", _hoisted_8, [...(_cache[17] || (_cache[17] = [
                                _createElementVNode("td", { colspan: "5" }, "暂无无源种子", -1)
                              ]))]))
                            : _createCommentVNode("", true)
                        ])
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_window_item, { value: "cleanup" }, {
                  default: _withCtx(() => [
                    _createElementVNode("div", _hoisted_9, [
                      _createVNode(_component_v_btn, {
                        color: "primary",
                        variant: "flat",
                        "prepend-icon": "mdi-eye",
                        loading: cleanupLoading.value,
                        onClick: _cache[1] || (_cache[1] = $event => (runCleanup(true)))
                      }, {
                        default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                          _createTextVNode("预演清理", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"]),
                      _createVNode(_component_v_btn, {
                        color: "error",
                        variant: "flat",
                        "prepend-icon": "mdi-delete",
                        loading: cleanupLoading.value,
                        onClick: _cache[2] || (_cache[2] = $event => (runCleanup(false)))
                      }, {
                        default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                          _createTextVNode("实际清理", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading"])
                    ]),
                    (cleanup.message)
                      ? (_openBlock(), _createBlock(_component_v_alert, {
                          key: 0,
                          type: "info",
                          variant: "tonal",
                          density: "compact",
                          class: "mb-3"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(cleanup.message), 1)
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true),
                    (cleanup.cs_root)
                      ? (_openBlock(), _createBlock(_component_v_row, {
                          key: 1,
                          dense: ""
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_col, {
                              cols: "6",
                              md: "3"
                            }, {
                              default: _withCtx(() => [
                                _createVNode(_component_v_card, {
                                  variant: "tonal",
                                  class: "pa-3"
                                }, {
                                  default: _withCtx(() => [
                                    _cache[21] || (_cache[21] = _createElementVNode("div", { class: "text-caption" }, "扫描文件", -1)),
                                    _createElementVNode("div", _hoisted_10, _toDisplayString(cleanup.scanned_files), 1)
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
                                  class: "pa-3"
                                }, {
                                  default: _withCtx(() => [
                                    _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-caption" }, "受保护", -1)),
                                    _createElementVNode("div", _hoisted_11, _toDisplayString(cleanup.protected_files), 1)
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
                                  color: "warning",
                                  class: "pa-3"
                                }, {
                                  default: _withCtx(() => [
                                    _cache[23] || (_cache[23] = _createElementVNode("div", { class: "text-caption" }, "可删除", -1)),
                                    _createElementVNode("div", _hoisted_12, _toDisplayString(cleanup.deletable_files), 1),
                                    _createElementVNode("div", _hoisted_13, _toDisplayString(cleanup.deletable_human), 1)
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
                                    _cache[24] || (_cache[24] = _createElementVNode("div", { class: "text-caption" }, "已删除", -1)),
                                    _createElementVNode("div", _hoisted_14, _toDisplayString(cleanup.deleted_files), 1),
                                    _createElementVNode("div", _hoisted_15, _toDisplayString(cleanup.deleted_human), 1)
                                  ]),
                                  _: 1
                                })
                              ]),
                              _: 1
                            })
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true),
                    (cleanup.sample?.length)
                      ? (_openBlock(), _createBlock(_component_v_table, {
                          key: 2,
                          density: "compact",
                          class: "mt-3"
                        }, {
                          default: _withCtx(() => [
                            _cache[25] || (_cache[25] = _createElementVNode("thead", null, [
                              _createElementVNode("tr", null, [
                                _createElementVNode("th", null, "可删除文件示例")
                              ])
                            ], -1)),
                            _createElementVNode("tbody", null, [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(cleanup.sample, (path) => {
                                return (_openBlock(), _createElementBlock("tr", { key: path }, [
                                  _createElementVNode("td", _hoisted_16, _toDisplayString(path), 1)
                                ]))
                              }), 128))
                            ])
                          ]),
                          _: 1
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_window_item, { value: "logs" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_sheet, {
                      class: "pa-3",
                      color: "grey-darken-4",
                      rounded: ""
                    }, {
                      default: _withCtx(() => [
                        _createElementVNode("pre", _hoisted_17, _toDisplayString(logs.value), 1)
                      ]),
                      _: 1
                    })
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};

export { _sfc_main as default };
