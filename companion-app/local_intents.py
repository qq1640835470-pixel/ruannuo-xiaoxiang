"""Small deterministic synonyms before the optional local/cloud language model."""
import re

def music_request(text):
    if len(text)>160 or re.search(r'不要|不想|不用|别|例如|比如|反馈|[？?“”「」]',text):return None
    match=re.fullmatch(r'(?:请|麻烦)?(?:帮我|给我)?(随便|随机)?(?:播放|放|来|我想听|我要听|听)\s*(.{1,100}?)[。！!]?$',text)
    if not match:return None
    query=match[2].strip();random=bool(match[1])
    if query.startswith(('随便','随机')):random=True;query=query[2:].strip()
    amount=re.match(r'([0-9]{1,3}|[一二三四五六七八九十两几]{1,3})首\s*',query)
    count=None
    if amount:
        number=amount[1];digits={'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
        if number.isdigit():count=int(number)
        elif number=='几':count=5
        elif '十' in number:
            tens,ones=number.split('十',1);count=digits.get(tens,1)*10+digits.get(ones,0)
        else:count=digits.get(number,0)
        if not 1<=count<=20:raise ValueError('每次可以请求1至20首音乐。')
        query=query[amount.end():].strip()
    if not query:return None
    style=bool(re.search(r'钢琴|纯音乐|轻音乐|古典|爵士|摇滚|民谣|电子乐|助眠|放松|吉他曲|华语情歌',query))
    recommend=random or (count is not None and count>1) or style
    return {'query':query,'count':count or (5 if recommend else 1),'recommend':recommend}

def normalize(text):
    value=text.strip()
    if len(value)>100 or re.search(r'不要|不用|不想|别|不能|无法|怎么|为何|为什么|反馈|例如|比如|[「」“”"\n]',value):return value
    names=('QQ','qq','微信','Steam','steam','Chrome','chrome','计算器','记事本','百度地图','高德地图')
    if re.search(r'调出|唤起|开一下|帮我开|我想用|我要用|我想看看|我想看|切到|启动一下',value):
        for name in names:
            if name in value:return '打开'+name
    return value
