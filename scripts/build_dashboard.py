"""Build a downloadable HTML with a dated CH/HSS snapshot and live refresh.

No observation timestamps are changed. The browser applies the normal checksum,
age and quality gates to the embedded snapshot before using it.
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SLOT='<!-- CHHSS_BOOTSTRAP_SLOT -->'


def build(output, feed=None):
    html=(ROOT/'SpaceWxOps_Coronal_Hole_HSS_Outlook.html').read_text()
    payload=json.loads(Path(feed or ROOT/'chhss-data/feed.json').read_text())
    if payload.get('schemaVersion')!='chhss-feed-1':
        raise ValueError('Expected a measured chhss-feed-1 publication')
    encoded=json.dumps(payload,separators=(',',':'),allow_nan=False)
    encoded=encoded.replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    if html.count(SLOT)!=1:
        raise ValueError('Canonical HTML must contain one bootstrap slot')
    html=html.replace(SLOT, SLOT+'\n<script type="application/json" id="chhssBootstrap">'+encoded+'</script>')
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--feed',type=Path)
    args=parser.parse_args()
    print(build(args.output,args.feed))
