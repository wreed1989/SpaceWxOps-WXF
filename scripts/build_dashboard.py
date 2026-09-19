"""Build a downloadable HTML with a dated CH/HSS snapshot and live refresh.

No observation timestamps are changed. The browser applies the normal checksum,
age and quality gates to the embedded snapshot before using it.
"""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SLOT='<!-- CHHSS_BOOTSTRAP_SLOT -->'


def build(output, feed=None, solar_cycle=None, cme_scoreboard=None, particle_forecasts=None, nairas=None, electron_forecast=None):
    html=(ROOT/'SpaceWxOps_Coronal_Hole_HSS_Outlook.html').read_text()
    payload=json.loads(Path(feed or ROOT/'chhss-data/feed.json').read_text())
    if payload.get('schemaVersion')!='chhss-feed-1':
        raise ValueError('Expected a measured chhss-feed-1 publication')
    encoded=json.dumps(payload,separators=(',',':'),allow_nan=False)
    encoded=encoded.replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    if html.count(SLOT)!=1:
        raise ValueError('Canonical HTML must contain one bootstrap slot')
    html=html.replace(SLOT, SLOT+'\n<script type="application/json" id="chhssBootstrap">'+encoded+'</script>')
    if solar_cycle:
        solar=json.loads(Path(solar_cycle).read_text())
        if not all(isinstance(solar.get(k),list) and solar[k] for k in ['observed','predicted']) or not solar.get('retrievedAt'):
            raise ValueError('Solar-cycle snapshot requires both full NOAA arrays and retrieval time')
        slot='<!-- SOLAR_CYCLE_BOOTSTRAP_SLOT -->'
        if html.count(slot)!=1:
            raise ValueError('Canonical HTML must contain one solar-cycle slot')
        encoded=json.dumps(solar,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
        html=html.replace(slot,slot+'\n<script type="application/json" id="solarCycleBootstrap">'+encoded+'</script>')
    if cme_scoreboard:
        snapshot=json.loads(Path(cme_scoreboard).read_text())
        if not isinstance(snapshot.get('rows'),list) or not snapshot.get('retrievedAt'):
            raise ValueError('CME Scoreboard snapshot requires rows and retrieval time')
        slot='<!-- CME_SCOREBOARD_BOOTSTRAP_SLOT -->'
        if html.count(slot)!=1:raise ValueError('Canonical HTML must contain one CME Scoreboard slot')
        encoded=json.dumps(snapshot,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
        html=html.replace(slot,slot+'\n<script type="application/json" id="cmeScoreboardBootstrap">'+encoded+'</script>')
    particles=Path(particle_forecasts or ROOT/'chhss-data/particle-forecasts.json')
    if particles.exists():
        snapshot=json.loads(particles.read_text())
        if snapshot.get('schemaVersion')!='particle-forecasts-1':
            raise ValueError('Invalid particle-forecast snapshot')
        slot='<!-- PARTICLE_FORECAST_BOOTSTRAP_SLOT -->'
        if html.count(slot)!=1:raise ValueError('Canonical HTML must contain one particle slot')
        encoded=json.dumps(snapshot,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
        html=html.replace(slot,slot+'\n<script type="application/json" id="particleForecastBootstrap">'+encoded+'</script>')
    radiation=Path(nairas or ROOT/'chhss-data/nairas.json')
    if radiation.exists():
        snapshot=json.loads(radiation.read_text())
        if snapshot.get('schemaVersion')!='nairas-effective-dose-1':
            raise ValueError('Invalid NAIRAS snapshot')
        slot='<!-- NAIRAS_BOOTSTRAP_SLOT -->'
        if html.count(slot)!=1:raise ValueError('Canonical HTML must contain one NAIRAS slot')
        encoded=json.dumps(snapshot,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
        html=html.replace(slot,slot+'\n<script type="application/json" id="nairasBootstrap">'+encoded+'</script>')
    electron=Path(electron_forecast or ROOT/'chhss-data/electron-fluence.json')
    if electron.exists():
        snapshot=json.loads(electron.read_text())
        if snapshot.get('schemaVersion')!='WXF-EF-0.1':
            raise ValueError('Invalid WXF experimental electron snapshot')
        slot='<!-- WXF_ELECTRON_BOOTSTRAP_SLOT -->'
        if html.count(slot)!=1:raise ValueError('Canonical HTML must contain one WXF electron slot')
        encoded=json.dumps(snapshot,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
        html=html.replace(slot,slot+'\n<script type="application/json" id="wxfElectronBootstrap">'+encoded+'</script>')
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--feed',type=Path)
    parser.add_argument('--solar-cycle',type=Path,help='Full observed/predicted NOAA snapshot with original retrieval time')
    parser.add_argument('--cme-scoreboard',type=Path,help='Dated current NASA CME Scoreboard response')
    parser.add_argument('--particle-forecasts',type=Path,help='Dated published particle-model snapshot')
    parser.add_argument('--nairas',type=Path,help='Full global 20 km effective-dose-rate grids with original product epochs')
    parser.add_argument('--electron-forecast',type=Path,help='Dated WXF experimental rolling-fluence forecast')
    args=parser.parse_args()
    print(build(args.output,args.feed,args.solar_cycle,args.cme_scoreboard,args.particle_forecasts,args.nairas,args.electron_forecast))
