"""Bounded local attachment storage. Only explicit user uploads are readable."""
import base64,binascii,hashlib,io,json,pathlib,re,threading,zipfile
import xml.etree.ElementTree as ET
from PIL import Image,UnidentifiedImageError

LOCK=threading.Lock()
MAX_FILE=4*1024*1024
TEXT_EXTENSIONS={'.txt','.md','.csv','.json','.log','.py','.js','.ts','.html','.css','.yaml','.yml','.xml'}
IMAGE_TYPES={'.png':('PNG','image/png'),'.jpg':('JPEG','image/jpeg'),'.jpeg':('JPEG','image/jpeg'),'.webp':('WEBP','image/webp')}

def validate_ids(values):
    if values is None:return []
    if not isinstance(values,list) or len(values)>3 or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in values):raise ValueError('每条消息最多选择3个有效附件。')
    if len(set(values))!=len(values):raise ValueError('请移除重复附件。')
    return values

def public(item):return {k:item[k] for k in ('id','name','size','kind')}

def store(body,data_dir):
    name=body.get('name');encoded=body.get('base64')
    if not isinstance(name,str) or not name.strip() or len(name)>160 or re.search(r'[/\\\x00-\x1f\x7f]',name):raise ValueError('附件文件名无效。')
    suffix=pathlib.Path(name).suffix.lower()
    if suffix not in TEXT_EXTENSIONS|IMAGE_TYPES.keys()|{'.docx'}:raise ValueError('支持PNG/JPEG/WebP图片、文本及DOCX文件；暂不支持PDF、压缩包或可执行文件。')
    if not isinstance(encoded,str) or len(encoded)>((MAX_FILE+2)//3)*4:raise ValueError('每个附件最多4MB。')
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):raise ValueError('附件编码无效。') from None
    if not raw or len(raw)>MAX_FILE:raise ValueError('附件不能为空，且每个最多4MB。')
    text='';kind='text';mime='application/octet-stream'
    if suffix in IMAGE_TYPES:
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!=IMAGE_TYPES[suffix][0] or image.width*image.height>20_000_000:raise ValueError('图片格式不符或像素超过2000万。')
                image.verify()
        except (OSError,UnidentifiedImageError,Image.DecompressionBombError):raise ValueError('图片损坏或尺寸过大，请换一张。') from None
        kind='image';mime=IMAGE_TYPES[suffix][1]
    elif suffix=='.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist())>2000 or sum(i.file_size for i in archive.infolist())>8*1024*1024:raise ValueError('DOCX展开后过大。')
                xml=archive.read('word/document.xml')
                if b'<!DOCTYPE' in xml.upper():raise ValueError('不支持含文档类型声明的DOCX。')
                root=ET.fromstring(xml)
                text='\n'.join(''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
        except (zipfile.BadZipFile,KeyError,ET.ParseError,RuntimeError):raise ValueError('DOCX无法读取；仅支持未加密文档正文。') from None
    else:
        for encoding in ('utf-8-sig','gb18030'):
            try:text=raw.decode(encoding);break
            except UnicodeDecodeError:pass
        else:raise ValueError('文本需使用UTF-8或GB18030编码。')
    if kind=='text' and (not text.strip() or len(text)>5000 or any(ord(c)<32 and c not in '\n\r\t' for c in text)):raise ValueError('文本或DOCX正文需为1至5000字，不能包含二进制内容；请先选取所需片段。')
    ident=hashlib.sha256(name.encode()+b'\0'+raw).hexdigest()
    item={'id':ident,'name':name,'size':len(raw),'kind':kind,'mime_type':mime,'text':text}
    directory=pathlib.Path(data_dir)/'chat-attachments'
    with LOCK:
        directory.mkdir(parents=True,exist_ok=True)
        (directory/(ident+'.bin')).write_bytes(raw)
        (directory/(ident+'.json')).write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
    return public(item)

def load(values,data_dir):
    values=validate_ids(values);items=[];directory=pathlib.Path(data_dir)/'chat-attachments'
    with LOCK:
        for ident in values:
            try:item=json.loads((directory/(ident+'.json')).read_text(encoding='utf-8'))
            except (OSError,ValueError):raise ValueError('附件已不可用，请重新选择文件。') from None
            if not (directory/(ident+'.bin')).is_file():raise ValueError('附件已不可用，请重新选择文件。')
            items.append(item)
    if sum(i['size'] for i in items)>8*1024*1024 or sum(i['kind']=='image' for i in items)>2:raise ValueError('每条消息附件合计最多8MB，图片最多2张。')
    return items

def content(item,data_dir):return (pathlib.Path(data_dir)/'chat-attachments'/(item['id']+'.bin')).read_bytes()
