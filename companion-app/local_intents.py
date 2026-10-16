"""Small deterministic synonyms before the optional local/cloud language model."""
import re

def normalize(text):
    value=text.strip()
    if len(value)>100 or re.search(r'不要|不用|不想|别|不能|无法|怎么|为何|为什么|反馈|例如|比如|[「」“”"\n]',value):return value
    names=('QQ','qq','微信','Steam','steam','Chrome','chrome','计算器','记事本','百度地图','高德地图')
    if re.search(r'调出|唤起|开一下|帮我开|我想用|我要用|我想看看|我想看|切到|启动一下',value):
        for name in names:
            if name in value:return '打开'+name
    return value
