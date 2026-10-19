"""Production scripts in Edge; temporary settings/catalogue and simulated HTTP."""
import subprocess
import tempfile
from unittest.mock import patch
from test_learning_models import SelectionFixture, read_local_selection
import server

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder,SelectionFixture(folder) as fixture:
        models=server.local_models
        def status():return {'installed':True,'ready':False,'selection':read_local_selection(),'models':[{'id':ident,'label':row['label'],'installed':True} for ident,row in models.CATALOG.items()]}
        with patch.object(models.app_paths,'DATA',fixture.data),patch('local_models.selection',side_effect=read_local_selection),patch('local_models.installed',return_value=True),patch('local_runtime.status',side_effect=status):
            result=subprocess.run(['node','test_learning_models_ui.cjs',fixture.base],cwd=server.ROOT)
        assert len(fixture.calls)==2,[(c['stage'],c['body']['model']) for c in fixture.calls]
        assert all(c['body']['model']=='vendor/independent-learning' for c in fixture.calls)
        raise SystemExit(result.returncode)
