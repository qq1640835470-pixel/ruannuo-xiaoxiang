"""Explicit text-address routing through fixed official REST adapters.

Keys stay in Windows user-bound DPAPI storage. No GPS, model calls or fallback
to another provider; each plan sends only the addresses to the selected service.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import math
import pathlib
import re
import threading
import time
import urllib.parse
import urllib.request

_LOCK = threading.RLock()
PROVIDERS = {'amap': '高德地图', 'baidu': '百度地图', 'google': 'Google Maps'}
GOOGLE_REASON = '暂未启用：需要独立 API Key、结算账户及展示策略核验。'
_ENDPOINTS = {
    'amap_geo': 'https://restapi.amap.com/v3/geocode/geo',
    'amap_poi': 'https://restapi.amap.com/v3/place/text',
    'amap_walking': 'https://restapi.amap.com/v3/direction/walking',
    'amap_transit': 'https://restapi.amap.com/v3/direction/transit/integrated',
    'baidu_geo': 'https://api.map.baidu.com/geocoding/v3/',
    'baidu_walking': 'https://api.map.baidu.com/directionlite/v1/walking',
    'baidu_transit': 'https://api.map.baidu.com/directionlite/v1/transit',
}


def _protect(raw, decrypt=False):
    from providers import hub
    return hub.protect(raw, decrypt=decrypt)


def _load(data_dir):
    path = pathlib.Path(data_dir) / 'routes.dpapi'
    if not path.exists():
        return {'provider': 'amap', 'enabled': False, 'keys': {}}
    try:
        data = json.loads(_protect(path.read_bytes(), decrypt=True))
        if not isinstance(data, dict) or not isinstance(data.get('keys'), dict):
            raise ValueError()
        return data
    except Exception:
        raise ValueError('本机路线配置无法读取，请在路线设置中重新保存。') from None


def _public(data):
    provider = data.get('provider', 'amap')
    configured = bool(data['keys'].get(provider))
    return {'provider': provider, 'enabled': data.get('enabled') is True,
            'configured': configured,
            'providers': [{'id': p, 'name': name, 'configured': bool(data['keys'].get(p)),
                           'available': p != 'google', 'reason': GOOGLE_REASON if p == 'google' else ''}
                          for p, name in PROVIDERS.items()],
            'summary': ('已保存本机配置，尚未验证服务权限。' if configured else '尚未配置地图 Key，暂不能查询真实路线。'),
            'privacy': '仅主动查询时将输入的地点名称或起点、终点发给选定平台；不自动发送设备 GPS。费用和配额由平台规则决定。'}


def status(data_dir):
    with _LOCK:
        return _public(_load(data_dir))


def configure(body, data_dir):
    if not isinstance(body, dict):
        raise ValueError('路线设置格式无效。')
    provider = body.get('provider', 'amap')
    if provider not in ('amap', 'baidu'):
        raise ValueError(GOOGLE_REASON if provider == 'google' else '请选择高德或百度。')
    key = body.get('api_key', body.get('key', ''))
    if not isinstance(key, str) or (key and not re.fullmatch(r'[A-Za-z0-9_-]{8,256}', key.strip())):
        raise ValueError('地图 Key 格式无效，请在本机设置中检查。')
    with _LOCK:
        try:
            data = _load(data_dir)
        except ValueError:
            if not key.strip():
                raise
            data = {'keys': {}}
        if body.get('clear') is True:
            data['keys'].pop(provider, None)
        elif key.strip():
            data['keys'][provider] = key.strip()
        data.update(provider=provider, enabled=body.get('enabled', True) is True)
        directory = pathlib.Path(data_dir)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / 'routes.dpapi.tmp'
        temporary.write_bytes(_protect(json.dumps(data).encode('utf-8')))
        temporary.replace(directory / 'routes.dpapi')
        return _public(data)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(endpoint, params):
    url = _ENDPOINTS[endpoint] + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'StudyLifePlan/0.3.1'})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('response limit')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('invalid response')
    return value


def _number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None


def _text(value):
    return html.unescape(re.sub(r'<[^>]*>', '', value))[:1000] if isinstance(value, str) else ''


def _step(row):
    return {'instruction': _text(row.get('instruction') or row.get('instructions')),
            'distance_meters': _number(row.get('distance')), 'duration_seconds': _number(row.get('duration'))}


def _amap_geocode(address, key):
    if re.search(r'(?:大学|校区|地铁站|火车站|[东南西北]站)$',address):
        return _amap_landmark(address,key)
    raw = _request('amap_geo', {'address': address, 'key': key, 'output': 'JSON'})
    if str(raw.get('status')) != '1':
        raise RuntimeError('provider rejected')
    rows = raw.get('geocodes') or []
    if len(rows) != 1:
        return _amap_landmark(address,key)
    row = rows[0]
    if row.get('level') in ('国家', '省', '市', '区县', '乡镇'):
        return _amap_landmark(address,key)
    location = row.get('location', '')
    if not isinstance(location, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?', location):
        raise RuntimeError('invalid coordinates')
    return {'coordinate': location, 'label': _text(row.get('formatted_address')) or address,
            'city': _text(row.get('citycode')) or _text(row.get('city'))}


def _amap_pois(query,key):
    raw=_request('amap_poi',{'keywords':query,'key':key,'offset':10,'extensions':'base','output':'JSON'})
    if str(raw.get('status'))!='1':raise RuntimeError('provider rejected')
    rows=[];seen=set()
    for row in (raw.get('pois') or [])[:10]:
        name=_text(row.get('name')).replace(key,'[已隐藏]');coordinate=row.get('location','')
        if not name or not isinstance(coordinate,str) or not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?',coordinate):continue
        lng,lat=map(float,coordinate.split(','))
        if not (-180<=lng<=180 and -90<=lat<=90) or (name,coordinate) in seen:continue
        seen.add((name,coordinate))
        address=''.join(_text(row.get(field)) for field in ('pname','cityname','adname','address')).replace(key,'[已隐藏]')
        rows.append({'name':name,'address':address,'coordinate':coordinate,'city':_text(row.get('cityname')).replace(key,'[已隐藏]'),
                     'longitude':lng,'latitude':lat})
    return rows


def search_places(query,data_dir):
    """Return configured AMap candidates, or None when the legacy lookup applies."""
    with _LOCK:data=_load(data_dir)
    if data.get('provider')!='amap' or not data.get('enabled') or not data['keys'].get('amap'):return None
    base={'query':query,'results':[],'provider':'amap','source':'高德地图','source_url':'https://www.amap.com/',
          'coordinate_system':'GCJ-02'}
    try:
        rows=_amap_pois(query,data['keys']['amap'])
        for row in rows:
            row['url']='https://uri.amap.com/marker?'+urllib.parse.urlencode({'position':row['coordinate'],'name':row['name'],'src':'ruannuo-xiaoxiang','coordinate':'gaode','callnative':0})
        return {**base,'status':'ok','results':rows,'queried_at':int(time.time()),
                'detail':'高德地点候选，请核对名称与地址；点击候选在高德地图查看。未获取当前位置。' if rows else '高德未返回地点候选，请补充城市、校区或车站全名。'}
    except Exception:
        return {**base,'status':'unavailable','detail':'高德地点服务未完成查询，请检查Key权限、配额或网络；未切换其他平台。'}


def _amap_landmark(address,key):
    rows=_amap_pois(address,key)
    normalize=lambda value:re.sub(r'[\s()（）·-]','',value)
    query=normalize(address)
    matches=[row for row in rows if len(normalize(row['name']))>=4 and
             (query.endswith(normalize(row['name'])) or query in (normalize(row['name']+row['address']),normalize(row['address']+row['name'])))]
    if len(matches)!=1:
        names='；'.join(row['name']+' · '+row['address'] for row in rows[:3])
        raise LookupError('地点尚未唯一匹配，请补充校门、车站或区县。'+('候选：'+names if names else ''))
    row=matches[0]
    return {'coordinate':row['coordinate'],'label':row['name']+'（'+row['city']+'）','city':row['city']}


def _baidu_geocode(address, key):
    if len(address.encode('utf-8')) > 128:
        raise LookupError('百度地址最多128字节，请缩短地址并保留城市和具体地点。')
    raw = _request('baidu_geo', {'address': address, 'ak': key, 'output': 'json', 'ret_coordtype': 'bd09ll'})
    if raw.get('status') != 0:
        raise RuntimeError('provider rejected')
    row = raw.get('result') or {}
    if row.get('precise') != 1 or row.get('level') in ('国家', '省', '城市', '区县', '乡镇'):
        raise LookupError('地址匹配不够精确，请补充城市、区县和门牌或地标。')
    point = row.get('location') or {}
    lat, lng = point.get('lat'), point.get('lng')
    if not isinstance(lat, (float, int)) or not isinstance(lng, (float, int)) or not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 90 or abs(lng) > 180:
        raise RuntimeError('invalid coordinates')
    return {'coordinate': f'{lat:.6f},{lng:.6f}', 'label': address}


def _amap_routes(raw, mode):
    if str(raw.get('status')) != '1':
        raise RuntimeError('provider rejected')
    route = raw.get('route') or {}
    result = []
    for row in (route.get('paths' if mode == 'walking' else 'transits') or [])[:3]:
        steps = []
        complete = True
        if mode == 'walking':
            steps = [_step(s) for s in row.get('steps', [])]
        else:
            for segment in row.get('segments', []):
                railway=segment.get('railway') or {}
                if any(railway.get(field) for field in ('id','name','trip','departure_stop','arrival_stop')) or segment.get('taxi'):
                    complete = False
                    break
                walking = segment.get('walking') or {}
                if _number(walking.get('distance')) and not walking.get('steps'):
                    complete = False
                    break
                steps.extend(_step(s) for s in walking.get('steps', []))
                lines = (segment.get('bus') or {}).get('buslines') or []
                if lines:
                    line = lines[0]
                    start = _text((line.get('departure_stop') or {}).get('name'))
                    end = _text((line.get('arrival_stop') or {}).get('name'))
                    name = _text(line.get('name'))
                    if name and start and end:
                        instruction = f'在{start}上车，乘坐{name}，在{end}下车'
                        stops = _number(line.get('via_num'))
                        if stops is not None:
                            instruction += f'（途经{int(stops)}站）'
                        steps.append({**_step(line), 'instruction': instruction, 'line': name,
                                      'departure_stop': start, 'arrival_stop': end})
                    else:
                        complete = False
                        break
        if not complete:
            continue
        result.append({'duration_seconds': _number(row.get('duration')), 'distance_meters': _number(row.get('distance')),
                       'fare': None, 'steps': [s for s in steps if s['instruction']]})
    return result


def _baidu_routes(raw, mode):
    if raw.get('status') == 1001:
        return []
    if raw.get('status') != 0:
        raise RuntimeError('provider rejected')
    result = []
    for row in (raw.get('result', {}).get('routes') or [])[:3]:
        steps = []
        for group in row.get('steps', []):
            # Transit steps may contain alternatives; present the first alternative.
            item = group[0] if isinstance(group, list) and group else group
            if isinstance(item, dict):
                step = _step(item)
                vehicle = item.get('vehicle') or {}
                if vehicle.get('name'):
                    step.update(line=_text(vehicle['name']), departure_stop=_text(vehicle.get('start_name')),
                                arrival_stop=_text(vehicle.get('end_name')))
                if step['instruction']:
                    steps.append(step)
        result.append({'duration_seconds': _number(row.get('duration')), 'distance_meters': _number(row.get('distance')),
                       'fare': None, 'steps': steps})
    return result


def plan(origin, destination, mode='walking', provider=None, data_dir=None):
    """Return verifiable route steps; never return credentials or raw provider errors."""
    if data_dir is None:
        raise ValueError('需要本机数据目录。')
    if mode not in ('walking', 'transit'):
        raise ValueError('目前支持步行和公交。')
    if any(not isinstance(x, str) or not x.strip() or len(x) > 160 for x in (origin, destination)):
        raise ValueError('请明确输入1至160字的起点和终点，并包含城市。')
    with _LOCK:
        data = _load(data_dir)
    provider = provider or data.get('provider', 'amap')
    if provider not in PROVIDERS:
        raise ValueError('未知地图平台。')
    base = {'provider': provider, 'source': PROVIDERS[provider], 'routes': []}
    if provider == 'google':
        return {**base, 'status': 'disabled', 'summary': GOOGLE_REASON}
    key = data['keys'].get(provider)
    if not key or data.get('enabled') is not True:
        return {**base, 'status': 'needs_configuration', 'summary': '请在本机设置的「路线规划」中填入地图 Key 并启用，之后才能查询真实步行或公交步骤。请勿在聊天中发送 Key。'}
    try:
        geocode = _amap_geocode if provider == 'amap' else _baidu_geocode
        start, end = geocode(origin.strip(), key), geocode(destination.strip(), key)
        params = {'origin': start['coordinate'], 'destination': end['coordinate']}
        if provider == 'amap':
            params.update(key=key, output='JSON')
            if mode == 'transit':
                if not start.get('city') or not end.get('city'):
                    raise LookupError('公交查询需要可识别城市的具体地址，请补充起终点城市。')
                params.update(city=start['city'], cityd=end['city'], extensions='base')
        else:
            params.update(ak=key, coord_type='bd09ll', ret_coordtype='bd09ll')
            if mode == 'transit':
                params['steps_info'] = 1
        raw = _request(provider + '_' + mode, params)
        routes = (_amap_routes if provider == 'amap' else _baidu_routes)(raw, mode)
        routes = [r for r in routes if r['steps']]
        # Provider-controlled text is untrusted and could echo a request credential.
        routes = json.loads(json.dumps(routes, ensure_ascii=False).replace(key, '[已隐藏]'))
        if not routes:
            return {**base, 'status': 'no_route', 'summary': '平台没有返回可核对的路线步骤，请检查具体地址或尝试其他出行方式。'}
        return {**base, 'status': 'ok', 'mode': mode, 'routes': routes,
                'origin': start['label'].replace(key, '[已隐藏]'), 'destination': end['label'].replace(key, '[已隐藏]'),
                'queried_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'summary': f'{PROVIDERS[provider]}返回{len(routes)}条' + ('步行' if mode == 'walking' else '公交') + '方案；请先核对匹配地点。',
                'note': '用时为平台估算；未提供实时到站或可确认票价，请以车站公告和实际运营为准。'}
    except LookupError as error:
        return {**base, 'status': 'needs_clarification', 'summary': str(error).replace(key,'[已隐藏]')}
    except Exception:
        return {**base, 'status': 'unavailable', 'summary': '地图服务未完成查询，请检查本机 Key、服务权限、配额或网络后重试。未生成路线。'}
