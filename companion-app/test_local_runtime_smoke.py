"""Explicit opt-in smoke test; local inference only, never executes model tool calls."""
import argparse,json,time
import local_runtime,web_tools

def run():
    deadline=time.monotonic()+240
    while not local_runtime.status()['installed']:
        if time.monotonic()>deadline:raise RuntimeError('Official model download not complete.')
        time.sleep(2)
    try:
        greeting=local_runtime.chat([{'role':'user','content':'你好小祥，简单打个招呼。'}],'当前是2026年10月16日傍晚；用户只要求打招呼。',companion=True)
        assert greeting['text'] and greeting['usage']['estimate_cny']==0
        print(json.dumps({'case':'greeting','text':greeting['text'],'usage':greeting['usage'],'backend':local_runtime.status()['backend']},ensure_ascii=True),flush=True)
        tool=local_runtime.chat([{'role':'user','content':'请调用weather工具查询深圳市南山区天气，先生成结构化调用，不要猜测天气结果。'}],'用户明确要求查询深圳市南山区天气，尚无任何天气结果。',tools=web_tools.TOOLS)
        assert tool['calls'] and tool['calls'][0]['name']=='weather'
        assert tool['usage']['estimate_cny']==0
        print(json.dumps({'case':'tool','calls':tool['calls'],'usage':tool['usage'],'executed':False},ensure_ascii=True),flush=True)
    finally:local_runtime.stop();print('Owned inference process stopped.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-real',action='store_true');args=parser.parse_args()
    if not args.run_real:raise SystemExit('Use --run-real to opt in to local inference.')
    run()
