import pathlib,tempfile,unittest
from activity_monitor import Monitor

class ActivityTests(unittest.TestCase):
    def test_observed_time_and_pause(self):
        with tempfile.TemporaryDirectory() as d:
            values=iter([{'app':'code.exe','idle_seconds':0},{'app':'chrome.exe','idle_seconds':3},{'app':'chrome.exe','idle_seconds':100}])
            monitor=Monitor(d,lambda:next(values));monitor.enabled=True
            monitor.sample(1);monitor.sample(6);monitor.sample(100)
            rows=monitor.status()['today']
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['app'],'code.exe')
            self.assertEqual(rows[0]['foreground_seconds'],5);self.assertEqual(rows[0]['idle_seconds'],3)
            monitor.configure(False);monitor.sample(105)
            self.assertEqual(monitor.status()['current'],{})
            self.assertEqual(monitor.status()['today'],rows)
    def test_no_sensitive_api(self):
        import activity_monitor
        source=pathlib.Path(activity_monitor.__file__).read_text(encoding='utf-8')
        for forbidden in ('GetWindowText','SetWindowsHook','GetAsyncKeyState','ImageGrab'):
            self.assertNotIn(forbidden,source)

if __name__=='__main__':unittest.main()
