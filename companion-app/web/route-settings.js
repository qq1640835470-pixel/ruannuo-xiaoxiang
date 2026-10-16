"use strict";
(() => {
  const host = document.querySelector('#settings-drawer .drawer-body');
  if (!host || document.querySelector('#route-settings')) return;
  const section = document.createElement('details');
  section.id = 'route-settings';
  section.innerHTML = `<summary>路线规划</summary>
    <p>在聊天里给出步行或公交的具体步骤。查询会将你输入的起点、终点发送给选定地图平台，不自动发送设备 GPS。费用和配额由平台规则决定。</p>
    <label>地图平台<select id="route-provider"><option value="amap">高德地图（优先）</option><option value="baidu">百度地图（备选）</option><option value="google" disabled>Google Maps（暂未启用）</option></select></label>
    <p class="route-help">使用服务端 Web 服务 Key，并开通地理编码及步行/公交路线权限。百度需支持轻量级路线规划和 IP 校验类型；Google 仍需 Key、结算和展示策略核验。</p>
    <label>本机地图 Key<input id="route-key" type="password" autocomplete="new-password" spellcheck="false" placeholder="仅首次或更换时填写；不会回显"></label>
    <label class="route-check"><input id="route-enabled" type="checkbox">启用主动路线查询</label>
    <div class="route-actions"><button type="button" id="route-save">保存本机设置</button><button type="button" id="route-clear">删除此平台 Key</button></div>
    <p class="route-help">Key 通过 Windows DPAPI 加密保存在本机，供当前 Windows 用户使用；请勿在聊天中粘贴 Key。</p>
    <p id="route-status" role="status" aria-live="polite">正在读取本机配置…</p>
    <label>起点（含城市）<input id="route-origin" maxlength="160" placeholder="例如：北京市海淀区具体门牌或地标"></label>
    <label>终点（含城市）<input id="route-destination" maxlength="160" placeholder="请输入明确目的地"></label>
    <label>出行方式<select id="route-mode"><option value="walking">步行</option><option value="transit">公交 / 地铁</option></select></label>
    <button type="button" id="route-plan">查询路线步骤</button>
    <pre id="route-result" aria-live="polite"></pre>`;
  host.appendChild(section);
  const get = id => section.querySelector('#route-' + id);
  let busy = false, current = {};
  async function request(path, body) {
    const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Content-Type': 'application/json'}, ...(body ? {body: JSON.stringify(body)} : {})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '路线服务暂不可用。');
    return result.routes_status || result.settings || result;
  }
  function selectedStatus() {
    const item = (current.providers || []).find(p => p.id === get('provider').value);
    get('status').textContent = `${item?.configured ? '此平台已保存 Key（服务权限尚未验证）' : '此平台尚未配置 Key，暂不能查询真实路线'}。${current.enabled ? '已启用主动查询。' : '查询尚未启用。'}`;
  }
  function render(value) {
    current = value;
    get('provider').value = value.provider || 'amap';
    get('enabled').checked = value.enabled === true;
    selectedStatus();
  }
  async function run(action) {
    if (busy) return;
    busy = true;
    section.querySelectorAll('button').forEach(b => b.disabled = true);
    try { await action(); }
    catch { get('status').textContent = '操作未完成。请检查路线服务连接、地图 Key 和服务权限后重试。'; }
    finally { busy = false; section.querySelectorAll('button').forEach(b => b.disabled = false); }
  }
  get('provider').addEventListener('change', () => { get('key').value = ''; selectedStatus(); });
  get('save').addEventListener('click', () => run(async () => {
    const body = {provider: get('provider').value, api_key: get('key').value.trim(), enabled: get('enabled').checked};
    get('key').value = '';
    render(await request('/api/routes/settings', body));
  }));
  get('clear').addEventListener('click', () => run(async () => {
    get('key').value = '';
    render(await request('/api/routes/settings', {provider: get('provider').value, clear: true, enabled: get('enabled').checked}));
  }));
  get('plan').addEventListener('click', () => run(async () => {
    const origin = get('origin').value.trim(), destination = get('destination').value.trim();
    if (!origin || !destination) { get('status').textContent = '请先明确输入起点和终点，并包含城市。'; return; }
    get('result').textContent = '正在向选定地图平台查询…';
    const result = await request('/api/routes/plan', {origin, destination, mode: get('mode').value, provider: get('provider').value});
    const route = result.route || result;
    const lines = [route.summary || '平台未返回路线。'];
    if (route.origin && route.destination) lines.push(`匹配地点：${route.origin} → ${route.destination}`);
    (route.routes || []).forEach((r, i) => {
      lines.push(`\n方案 ${i + 1}${r.duration_seconds != null ? ` · 预计${Math.ceil(r.duration_seconds / 60)}分钟` : ''}${r.distance_meters != null ? ` · ${r.distance_meters}米` : ''}`);
      (r.steps || []).forEach((s, n) => lines.push(`${n + 1}. ${s.instruction}`));
    });
    if (route.source) lines.push(`来源：${route.source}`);
    if (route.note) lines.push(route.note);
    get('result').textContent = lines.join('\n');
  }));
  request('/api/routes/status').then(render).catch(() => { get('status').textContent = '本机路线设置暂未连接。'; });
})();
