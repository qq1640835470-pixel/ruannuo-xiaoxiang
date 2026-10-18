"""Explicit place candidates from configured AMap or the legacy public lookup."""
import json,threading,time,urllib.parse,urllib.request
import app_paths,maps_routes
_LOCK=threading.Lock()
_CACHE={}
_LAST=0.0

def search_places(query):
    global _LAST
    query=str(query).strip()
    if not query or len(query)>160:raise ValueError('地点名称须为1至160字。')
    try:configured=maps_routes.search_places(query,app_paths.DATA)
    except ValueError:return {'status':'unavailable','query':query,'results':[],'detail':'本机地图配置无法读取，请在路线设置中重新保存。'}
    if configured is not None:return configured
    with _LOCK:
        cached=_CACHE.get(query)
        if cached and time.time()-cached[0]<86400:return cached[1]
        time.sleep(max(0,1.05-(time.monotonic()-_LAST)))
        _LAST=time.monotonic()
        url='https://photon.komoot.io/api/?'+urllib.parse.urlencode({'q':query,'limit':5})
        request=urllib.request.Request(url,headers={'User-Agent':'RuannuoXiang/0.3 (local personal single-user explicit POI lookup)','Accept':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:raw=json.loads(response.read(1000000))
            results=[];seen=set()
            for feature in raw.get('features',[])[:5]:
                p=feature.get('properties',{});coordinates=feature.get('geometry',{}).get('coordinates',[])
                if len(coordinates)!=2:continue
                address=' '.join(str(p[k]) for k in ('country','state','city','district','street','housenumber') if p.get(k))
                name=p.get('name') or query
                if (name,address) in seen:continue
                seen.add((name,address))
                results.append({'name':name,'address':address,'latitude':coordinates[1],'longitude':coordinates[0]})
            result={'status':'ok','query':query,'results':results,'source':'Photon / OpenStreetMap','source_url':'https://photon.komoot.io/','queried_at':int(time.time()),'detail':'地点检索，无实时交通；地图数据 © OpenStreetMap contributors。'}
            _CACHE[query]=(time.time(),result)
            return result
        except Exception:
            return {'status':'unavailable','query':query,'results':[],'source':'Photon / OpenStreetMap','detail':'地点服务暂未返回；没有猜测位置。'}
