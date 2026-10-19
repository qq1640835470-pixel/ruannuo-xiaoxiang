"""Explicit local-only SQLite rehearsal. Never prints or exports row contents."""
import argparse
import contextlib
import hashlib
import json
import pathlib
import shutil
import sqlite3
import socket
import tempfile
from unittest.mock import patch


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def quote(name):return '"'+name.replace('"','""')+'"'


def inventory(c, columns=None):
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    result={}
    for table in (columns or dict.fromkeys(tables)):
        fields=columns[table]['columns'] if columns else [r[1] for r in c.execute('PRAGMA table_info('+quote(table)+')')]
        h=hashlib.sha256();count=0
        for row in c.execute('SELECT '+','.join(map(quote,fields))+' FROM '+quote(table)+' ORDER BY rowid'):
            # Type-tagged serialization stays in this process; only digests leave it.
            value=[['bytes',v.hex()] if isinstance(v,bytes) else [type(v).__name__,v] for v in row]
            h.update(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode());count+=1
        result[table]={'columns':fields,'count':count,'sha256':h.hexdigest()}
    return result


def run(source, destination, historical_backup=None, expected_backup_hash=None):
    source=pathlib.Path(source).resolve(strict=True);destination=pathlib.Path(destination).resolve()
    if destination.exists() or destination==source.parent or source.is_relative_to(destination):
        raise ValueError('Rehearsal requires a new independent destination directory.')
    destination.mkdir(parents=True,exist_ok=False)
    original_files={p.name:file_hash(p) for p in source.parent.glob(source.name+'*') if p.is_file()}
    pristine=destination/'pristine.sqlite3';working=destination/'working.sqlite3'
    with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as c:
        assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        c.execute('BEGIN')
        before=inventory(c)
        with contextlib.closing(sqlite3.connect(pristine)) as target:c.backup(target)
        c.rollback()
    shutil.copyfile(pristine,working)
    backup={}
    if historical_backup:
        path=pathlib.Path(historical_backup).resolve(strict=True)
        backup['sha256_matches_manifest']=file_hash(path)==expected_backup_hash
        with contextlib.closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
            backup['integrity_ok']=c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert all(backup.values())
    import server
    report={'source_read_only':True,'historical_backup':backup,'source_integrity_ok':True,
            'source_sha256':original_files[source.name],'pristine_sha256':file_hash(pristine),'source_counts':{k:v['count'] for k,v in before.items()}}
    # Run the real init path, with no network, credentials, monitoring or formal DB access.
    with tempfile.TemporaryDirectory() as metadata,patch.object(server,'DATA',pathlib.Path(metadata)),patch.object(server,'DB',working),patch.object(server,'MONITOR',None),patch.object(server.providers,'CATALOG_PATH',pathlib.Path(metadata)/'catalogue.json'),patch('socket.create_connection',side_effect=AssertionError('No network in private rehearsal')),patch('providers.hub.load_keys',side_effect=AssertionError('No credentials in private rehearsal')),patch('persistent_memory.observe',side_effect=AssertionError('Unexpected chat backfill; inspect without reading content')):
        catalogue=source.parent/'model-catalogue.json'
        if catalogue.is_file():shutil.copyfile(catalogue,server.providers.CATALOG_PATH)
        try:
            server.init()
            with server.connect() as c:
                assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                after=inventory(c,before);first=inventory(c)
            changed=[t for t in before if before[t]['sha256']!=after[t]['sha256'] or before[t]['count']!=after[t]['count']]
            server.init()
            with server.connect() as c:second=inventory(c)
            report.update(old_table_changes=changed,all_old_rows_preserved=not changed,
                          added_tables=sorted(set(first)-set(before)),
                          added_columns={t:[v for v in first[t]['columns'] if v not in before[t]['columns']] for t in before if first[t]['columns']!=before[t]['columns']},
                          repeated_init_identical=first==second,post_integrity_ok=True)
            assert not changed and first==second
        finally:
            if server.MONITOR:server.MONITOR.close()
    with contextlib.closing(sqlite3.connect(pristine)) as c:
        assert inventory(c)==before
        report['restoration_copy_verified']=c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    final_files={p.name:file_hash(p) for p in source.parent.glob(source.name+'*') if p.is_file()}
    report['source_files_unchanged']=original_files==final_files
    assert report['source_files_unchanged']
    (destination/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--destination',required=True)
    parser.add_argument('--historical-backup');parser.add_argument('--expected-backup-hash')
    args=parser.parse_args()
    result=run(args.source,args.destination,args.historical_backup,args.expected_backup_hash)
    print(json.dumps(result,ensure_ascii=False,indent=2))
