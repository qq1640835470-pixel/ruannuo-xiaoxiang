"""Opt-in, zero-cloud Gemma text and synthetic-image smoke test."""
import argparse,json,pathlib,struct,zlib
import local_models,local_runtime as runtime,local_runtime_setup as setup


def run():
    if not local_models.installed(local_models.GEMMA):raise RuntimeError('Gemma model and projector must finish verified download first.')
    width,height=512,256;rows=[]
    for y in range(height):
        row=bytearray()
        for x in range(width):
            pixel=(255,255,255)
            if 40<=x<200 and 48<=y<208:pixel=(235,20,20)
            if (x-375)**2+(y-128)**2<80**2:pixel=(20,60,235)
            row.extend(pixel)
        rows.append(b'\0'+row)
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    image=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
    directory=pathlib.Path(__file__).parent/'artifacts';directory.mkdir(exist_ok=True)
    (directory/'gemma-synthetic-033.png').write_bytes(image)
    report={'model':local_models.GEMMA,'runtime_version':(runtime._configuration() or {}).get('version'),'synthetic_image':'red square on left, blue circle on right, white background','requested_configuration':{'context':8192,'batch':512,'ubatch':512,'max_image_tokens':256,'single_process':True,'cloud':False},'selection_before':local_models.selection()}
    try:
        report['text']=runtime.chat([{'role':'user','content':'请计算7乘8，只回答结果。'}],'本次是本机模型验收。',model=local_models.GEMMA)
        assert '56' in report['text']['text'],report['text']['text']
        report['image']=runtime.analyze_images('请用中文说出图片左边和右边图形各是什么颜色、什么形状。',[{'data':image,'mime_type':'image/png'}])
        answer=report['image']['text'];assert all(value in answer for value in ('红','蓝','方','圆')),answer
        report['backend']=runtime.status()['backend'];report['pid']=runtime._PROCESS.pid
        report['selection_after']=local_models.selection()
        assert report['selection_before']==report['selection_after']
        report['passed']=True
        print(json.dumps(report,ensure_ascii=True),flush=True)
    finally:
        runtime.stop();report['released']=runtime._PROCESS is None
        (directory/'gemma-smoke-033.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-real',action='store_true');args=parser.parse_args()
    if not args.run_real:raise SystemExit('Use --run-real for the local-only smoke test.')
    run()
