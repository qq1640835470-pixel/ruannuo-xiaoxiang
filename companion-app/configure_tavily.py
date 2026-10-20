"""Configure only a local Tavily credential; no network or database access."""
import getpass
import json
import sys
import providers


def save_key(key):
    if not isinstance(key, str) or not key.startswith('tvly-') or not 12 <= len(key) <= 256 or any(ch.isspace() for ch in key):
        raise ValueError('Tavily Key 格式无效。')
    hub = providers.hub
    keys = hub.load_keys() if hub.VAULT.exists() else {}
    keys['tavily'] = key
    raw = json.dumps(keys).encode('utf-8');encrypted = hub.protect(raw)
    if hub.protect(encrypted, decrypt=True) != raw:raise RuntimeError('DPAPI 校验失败。')
    hub.VAULT.parent.mkdir(parents=True, exist_ok=True)
    temporary = hub.VAULT.with_suffix('.tmp')
    temporary.write_bytes(encrypted);temporary.replace(hub.VAULT)


if __name__ == '__main__':
    if not sys.stdin.isatty():raise SystemExit('请在本机交互式终端运行，不接受参数或管道中的 Key。')
    try:save_key(getpass.getpass('Tavily API Key (hidden): '))
    except (Exception, KeyboardInterrupt):raise SystemExit('保存未完成，请检查 Key 或 Windows DPAPI 权限。') from None
    print('已保存至现有 Windows DPAPI 凭据库，未发起网络请求。仅支持免费套餐且按量付费关闭。')
