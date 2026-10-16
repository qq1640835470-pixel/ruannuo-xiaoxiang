/* Independent provider/model selections. Listing models never generates text. */
(() => {
  const $ = id => document.getElementById(id);
  const catalogues = new Map(), requests = new Map();
  let reading = false;
  let maps = {chat_models: {}, pet_models: {}}, active = {}, revision = 0;
  const kinds = [
    {name:'chat', provider:'model-select', model:'chat-model-id', key:'chat_models'},
    {name:'pet', provider:'pet-provider', model:'pet-model-id', key:'pet_models'}
  ];
  async function getCatalogue(provider, refresh = false) {
    const request = (requests.get(provider) || 0) + 1; requests.set(provider, request);
    const response = await fetch(`/api/models?provider=${encodeURIComponent(provider)}${refresh ? '&refresh=1' : ''}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '读取型号列表失败');
    if (requests.get(provider) === request) catalogues.set(provider, data);
    return data;
  }
  function remember(kind) {
    const model = $(kind.model), provider = active[kind.name];
    if (model && model.value && provider && provider !== 'local') maps[kind.key][provider] = model.value;
  }
  function render(kind) {
    const select = $(kind.model), provider = $(kind.provider)?.value;
    if (!select) return;
    const catalogue = catalogues.get(provider), selected = maps[kind.key][provider] || catalogue?.defaults?.[kind.name];
    const local = provider === 'local';
    select.hidden = local;
    document.querySelector(`label[for="${kind.model}"]`)?.toggleAttribute('hidden', local);
    if (kind.name === 'chat' && $('model-detail')) $('model-detail').hidden = local;
    select.replaceChildren();
    if (local) {
      select.disabled = true; return;
    }
    select.disabled = false;
    const rows = catalogue?.models || [];
    if (selected && !rows.some(row => row.id === selected)) select.add(new Option(`${selected}（当前配置，列表未确认）`, selected));
    rows.forEach(row => select.add(new Option(`${row.id} · ${row.protective_estimate_available ? '已有保护估算' : '未核定计费'}`, row.id)));
    if (selected) select.value = selected;
    else { select.add(new Option('先读取模型列表并选择型号', '')); select.value = ''; }
  }
  function status() {
    const target = $('catalog-status'); if (!target) return;
    const providers = [...new Set(kinds.map(kind => $(kind.provider)?.value).filter(p => p && p !== 'local'))];
    target.hidden = !providers.length;
    if ($('catalog-refresh')) $('catalog-refresh').hidden = !providers.length;
    if (!providers.length) { target.textContent = ''; return; }
    target.textContent = providers.map(provider => {
      const c = catalogues.get(provider);
      if (!c || c.status === 'not_fetched') return `${provider}：尚未读取，点击读取型号列表`;
      const time = c.fetched_at ? new Date(c.fetched_at).toLocaleString('zh-CN') : '无成功快照';
      return `${provider}：${c.status === 'refresh_failed' ? '读取失败，保留旧列表；' : ''}${c.models.length} 个候选；${time}${c.stale ? '（旧快照）' : ''}${c.partial ? '；列表未完整' : ''}`;
    }).join('。') + '。仅列出文字候选，未逐一验证权限、工具和价格。未知价格的调用会占用全部剩余试用预算，待核账；已适配工具的主聊型号：Gemini 3.1/3.5 Flash-Lite、DeepSeek Flash；其他型号暂作纯文字对话，可使用本机设置及反馈按钮。Fish Audio仅用于语音。';
  }
  async function load(refresh = false) {
    const current = ++revision;
    const button = $('catalog-refresh'); if (refresh) reading = true; if (button) button.disabled = reading;
    const providers = [...new Set(kinds.map(kind => $(kind.provider)?.value).filter(p => p && p !== 'local'))];
    const outcomes = await Promise.allSettled(providers.map(p => getCatalogue(p, refresh)));
    if (current === revision) {
      kinds.forEach(render); status();
      const failed = outcomes.some(o => o.status === 'rejected');
      if (failed && $('catalog-status')) $('catalog-status').textContent = '型号列表读取失败，请稍后再试。已有选择保持保存。';
    }
    if (refresh) reading = false; if (button) button.disabled = reading;
  }
  window.XYModels = {
    settingsLoaded(settings) {
      maps = {chat_models:{...(settings.chat_models || {})}, pet_models:{...(settings.pet_models || {})}};
      kinds.forEach(kind => { active[kind.name] = $(kind.provider)?.value; render(kind); });
      status(); load();
    },
    savePayload() { kinds.forEach(remember); return {chat_models:{...maps.chat_models},pet_models:{...maps.pet_models}}; }
  };
  kinds.forEach(kind => {
    $(kind.provider)?.addEventListener('change', () => { remember(kind); active[kind.name] = $(kind.provider).value; render(kind); status(); load(); });
    $(kind.model)?.addEventListener('change', () => remember(kind));
  });
  $('catalog-refresh')?.addEventListener('click', () => { kinds.forEach(remember); load(true); });
})();
