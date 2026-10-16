'use strict';
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const flush = () => new Promise(resolve => setImmediate(resolve));
const nodes = new Map(), calls = [];
function node() {
  return {value: '', textContent: '', disabled: false, hidden: false, children: [], options: [], style: {},
    setAttribute() {},
    append(...children) { this.children.push(...children); children.forEach(child => { if (child.id) nodes.set(child.id, child); }); },
    after(...children) { this.append(...children); },
    replaceChildren(...children) { this.children = children; },
    add(option) { this.options.push(option); if (this.options.length === 1) this.value = option.value; },
    querySelectorAll() { return this.children.flatMap(child => [child, ...child.querySelectorAll()]).filter(child => child.type === 'button'); },
    addEventListener(event, fn) { this[event] = fn; }
  };
}
nodes.set('local-model-status', node());
let data = {enabled: true, count: 13, items: Array.from({length: 13}, (_, i) => ({id: `item-${i}`, kind: 'preference', text: i === 12 ? '<img src=x onerror=alert(1)>' : `内容${i}`, created_at: `2026-10-${String(i + 1).padStart(2, '0')}`, source_id: 'settings_user_teach'}))};
let fail = false;
vm.runInNewContext(fs.readFileSync('web/local-model-settings.js', 'utf8'), {
  document: {getElementById: id => nodes.get(id), createElement: node},
  Option: function(text, value) { this.textContent = text; this.value = value; },
  api: async (path, options) => {
    const body = options && JSON.parse(options.body); calls.push({path, method: options?.method || 'GET', body});
    if (options && fail) throw new Error('测试失败');
    if (options?.method === 'PATCH') data.enabled = body.enabled;
    if (options?.method === 'DELETE') { data.items = data.items.filter(item => path !== `/api/local/adaptation/${item.id}`); data.count = data.items.length; }
    return JSON.parse(JSON.stringify(data));
  }
});
const get = id => nodes.get(`local-adaptation-${id}`);
(async () => {
  assert.equal(calls.length, 0, 'collapsed panel loads lazily');
  const panel = get('panel'); panel.open = true; panel.toggle(); await flush();
  assert.equal(get('list').children.length, 12); assert.equal(get('more').hidden, false);
  assert.equal(get('list').children[0].children[1].textContent, '<img src=x onerror=alert(1)>', 'user data is displayed as text');
  get('more').click(); assert.equal(get('list').children.length, 13); assert.equal(get('more').hidden, true);
  get('enabled').checked = false; await get('enabled').change(); await flush();
  assert.equal(data.enabled, false);
  get('kind').value = 'example'; get('kind').change();
  assert.equal(get('prompt').hidden, false); get('text').value = '回答';
  await get('teach').click(); assert.match(get('status').textContent, /填写问题/);
  get('prompt').value = '问题'; await get('teach').click(); await flush();
  assert.deepEqual(calls.find(call => call.path.endsWith('/teach')).body, {kind: 'example', text: '回答', source_id: 'settings_user_teach', prompt: '问题'});
  assert.equal(get('text').value, '');
  await get('list').children[0].children.at(-1).click(); await flush();
  assert.equal(data.count, 12); assert.equal(calls.at(-2).method, 'DELETE');
  fail = true; get('text').value = '保留未保存内容'; get('prompt').value = '问题';
  await get('teach').click(); assert.equal(get('text').value, '保留未保存内容'); assert.match(get('status').textContent, /操作失败/);
  console.log('Adaptation UI checks passed: lazy collapsed panel, newest 12 and expand, safe text, enable switch, explicit teach validation/payload, deletion, failed save preserves draft.');
})().catch(error => { console.error(error); process.exitCode = 1; });
