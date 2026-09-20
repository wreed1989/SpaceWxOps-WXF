"""WXF SEP 0.1: event-triggered, 24-hour threshold probabilities.

Features stop at the flare peak. Labels start 10 minutes after the peak;
15-minute sustained crossings are required. No future flare/CME association
or post-peak integrated X-ray flux is used as a predictor.
"""
import math
import numpy as np
VERSION='WXF-SEP-0.1'
TARGETS={'p10_10':('P10',10.),'p10_40':('P10',40.),'p50_10':('P50',10.)}
FEATURES=['log_peak','log_rise_minutes','longitude_sin','longitude_cos','latitude_abs','log_p10','log_p50','p10_trend','p50_trend','log_prior_flares']

def exceeds(value, key):
    if value is None or not math.isfinite(value):
        return False
    threshold = TARGETS[key][1]
    return value > threshold if key == 'p10_40' else value >= threshold


def feature_values(event, prior, past_flares=0):
    """prior: valid GOES samples strictly before the flare peak, max 24 h."""
    def last(channel):
        vals=[r[channel] for r in prior[-12:] if r.get(channel) is not None and r[channel]>=0]
        return float(np.median(vals)) if vals else math.nan
    def trend(channel):
        recent=[r[channel] for r in prior[-12:] if r.get(channel) is not None and r[channel]>=0]
        earlier=[r[channel] for r in prior[-72:-12] if r.get(channel) is not None and r[channel]>=0]
        return math.log10((np.median(recent)+.01)/(np.median(earlier)+.01)) if recent and earlier else math.nan
    lon=event.get('longitude');lat=event.get('latitude');peak=event.get('peakFlux');rise=event.get('riseMinutes')
    return [math.log10(peak) if peak and peak>0 else math.nan,
            math.log1p(rise) if rise is not None and rise>=0 else math.nan,
            math.sin(math.radians(lon)) if lon is not None and math.isfinite(lon) else math.nan,
            math.cos(math.radians(lon)) if lon is not None and math.isfinite(lon) else math.nan,
            abs(lat)/90 if lat is not None and math.isfinite(lat) else math.nan,
            math.log10(last('P10')+.01),math.log10(last('P50')+.01),trend('P10'),trend('P50'),math.log1p(past_flares)]

def predict(values, fitted):
    x=np.asarray(values,dtype=float);missing=~np.isfinite(x)
    x=np.where(missing,np.array(fitted['median']),x)
    z=np.r_[(x-np.array(fitted['mean']))/np.array(fitted['scale']),missing.astype(float)]
    out={}
    for key,m in fitted['models'].items():
        raw=float(z@np.array(m['coef'])+m['intercept'])
        logit=raw*m.get('calSlope',1)+m.get('calIntercept',0)
        out[key]=float(1/(1+math.exp(-max(-40,min(40,logit)))))
    # Nested 10-MeV events must remain logically ordered.
    if 'p10_10' in out and 'p10_40' in out:out['p10_40']=min(out['p10_40'],out['p10_10'])
    return out
