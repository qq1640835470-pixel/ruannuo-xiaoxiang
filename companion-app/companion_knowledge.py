"""Small local lorebook and original dialogue candidates, separate from live facts."""
import datetime as dt,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parent

def load():
    return json.loads((ROOT/'assets'/'companion-worldbook.json').read_text(encoding='utf-8'))

def select(text,limit=1800):
    selected=[];remaining=limit
    for entry in load()['entries']:
        if not entry.get('always') and not any(k in text for k in entry['keywords']):continue
        content=entry['content'][:remaining]
        if not content:break
        selected.append({'id':entry['id'],'kind':entry['kind'],'content':content});remaining-=len(content)
    return selected

def library(clock,weather=None,task_count=0):
    data=load();phase=clock.get('phase',clock.get('period',''))
    # Phase from the local runtime is authoritative; lore never supplies current weather.
    lines=list(data['dialogue']['general'])+list(data['dialogue']['phases'].get(phase,[]))
    if weather and weather.get('status')=='ok':
        current=weather.get('current',{});summary=current.get('summary','')
        if '雨' in summary:lines+=['刚查到的天气预报里有雨。出门前可以再看一眼，伞带上会稳妥些。','预报里提到了雨，和我听一首歌也不错。']
        elif current.get('temperature_2m',0)>=30:lines+=['刚查到的预报温度有点高。要出门的话，记得带点水。']
    if task_count:lines+=['计划栏里有你记下的事情，想整理时叫我就好。']
    return {'lines':lines,'phase':phase,'worldbook_entries':len(data['entries']),'weather_attached':bool(weather),'source':'本机原创候选，不标作角色原作台词','limits':'角色条目不提供实时事实或工具权限；未启用持续监测或催促。'}
