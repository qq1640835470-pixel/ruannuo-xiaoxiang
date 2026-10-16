"""Import only Sakiko model data and pinned runtime distributions; never runs package code."""
import base64
import hashlib
import io
import json
import pathlib
import struct
import tarfile
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'web/assets/pet'

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.live2d.com/'})
    return urllib.request.urlopen(request, timeout=45).read()

def main():
    source = next(pathlib.Path(r'C:\Users\16408\Downloads').glob('01-GALMYGO2.5*.galupdate'))
    with source.open('rb') as stream:
        assert stream.read(16) == b'GALMYGO-BUNDLE1\n'
        manifest = json.loads(stream.read(struct.unpack('<I', stream.read(4))[0]))
        stream.seek(sum(item['bytes'] for item in manifest['parts'][:2]), 1)
        part = stream.read(manifest['parts'][2]['bytes'])
    assert hashlib.sha256(part).hexdigest() == manifest['parts'][2]['sha256']
    labels = ['春季便服', '舞台服', '夏季高中制服', '冬季高中制服', '冬季初中制服']
    models = []
    with zipfile.ZipFile(io.BytesIO(part)) as archive:
        configs = [name for name in archive.namelist() if '/010_' in name and name.endswith('.model3.json')]
        for config, label in zip(configs, labels):
            directory = pathlib.PurePosixPath(config).parent
            model = json.loads(archive.read(config))
            refs = model['FileReferences']
            names = [refs['Moc'], *refs['Textures'], *[x['File'] for x in refs['Expressions']]]
            names += [x['File'] for group in refs['Motions'].values() for x in group]
            names += [refs[key] for key in ('Physics', 'Pose', 'DisplayInfo', 'UserData') if key in refs]
            for name in [pathlib.PurePosixPath(config).name, *names]:
                relative = pathlib.PurePosixPath(name)
                assert not relative.is_absolute() and '..' not in relative.parts
                assert relative.suffix in {'.json', '.moc3', '.png'}
                target = ROOT / 'live2d' / directory.name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(str(directory / relative)))
            models.append({'id': directory.name, 'label': label, 'url': '/assets/pet/live2d/' + directory.name + '/' + pathlib.PurePosixPath(config).name,
                           'expressions': [x['Name'] for x in refs['Expressions']], 'motions': list(refs['Motions'])})
    (ROOT / 'live2d/manifest.json').write_text(json.dumps({'source': source.name, 'part_sha256': hashlib.sha256(part).hexdigest(), 'models': models}, ensure_ascii=False, indent=2), encoding='utf-8')
    vendor = ROOT / 'vendor'
    vendor.mkdir(parents=True, exist_ok=True)
    records = []
    for package, version, entry, filename, license_name in [
        ('pixi.js', '6.5.10', 'package/dist/browser/pixi.min.js', 'pixi.min.js', 'PIXI-LICENSE.txt'),
        ('pixi-live2d-display', '0.4.0', 'package/dist/cubism4.min.js', 'cubism4.min.js', 'DISPLAY-LICENSE.txt'),
    ]:
        metadata = json.loads(fetch(f'https://registry.npmjs.org/{package}/{version}'))
        data = fetch(metadata['dist']['tarball'])
        assert hashlib.sha1(data).hexdigest() == metadata['dist']['shasum']
        if metadata['dist'].get('integrity', '').startswith('sha512-'):
            assert base64.b64encode(hashlib.sha512(data).digest()).decode() == metadata['dist']['integrity'][7:]
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for source_name, target_name in [(entry, filename), ('package/LICENSE', license_name)]:
                content = archive.extractfile(source_name).read()
                (vendor / target_name).write_bytes(content)
                records.append({'file': target_name, 'url': metadata['dist']['tarball'], 'version': version, 'npm_integrity': metadata['dist'].get('integrity'), 'sha256': hashlib.sha256(content).hexdigest()})
    sdk_url = 'https://cubism.live2d.com/sdk-web/bin/CubismSdkForWeb-5-r.4.zip'
    with zipfile.ZipFile(io.BytesIO(fetch(sdk_url))) as sdk:
        for suffix in ('Core/live2dcubismcore.min.js', 'Core/LICENSE.md', 'Core/RedistributableFiles.txt'):
            matches = [name for name in sdk.namelist() if name.endswith(suffix)]
            if not matches:
                continue
            content = sdk.read(matches[0])
            name = 'live2dcubismcore.min.js' if suffix.endswith('.js') else 'CORE-' + pathlib.PurePosixPath(suffix).name
            (vendor / name).write_bytes(content)
            records.append({'file': name, 'url': sdk_url, 'entry': matches[0], 'sha256': hashlib.sha256(content).hexdigest()})
    (vendor / 'provenance.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'models': len(models), 'files': sum(1 for x in ROOT.rglob('*') if x.is_file()), 'bytes': sum(x.stat().st_size for x in ROOT.rglob('*') if x.is_file())}))

if __name__ == '__main__':
    main()
