import contextlib,pathlib,sqlite3,tempfile,unittest
from checkpoint import redact_database

class BackupTests(unittest.TestCase):
    def test_redaction_removes_bytes_and_keeps_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'copy.sqlite3'
            with contextlib.closing(sqlite3.connect(path)) as c,c:
                c.execute('CREATE TABLE feedback(id TEXT PRIMARY KEY,content TEXT)')
                c.execute('INSERT INTO feedback VALUES(?,?)',('one','{"text":"my_map_key_fixture and sk-testcredential123456789"}'))
            redact_database(path,['my_map_key_fixture'])
            raw=path.read_bytes()
            self.assertNotIn(b'my_map_key_fixture',raw);self.assertNotIn(b'sk-testcredential',raw)
            import json
            with contextlib.closing(sqlite3.connect(path)) as c:
                value=json.loads(c.execute('SELECT content FROM feedback').fetchone()[0])
                self.assertIn('[凭据已遮蔽]',value['text'])

if __name__=='__main__':unittest.main()
