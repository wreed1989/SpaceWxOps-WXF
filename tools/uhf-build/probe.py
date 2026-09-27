"""Retrieve public model references without altering operational assets.

This isolated build publishes only short-lived workflow artifacts. It does not
run downloaded source, commit third-party packages, or modify the main branch.
"""
import concurrent.futures
import hashlib
import json
import pathlib
import urllib.request
import zipfile
import io

root = pathlib.Path('model-assets')
root.mkdir(exist_ok=True)
sources = {
    'itu_p531_16_supplement.zip': 'https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.531-16-202509-I!!ZIP-E.zip',
    'itu_p2097_components.zip': 'https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-P.2097-2007-ZPF-E.zip',
    'wbmod_instantrun.html': 'https://kauai.ccmc.gsfc.nasa.gov/instantrun/wbmod/',
    'itu_p531_16.pdf': 'https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.531-16-202509-I!!PDF-E.pdf',
    'itu_p2097.pdf': 'https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-P.2097-2007-PDF-E.pdf',
}

def retrieve(item):
    name, url = item
    record = {'name': name, 'source': url}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SpaceWxOps-UHF-Research/1.0'})
        with urllib.request.urlopen(req, timeout=45) as response:
            data = response.read(35_000_001)
            record['final_url'] = response.url
            record['content_type'] = response.headers.get('Content-Type')
        if len(data) > 35_000_000:
            raise ValueError('Source exceeds reference retrieval size limit')
        if name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                record['members'] = archive.namelist()
                if archive.testzip() is not None:
                    raise ValueError('ZIP CRC failure')
        elif name.endswith('.pdf') and not data.startswith(b'%PDF'):
            raise ValueError('Response is not a PDF')
        (root / name).write_bytes(data)
        record.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), status='success')
    except Exception as error:
        record.update(status='failed', error=str(error))
    print(json.dumps(record), flush=True)
    return record

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    records = list(pool.map(retrieve, sources.items()))
(root / 'public_reference_manifest.json').write_text(json.dumps(records, indent=2))
