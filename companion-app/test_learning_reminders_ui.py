"""Full production page, controlled clock, temporary data and blocked real providers."""
import datetime as dt
import json
import subprocess
import tempfile
from unittest.mock import patch
import server
import learning_reminders
from test_learning_system_034 import Fixture

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as folder,Fixture(folder) as fixture:
        stamp=[dt.datetime.now().astimezone().replace(hour=10,minute=0,second=0,microsecond=0)]
        plan={**fixture.plan,'requirements':fixture.req}
        fixture.request('/api/learning/confirm',{'plan':plan,'request_id':'ui-plan'},'POST')
        handler=fixture.srv.RequestHandlerClass;original=handler.do_POST
        def controlled(self):
            if self.path=='/api/reminder-fixture/time':
                self.begin_request()
                if not self.permitted(True):return self.send(403,{'error':'Isolated session only'})
                body=self.body();stamp[0]+=dt.timedelta(minutes=body.get('minutes',0),days=body.get('days',0))
                return self.send(200,{'time':stamp[0].isoformat()})
            return original(self)
        handler.do_POST=controlled
        with patch('learning_reminders.local_now',side_effect=lambda:stamp[0]):
            result=subprocess.run(['node','test_learning_reminders_ui.cjs',fixture.base],cwd=server.ROOT,check=False)
        assert fixture.calls==[], 'Reminder UI must never call any model'
        raise SystemExit(result.returncode)
