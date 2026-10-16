"""Opt-in coarse location and public weather, with Windows user-bound storage."""
from __future__ import annotations
import datetime as dt
import json
import math
import pathlib
import threading
import time
import urllib.parse
import web_tools

_LOCK=threading.RLock()
_CACHE={}
REFRESH_SECONDS=1800

def _protect(raw,decrypt=False):
    from providers import hub
    return hub.protect(raw,decrypt=decrypt)

def _load(data_dir):
    path=pathlib.Path(data_dir)/'location.dpapi'
    if not path.is_file():return {'mode':'disabled'}
    try:
        data=json.loads(_protect(path.read_bytes(),decrypt=True))
        if not isinstance(data,dict) or data.get('mode') not in ('disabled','manual','geolocation'):raise ValueError()
        return data
    except Exception:
        raise ValueError('本机位置记录无法读取，请重新选择城市或定位。') from None

def _save(data,data_dir):
    directory=pathlib.Path(data_dir);directory.mkdir(parents=True,exist_ok=True)
    path=directory/'location.dpapi';temporary=directory/'location.dpapi.tmp'
    temporary.write_bytes(_protect(json.dumps(data,ensure_ascii=False).encode('utf-8')))
    temporary.replace(path)

def _coordinate(value,limit):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>limit:
        raise ValueError('位置坐标格式无效。')
    return round(value,2)

def _public(data):
    enabled=data.get('mode') in ('manual','geolocation')
    return {'mode':data.get('mode','disabled'),'enabled':enabled,
            'label':data.get('label','未设置位置'),'updated_at':data.get('updated_at'),
            'stale':enabled and time.time()-data.get('updated_epoch',0)>=REFRESH_SECONDS,
            'auto_refresh':data.get('mode')=='geolocation' and data.get('auto_refresh') is True,
            'timezone':data.get('timezone'),'precision':'约1公里（0.01度）','refresh_seconds':REFRESH_SECONDS}

def status(data_dir):
    with _LOCK:return _public(_load(data_dir))

def update(body,data_dir):
    if not isinstance(body,dict):raise ValueError('位置设置格式无效。')
    mode=body.get('mode')
    if mode not in ('disabled','manual','geolocation'):raise ValueError('请选择城市、定位或关闭位置。')
    with _LOCK:
        if body.get('automatic') is True:
            previous=_load(data_dir)
            if previous.get('mode')!='geolocation' or previous.get('auto_refresh') is not True:
                return {**_public(previous),'ignored':True}
        if mode=='disabled':
            _save({'mode':'disabled'},data_dir)
            return status(data_dir)
        if mode=='manual':
            city=web_tools.clean(body.get('city'),80)
            url='https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':city,'count':5,'language':'zh','format':'json'})
            try:rows=json.loads(web_tools.get(url)).get('results') or []
            except Exception:raise ValueError('城市检索暂不可用，请稍后重试。') from None
            if not rows:raise ValueError('没有找到这座城市，请补充省份或尝试城市名称。')
            row=rows[0]
            latitude=_coordinate(row.get('latitude'),90);longitude=_coordinate(row.get('longitude'),180)
            label=' · '.join(str(row[k])[:80] for k in ('name','admin1','country') if row.get(k))[:180]
        else:
            latitude=_coordinate(body.get('latitude'),90);longitude=_coordinate(body.get('longitude'),180)
            label='设备当前位置（粗略）'
        data={'mode':mode,'latitude':latitude,'longitude':longitude,'label':label,
              'auto_refresh':mode=='geolocation' and body.get('auto_refresh') is True,
              'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),'updated_epoch':time.time()}
        _save(data,data_dir)
        return _public(data)

def weather(data_dir):
    with _LOCK:data=_load(data_dir)
    if data.get('mode') not in ('manual','geolocation'):
        return {'status':'needs_location','detail':'请先选择城市，或主动启用设备定位。'}
    latitude=_coordinate(data.get('latitude'),90);longitude=_coordinate(data.get('longitude'),180)
    key=(str(pathlib.Path(data_dir).resolve()),latitude,longitude,data.get('label'))
    with _LOCK:
        previous=_CACHE.get(key)
        if previous and time.monotonic()-previous[0]<600:return {**previous[1],'cached':True}
    params={'latitude':latitude,'longitude':longitude,'timezone':'auto','forecast_days':2,
            'current':'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m',
            'daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'}
    try:
        raw=json.loads(web_tools.get('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(params)))
        current=raw.get('current') or {};daily=raw.get('daily') or {};zone=raw.get('timezone')
        if not isinstance(current.get('temperature_2m'),(int,float)) or not current.get('time') or not isinstance(zone,str) or len(daily.get('time',[]))<2:raise ValueError()
        current={k:current.get(k) for k in ('time','temperature_2m','apparent_temperature','relative_humidity_2m','weather_code','wind_speed_10m')}
        current['summary']=web_tools.WMO.get(current.get('weather_code'),'未知天气代码')
        days=[]
        for i,date in enumerate(daily['time'][:2]):
            day={k:daily.get(k,[None,None])[i] for k in ('weather_code','temperature_2m_max','temperature_2m_min','precipitation_probability_max')}
            day.update(date=date,summary=web_tools.WMO.get(day['weather_code'],'未知天气代码'));days.append(day)
        result={'status':'ok','kind':'weather','location':data['label'],'mode':data['mode'],'current':current,'days':days,'timezone':zone,
                'source':'Open-Meteo','source_url':'https://open-meteo.com/','queried_at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'note':'天气按约1公里粗略位置查询；模型网格预报，不是本地实测。','cached':False}
    except Exception:
        return {'status':'unavailable','detail':'天气数据源暂不可用，请稍后刷新。','source':'Open-Meteo'}
    with _LOCK:
        latest=_load(data_dir)
        if latest.get('updated_at')==data.get('updated_at') and latest.get('mode')==data.get('mode') and latest.get('latitude')==latitude and latest.get('longitude')==longitude:
            latest['timezone']=zone;_save(latest,data_dir)
        if len(_CACHE)>=16:_CACHE.pop(next(iter(_CACHE)))
        _CACHE[key]=(time.monotonic(),result)
    return result


def recent(data_dir):
    with _LOCK:
        data=_load(data_dir)
        rows=[value for key,(stamp,value) in _CACHE.items() if key[0]==str(pathlib.Path(data_dir).resolve()) and key[1:]==(data.get('latitude'),data.get('longitude'),data.get('label')) and time.monotonic()-stamp<600]
        return dict(rows[-1]) if rows else None
