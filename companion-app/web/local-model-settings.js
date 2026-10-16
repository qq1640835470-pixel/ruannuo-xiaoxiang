'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const info = $('local-model-info');
  if (!info) return;
  const label = document.createElement('label');
  label.className = 'setting-label'; label.htmlFor = 'local-model-selection'; label.textContent = '本机模型选择';
  const select = document.createElement('select');
  select.id = 'local-model-selection'; select.disabled = true;
  const policy = document.createElement('p');
  policy.className = 'muted-text';
  policy.textContent = '自动模式按任务选择4B或8B；手动选择固定型号。对话和小祥闲聊共用此选择，保存后在下一次本机请求时生效，首次加载需要稍等。';
  const status = document.createElement('p');
  status.id = 'local-model-status'; status.className = 'muted-text'; status.setAttribute('role', 'status');
  const refresh = document.createElement('button');
  refresh.id = 'local-model-refresh';
  refresh.type = 'button'; refresh.className = 'text-button'; refresh.textContent = '刷新本机模型状态';
  const release = document.createElement('button');
  release.id = 'local-model-release';
  release.type = 'button'; release.className = 'text-button'; release.textContent = '释放本机模型占用';
  info.after(label, select, policy, refresh, release, status);
  let selection = 'auto', busy = false, revision = 0;
  const known = [
    {id: 'qwen3-4b-q4_k_m', label: 'Qwen3 4B · Q4_K_M'},
    {id: 'qwen3-8b-q4_k_m', label: 'Qwen3 8B · Q4_K_M'}
  ];
  function controls() { select.disabled = busy || !select.options.length; release.disabled = busy; refresh.disabled = busy; }
  async function load() {
    const current = ++revision;
    try {
      const data = await api('/api/local/model');
      if (current !== revision) return;
      const models = data.models || [];
      selection = data.selection || 'auto';
      select.replaceChildren(new Option('自动选择（4B / 8B）', 'auto'));
      known.forEach(item => {
        const model = models.find(row => row.id === item.id);
        const option = new Option(`${model?.label || item.label}${model?.installed ? '' : '（未安装）'}`, item.id);
        option.disabled = !model?.installed; select.add(option);
      });
      select.value = selection;
      const active = typeof data.active_model === 'object' ? data.active_model?.id : data.active_model;
      const activeLabel = models.find(row => row.id === active)?.label || active;
      const installed = models.filter(row => row.installed).map(row => row.label || row.id);
      info.textContent = `已安装：${installed.join('、') || '暂无'}。当前载入：${data.ready && activeLabel ? activeLabel : '未载入（按需启动）'}。`;
      controls();
    } catch (error) {
      if (current === revision) status.textContent = `读取本机模型失败：${error.message}`;
    }
  }
  async function control(payload) {
    busy = true; ++revision; controls(); status.textContent = '正在保存…';
    try {
      await api('/api/local/model/control', {method: 'POST', body: JSON.stringify(payload)});
      status.textContent = payload.operation === 'select' ? '本机模型选择已保存，下次本机请求时生效。' : '已释放本机模型占用。';
      await load();
    } catch (error) {
      select.value = selection; status.textContent = `操作失败：${error.message}`;
    } finally { busy = false; controls(); }
  }
  select.addEventListener('change', () => control({operation: 'select', model: select.value}));
  release.addEventListener('click', () => control({operation: 'stop'}));
  refresh.addEventListener('click', () => { status.textContent = ''; load(); });
  window.addEventListener('xy:settings', load);
  load();
})();

(() => {
  const anchor = document.getElementById('local-model-status');
  if (!anchor) return;
  const panel = document.createElement('details');
  panel.id = 'local-adaptation-panel';
  function element(tag, id, text) {
    const node = document.createElement(tag);
    if (id) node.id = id;
    if (text) node.textContent = text;
    panel.append(node);
    return node;
  }
  element('summary', '', '本机学习记录（非权重训练）');
  const description = element('p', '', '最多保留96条本机经验，作为后续对话参考；不会修改模型权重。仅保存你明确提交的教学内容。');
  description.className = 'muted-text';
  const enabledLabel = element('label', '', '启用本机经验适配');
  enabledLabel.className = 'toggle-row';
  const enabled = document.createElement('input');
  enabled.id = 'local-adaptation-enabled'; enabled.type = 'checkbox'; enabled.disabled = true;
  enabledLabel.append(enabled);
  const count = element('p', 'local-adaptation-count', '展开后读取本机记录。');
  count.className = 'muted-text';
  const refresh = element('button', 'local-adaptation-refresh', '刷新学习记录'); refresh.type = 'button'; refresh.className = 'text-button';
  const list = element('div', 'local-adaptation-list');
  const more = element('button', 'local-adaptation-more', '展开更多'); more.type = 'button'; more.className = 'text-button'; more.hidden = true;
  const kindLabel = element('label', '', '教学种类'); kindLabel.htmlFor = 'local-adaptation-kind'; kindLabel.className = 'setting-label';
  const kind = element('select', 'local-adaptation-kind');
  [['preference', '偏好'], ['correction', '纠正'], ['example', '问答示例']].forEach(([value, text]) => kind.add(new Option(text, value)));
  const promptLabel = element('label', '', '示例问题'); promptLabel.htmlFor = 'local-adaptation-prompt'; promptLabel.className = 'setting-label'; promptLabel.hidden = true;
  const prompt = element('textarea', 'local-adaptation-prompt'); prompt.rows = 2; prompt.hidden = true;
  const textLabel = element('label', '', '要教给小祥的内容'); textLabel.htmlFor = 'local-adaptation-text'; textLabel.className = 'setting-label';
  const text = element('textarea', 'local-adaptation-text'); text.rows = 3;
  const teach = element('button', 'local-adaptation-teach', '保存这条教学'); teach.type = 'button'; teach.className = 'subtle-button';
  const status = element('p', 'local-adaptation-status'); status.className = 'muted-text'; status.setAttribute('role', 'status');
  anchor.after(panel);
  let data = null, limit = 12, busy = false;
  function controls() {
    enabled.disabled = busy || !data;
    refresh.disabled = busy; teach.disabled = busy || !data;
    kind.disabled = busy; prompt.disabled = busy; text.disabled = busy;
    list.querySelectorAll('button').forEach(button => { button.disabled = busy; });
  }
  function render() {
    enabled.checked = data.enabled === true;
    const items = [...(data.items || [])].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))).slice(0, 96);
    count.textContent = `${data.count ?? items.length} / 96 条；${data.enabled ? '已启用' : '已暂停使用，记录仍保留'}。`;
    list.replaceChildren();
    items.slice(0, limit).forEach(item => {
      const row = document.createElement('div');
      const heading = document.createElement('p');
      heading.className = 'muted-text';
      heading.textContent = `${{preference: '偏好', correction: '纠正', example: '问答示例'}[item.kind] || item.kind} · ${item.created_at || ''}`;
      row.append(heading);
      if (item.prompt) { const question = document.createElement('p'); question.textContent = `问题：${item.prompt}`; row.append(question); }
      const content = document.createElement('p'); content.textContent = item.text || ''; content.style.whiteSpace = 'pre-wrap'; row.append(content);
      const source = document.createElement('p'); source.className = 'muted-text'; source.textContent = `来源：${item.source_id || '未记录'}`; row.append(source);
      const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button'; remove.textContent = '删除这条记录';
      remove.addEventListener('click', () => mutate(`/api/local/adaptation/${encodeURIComponent(item.id)}`, 'DELETE', {}, '记录已删除。'));
      row.append(remove); list.append(row);
    });
    if (!items.length) list.textContent = '暂无学习记录。';
    more.hidden = limit >= items.length;
    controls();
  }
  async function load() {
    data = await api('/api/local/adaptation');
    render();
  }
  async function refreshData() {
    if (busy) return;
    busy = true; controls(); status.textContent = '正在读取…';
    try { await load(); status.textContent = ''; }
    catch (error) { status.textContent = `读取失败：${error.message}`; }
    finally { busy = false; controls(); }
  }
  async function mutate(path, method, body, message) {
    if (busy) return false;
    busy = true; controls(); status.textContent = '正在保存…';
    try {
      await api(path, {method, body: JSON.stringify(body)});
      await load(); status.textContent = message; return true;
    } catch (error) { if (data) enabled.checked = data.enabled === true; status.textContent = `操作失败：${error.message}`; return false; }
    finally { busy = false; controls(); }
  }
  enabled.addEventListener('change', () => mutate('/api/local/adaptation', 'PATCH', {enabled: enabled.checked}, '经验适配设置已保存。'));
  kind.addEventListener('change', () => { prompt.hidden = promptLabel.hidden = kind.value !== 'example'; });
  teach.addEventListener('click', async () => {
    if (!text.value.trim()) { status.textContent = '请先输入教学内容。'; return; }
    if (kind.value === 'example' && !prompt.value.trim()) { status.textContent = '问答示例需要填写问题。'; return; }
    const body = {kind: kind.value, text: text.value.trim(), source_id: 'settings_user_teach'};
    if (kind.value === 'example') body.prompt = prompt.value.trim();
    if (await mutate('/api/local/adaptation/teach', 'POST', body, '教学已保存。')) { text.value = ''; prompt.value = ''; }
  });
  more.addEventListener('click', () => { limit = Math.min(96, limit + 12); render(); });
  refresh.addEventListener('click', refreshData);
  panel.addEventListener('toggle', () => { if (panel.open && !data) refreshData(); });
  controls();
})();
