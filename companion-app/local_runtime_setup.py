"""Portable official Qwen/llama.cpp installer. No model-provided code is executed."""
from __future__ import annotations
import hashlib,json,os,pathlib,re,shutil,subprocess,time,urllib.request,zipfile
import app_paths
BASE=app_paths.MODELS
MODEL_NAME='Qwen3-4B-Q4_K_M.gguf'
MODEL_SIZE=2497280256
MODEL_SHA='7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
MODEL_URL='https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/'+MODEL_NAME
HEADERS={'User-Agent':'StudyLifeAssistant-local-setup/0.3.1','Accept':'application/json'}

def metadata(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=20) as r:return json.load(r)

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def download(url,destination,size,digest):
    destination=pathlib.Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    record=destination.with_suffix(destination.suffix+'.download.json')
    if destination.is_file() and destination.stat().st_size==size and sha256(destination)==digest:
        record.write_text(json.dumps({'source':url,'size':size,'sha256':digest,'state':'verified'}),encoding='utf-8');return destination
    partial=destination.with_suffix(destination.suffix+'.part')
    record.write_text(json.dumps({'source':url,'size':size,'sha256':digest,'state':'downloading'}),encoding='utf-8')
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>size:raise ValueError('下载残片超过官方长度，请检查下载目录。')
    if offset<size:
        request=urllib.request.Request(url,headers={**HEADERS,**({'Range':f'bytes={offset}-'} if offset else {})})
        with urllib.request.urlopen(request,timeout=30) as response:
            if offset and response.status!=206:raise ValueError('下载源未确认续传，已保留本机残片。')
            if offset and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise ValueError('下载源续传范围不符。')
            with partial.open('ab' if offset else 'wb') as target:
                last=time.monotonic()
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    target.write(block);offset+=len(block)
                    if offset>size:raise ValueError('下载内容超过官方长度。')
                    if time.monotonic()-last>10:
                        target.flush();print(json.dumps({'file':destination.name,'downloaded':offset,'size':size}),flush=True);last=time.monotonic()
    if partial.stat().st_size!=size:raise ValueError('下载未完成，重跑可续传。')
    if sha256(partial)!=digest:raise ValueError('SHA256校验失败，未启用文件。')
    partial.replace(destination);record.write_text(json.dumps({'source':url,'size':size,'sha256':digest,'state':'verified'}),encoding='utf-8');return destination

def download_parallel(url,destination,size,digest):
    import concurrent.futures
    destination=pathlib.Path(destination);partial=destination.with_suffix(destination.suffix+'.part')
    if destination.is_file():return download(url,destination,size,digest)
    destination.parent.mkdir(parents=True,exist_ok=True)
    start=partial.stat().st_size if partial.exists() else 0
    if start>size:raise ValueError('下载残片超过官方长度。')
    directory=destination.with_suffix('.chunks');directory.mkdir(exist_ok=True)
    ranges=[(offset,min(size,offset+256*1024*1024)) for offset in range(start,size,256*1024*1024)]
    def segment(bounds):
        first,end=bounds;path=directory/str(first)
        for attempt in range(6):
            offset=first+(path.stat().st_size if path.exists() else 0)
            if offset==end:return path
            if offset>end:raise ValueError('下载分段长度无效。')
            try:
                headers={**HEADERS,'Range':f'bytes={offset}-{end-1}'}
                with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as response:
                    if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-{end-1}/'):raise ValueError('下载源没有确认分段范围。')
                    with path.open('ab') as stream:
                        remaining=end-offset
                        while remaining:
                            block=response.read(min(1024*1024,remaining))
                            if not block:break
                            stream.write(block);remaining-=len(block)
            except (OSError,TimeoutError):
                if attempt==5:raise
        if not path.exists() or path.stat().st_size!=end-first:raise ValueError('分段未完成，已保留以便续传。')
        return path
    completed=start
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in concurrent.futures.as_completed([pool.submit(segment,bounds) for bounds in ranges]):
            path=future.result();completed+=path.stat().st_size
            print(json.dumps({'file':destination.name,'downloaded':completed,'size':size,'mode':'parallel_resume'}),flush=True)
    with partial.open('ab') as output:
        for first,end in ranges:
            with (directory/str(first)).open('rb') as stream:shutil.copyfileobj(stream,output,4*1024*1024)
    if partial.stat().st_size!=size or sha256(partial)!=digest:raise ValueError('官方文件校验失败，未启用。')
    partial.replace(destination)
    destination.with_suffix(destination.suffix+'.download.json').write_text(json.dumps({'source':url,'size':size,'sha256':digest,'state':'verified'}),encoding='utf-8')
    for first,end in ranges:(directory/str(first)).unlink()
    if not any(directory.iterdir()):directory.rmdir()
    return destination

def detected_cuda():
    executable=shutil.which('nvidia-smi')
    if not executable:return None
    try:
        result=subprocess.run([executable],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        match=re.search(r'CUDA (?:UMD )?Version:\s*(\d+)\.(\d+)',result.stdout)
        return tuple(map(int,match.groups())) if match else None
    except (OSError,subprocess.SubprocessError):return None

def runtime_release():
    releases=metadata('https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10');supported=detected_cuda()
    for release in releases:
        assets=release.get('assets',[])
        cpu=[a for a in assets if re.fullmatch(r'llama-.*-bin-win-cpu-x64\.zip',a['name'])]
        candidates=[]
        for asset in assets:
            match=re.fullmatch(r'llama-.*-bin-win-cuda-(\d+)\.(\d+)-x64\.zip',asset['name'])
            if match and supported and tuple(map(int,match.groups()))<=supported:candidates.append((tuple(map(int,match.groups())),asset))
        if candidates:
            version_tuple,chosen=max(candidates,key=lambda row:row[0]);version='.'.join(map(str,version_tuple))
            dependencies=[a for a in assets if a['name']==f'cudart-llama-bin-win-cuda-{version}-x64.zip']
            return release['tag_name'],[chosen,*dependencies,*cpu[:1]]
        if cpu:return release['tag_name'],cpu[:1]
    raise ValueError('官方近期发布中没有匹配的Windows便携包，未下载未知替代品。')

def extract_verified(archive,directory):
    directory.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            target=(directory/entry.filename).resolve()
            if not target.is_relative_to(directory.resolve()):raise ValueError('运行时压缩包路径无效。')
        package.extractall(directory)

def install_runtime():
    tag,assets=runtime_release();destination=BASE/'llama.cpp'/tag
    for asset in assets:
        digest=asset.get('digest','')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):raise ValueError('官方运行时缺少SHA256，未启用。')
        print(json.dumps({'runtime':tag,'file':asset['name'],'size':asset['size']}),flush=True)
        archive=download(asset['browser_download_url'],BASE/'downloads'/asset['name'],asset['size'],digest[7:]);extract_verified(archive,destination/'cpu' if 'cpu-x64' in asset['name'] else destination)
    executables=list(destination.rglob('llama-server.exe'));executable=next((p for p in executables if 'cpu' not in p.parts),executables[0] if executables else None);cpu=next((p for p in executables if 'cpu' in p.parts),None)
    if not executable:raise ValueError('官方压缩包没有llama-server.exe。')
    (BASE/'runtime.json').write_text(json.dumps({'version':tag,'executable':str(executable),'backend':'cuda' if any('cuda' in a['name'] for a in assets) else 'cpu','cpu_executable':str(cpu) if cpu else '', 'verified':True}),encoding='utf-8')
    return executable

def install_model(model='4b'):
    if model=='4b':return download(MODEL_URL,BASE/MODEL_NAME,MODEL_SIZE,MODEL_SHA)
    if model!='8b':raise ValueError('仅支持4b或8b。')
    item=json.loads((pathlib.Path(__file__).parent/'assets/qwen8b-official.json').read_text(encoding='utf-8'))
    return download_parallel('https://huggingface.co/'+item['repo']+'/resolve/'+item['revision']+'/'+item['file'],BASE/item['file'],item['size'],item['sha256'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--model-only',action='store_true');parser.add_argument('--runtime-only',action='store_true');parser.add_argument('--model',choices=('4b','8b'),default='4b');args=parser.parse_args()
    try:
        if not args.runtime_only:install_model(args.model)
        if not args.model_only:install_runtime()
        (BASE/'setup-progress.json').write_text(json.dumps({'state':'complete' if not (args.runtime_only or args.model_only) else 'selected_step_complete'}),encoding='utf-8')
        print('Verified local setup complete.',flush=True)
    except Exception as exc:
        BASE.mkdir(parents=True,exist_ok=True)
        (BASE/'setup-progress.json').write_text(json.dumps({'state':'failed','error_type':type(exc).__name__,'resume':'python local_runtime_setup.py'}),encoding='utf-8')
        print(json.dumps({'state':'failed','error_type':type(exc).__name__,'resume':'python local_runtime_setup.py'}),flush=True);raise SystemExit(1)
