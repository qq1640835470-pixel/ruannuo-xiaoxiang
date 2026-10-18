"""Configure only the local OpenRouter credential; never make an API request."""
import getpass
import json
import sys
import providers


def save_key(key):
    if not isinstance(key,str) or not key.startswith('sk-or-') or len(key)<20 or any(c.isspace() for c in key):
        raise ValueError('OpenRouter Key 格式无效。')
    hub=providers.hub
    keys=hub.load_keys() if hub.VAULT.exists() else {}
    keys['openrouter']=key
    raw=json.dumps(keys).encode('utf-8')
    encrypted=hub.protect(raw)
    if hub.protect(encrypted,decrypt=True)!=raw:raise RuntimeError('DPAPI 校验失败，原凭据未修改。')
    hub.VAULT.parent.mkdir(parents=True,exist_ok=True)
    temporary=hub.VAULT.with_suffix('.tmp')
    temporary.write_bytes(encrypted)
    temporary.replace(hub.VAULT)


if __name__=='__main__':
    if not sys.stdin.isatty():raise SystemExit('请在本机交互式终端运行；不接受参数或管道中的 Key。')
    try:
        save_key(getpass.getpass('OpenRouter API Key (hidden): '))
    except (Exception,KeyboardInterrupt):
        raise SystemExit('保存未完成；请检查 Key 或当前 Windows 用户的 DPAPI 凭据权限。') from None
    print('已保存至现有 Windows 当前用户 DPAPI 库；未发起任何网络请求。')
