import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { u as usePluginApi } from './api-Bew_unR_.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock} = await importShared('vue');


const _hoisted_1 = { class: "d-flex align-center mb-2" };
const _hoisted_2 = { class: "d-flex justify-space-between text-caption" };
const _hoisted_3 = { class: "d-flex justify-space-between text-caption" };
const _hoisted_4 = { class: "d-flex justify-space-between text-caption" };
const _hoisted_5 = { class: "text-caption text-medium-emphasis mt-2" };

const {onMounted,reactive} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'CrossSeedRelocator' },
  sourcePluginId: { type: String, default: '' },
  config: { type: Object, default: () => ({}) },
  allowRefresh: { type: Boolean, default: false },
  nativeSubscribe: { type: Function, default: null },
},
  setup(__props) {

const props = __props;
const client = usePluginApi(props);
const data = reactive({});

onMounted(async () => {
  try {
    Object.assign(data, (await client.get('status')) || {});
  } catch (error) {
    // 仪表盘加载失败时保持静默，不打扰主界面
  }
});

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_card = _resolveComponent("v-card");

  return (_openBlock(), _createBlock(_component_v_card, {
    variant: "tonal",
    class: "pa-3"
  }, {
    default: _withCtx(() => [
      _createElementVNode("div", _hoisted_1, [
        _createVNode(_component_v_icon, {
          class: "mr-2",
          size: "20"
        }, {
          default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
            _createTextVNode("mdi-swap-horizontal-bold", -1)
          ]))]),
          _: 1
        }),
        _cache[1] || (_cache[1] = _createElementVNode("span", { class: "text-subtitle-2" }, "辅种路径回迁", -1)),
        _createVNode(_component_v_spacer),
        _createVNode(_component_v_chip, {
          size: "x-small",
          color: data.enabled ? 'success' : 'grey'
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(data.enabled ? '启用' : '停用'), 1)
          ]),
          _: 1
        }, 8, ["color"])
      ]),
      _createElementVNode("div", _hoisted_2, [
        _cache[2] || (_cache[2] = _createElementVNode("span", null, "待处理", -1)),
        _createElementVNode("b", null, _toDisplayString(data.stats?.ready || 0), 1)
      ]),
      _createElementVNode("div", _hoisted_3, [
        _cache[3] || (_cache[3] = _createElementVNode("span", null, "无源保留", -1)),
        _createElementVNode("b", null, _toDisplayString(data.stats?.no_source || 0), 1)
      ]),
      _createElementVNode("div", _hoisted_4, [
        _cache[4] || (_cache[4] = _createElementVNode("span", null, "累计成功", -1)),
        _createElementVNode("b", null, _toDisplayString(data.success_count || 0), 1)
      ]),
      _createElementVNode("div", _hoisted_5, _toDisplayString(data.last_run?.finished_at || '尚未运行'), 1)
    ]),
    _: 1
  }))
}
}

};

export { _sfc_main as default };
