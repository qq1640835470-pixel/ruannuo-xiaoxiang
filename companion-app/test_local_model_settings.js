'use strict';
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const flush = () => new Promise(resolve => setImmediate(resolve));
function fixture() {
  const nodes = new Map(), calls = [], events = {};
  function node() {
    return {value: '', textContent: '', disabled: false, hidden: false, options: [],
      setAttribute() {}, toggleAttribute(name, value) { this[name] = value; },
      append() {}, querySelectorAll() { return []; },
      after(...children) { children.forEach(child => { if (child.id) nodes.set(child.id, child); }); },
      replaceChildren(...children) { this.options = children; this.value = children[0]?.value || ''; },
      add(option) { this.options.push(option); }, addEventListener(event, fn) { this[event] = fn; }};
  }
  const get = id => { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); };
  let current = {selection: 'auto', ready: true, active_model: 'qwen3-4b-q4_k_m', models: [
    {id: 'qwen3-4b-q4_k_m', label: 'Qwen3 4B', installed: true},
    {id: 'qwen3-8b-q4_k_m', label: 'Qwen3 8B', installed: false}
  ]}, failure = false;
  const context = vm.createContext({document: {getElementById: get, createElement: node, querySelector: get},
    window: {addEventListener(event, fn) { events[event] = fn; }},
    Option: function(text, value) { this.textContent = text; this.value = value; },
    api: async (path, options) => {
      calls.push({path, body: options && JSON.parse(options.body)});
      if (options) { if (failure) throw new Error('保存失败'); current.selection = JSON.parse(options.body).model || current.selection; }
      return current;
    }
  });
  vm.runInContext(fs.readFileSync('web/local-model-settings.js', 'utf8'), context);
  return {nodes, calls, events, current, context, fail() { failure = true; }, get};
}
(async () => {
  const f = fixture(); await flush();
  const select = f.get('local-model-selection');
  assert.equal(select.value, 'auto'); assert.equal(select.disabled, false);
  assert.equal(select.options[2].disabled, true, 'uninstalled 8B cannot be selected');
  assert.match(f.get('local-model-info').textContent, /当前载入：Qwen3 4B/);
  f.current.models[1].installed = true; await f.events['xy:settings']();
  assert.equal(select.options[2].disabled, false);
  select.value = 'qwen3-8b-q4_k_m'; await select.change(); await flush();
  assert.deepEqual(f.calls.find(call => call.body)?.body, {operation: 'select', model: 'qwen3-8b-q4_k_m'});
  assert.equal(f.current.selection, 'qwen3-8b-q4_k_m');
  assert.equal(f.current.active_model, 'qwen3-4b-q4_k_m', 'selection does not claim immediate load');
  await f.get('local-model-release').click(); await flush();
  assert.deepEqual(f.calls.find(call => call.body?.operation === 'stop').body, {operation: 'stop'});
  f.fail(); select.value = 'auto'; await select.change(); await flush();
  assert.equal(select.value, 'qwen3-8b-q4_k_m', 'failed selection restores saved choice');
  assert.match(f.get('local-model-status').textContent, /操作失败/);
  f.get('model-select').value = 'local'; f.get('pet-provider').value = 'local';
  vm.runInContext(fs.readFileSync('web/model-settings.js', 'utf8'), f.context);
  f.context.window.XYModels.settingsLoaded({chat_models: {gemini: 'saved-chat'}, pet_models: {deepseek: 'saved-pet'}});
  await flush();
  assert.equal(f.get('chat-model-id').hidden, true); assert.equal(f.get('pet-model-id').hidden, true);
  assert.equal(f.get('catalog-status').hidden, true); assert.equal(f.get('catalog-refresh').hidden, true);
  assert.equal(f.context.window.XYModels.savePayload().chat_models.gemini, 'saved-chat');
  assert.equal(f.context.window.XYModels.savePayload().pet_models.deepseek, 'saved-pet');
  console.log('Local model UI checks passed: install gating, selection persistence, failed save recovery, loaded status, local catalogue isolation, preserved cloud preferences.');
})().catch(error => { console.error(error); process.exitCode = 1; });
