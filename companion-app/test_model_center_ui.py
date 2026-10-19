import copy,json,subprocess,tempfile
from test_learning_system_034 import Fixture
from test_openrouter import ROW
import providers,server
if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder,Fixture(folder) as fixture:
        cache=json.loads(providers.CATALOG_PATH.read_text(encoding='utf-8'));rows=[]
        for i in range(1200):
            row=copy.deepcopy(ROW);row['id']=f'vendor{i%3}/model-{i:04d}';row['name']='Synthetic '+str(i);row['context_length']=32000;row['top_provider']['max_completion_tokens']=10000
            row['architecture']['input_modalities']=['text','image'] if i%5==0 else ['text']
            row['pricing']={'prompt':'0','completion':'0'} if i%3==0 else {'prompt':'0.000001','completion':'0.000003'}
            rows.append(row)
        row=copy.deepcopy(ROW);row.update(id='unknown/free-label:free',name='Unknown Price',pricing={});rows.append(row)
        cache['openrouter']['models']+=providers.normalize_models('openrouter',{'data':rows});providers.CATALOG_PATH.write_text(json.dumps(cache),encoding='utf-8')
        result=subprocess.run(['node','test_model_center_ui.cjs',fixture.base],cwd=server.ROOT)
        assert not fixture.calls,'Model center must not call a generation API'
        raise SystemExit(result.returncode)
