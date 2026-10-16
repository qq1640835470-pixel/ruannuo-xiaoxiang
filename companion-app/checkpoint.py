"""Save a local source snapshot and a consistent app database copy for continuation."""
import app_paths
import argparse,datetime as dt,json,os,pathlib,shutil,sqlite3,zipfile

ROOT=pathlib.Path(__file__).resolve().parent
def save(note):
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    folder=ROOT.parent/'checkpoints'/stamp;folder.mkdir(parents=True,exist_ok=False)
    for name in ('continuation.md','AGENTS.md'):
        source=ROOT.parent/name
        if source.is_file():shutil.copy2(source,folder/name)
    files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py','.md','.json','.cjs')]
    files += [p for p in (ROOT/'web').rglob('*') if p.is_file()]
    for p in (ROOT/'music-runtime'/'package.json',ROOT/'music-runtime'/'package-lock.json'):
        if p.is_file():files.append(p)
    with zipfile.ZipFile(folder/'source.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
    database=app_paths.DATA/'assistant.sqlite3'
    if database.is_file():
        with sqlite3.connect(database) as source,sqlite3.connect(folder/'assistant.sqlite3') as target:source.backup(target)
    result={'created_at':stamp,'source_files':len(files),'note':note,'continuation':'D:/StudyLifePlan/continuation.md','excludes':['API密钥','登录Cookie','浏览器凭据','运行时依赖目录']}
    (folder/'checkpoint.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT.parent/'checkpoints'/'latest.json').write_text(json.dumps({'path':str(folder),**result},ensure_ascii=False,indent=2),encoding='utf-8')
    return folder
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--note',default='阶段性进度保存');print(save(p.parse_args().note))
