"""WXF pre-flare context; this is not NOAA's event termination definition."""
import math

POLICY='WXF-preflare-24h-v1'

def channel_context(prior, channel):
    """288 regular five-minute slots strictly before the flare peak; missing stays unknown."""
    valid=[isinstance(r.get(channel),(int,float)) and math.isfinite(r[channel]) and r[channel]>=0 for r in prior]
    above=[ok and r[channel]>=10 for r,ok in zip(prior,valid)]
    sustained=any(all(above[i:i+3]) for i in range(len(above)-2))
    gap=longest=0
    for ok in valid:
        gap=0 if ok else gap+1;longest=max(longest,gap)
    complete=len(prior)==288 and sum(valid)/288>=.95 and longest<=6
    status='recent' if sustained else 'clear' if complete else 'unknown'
    last=next((r.get('time') for r,yes in reversed(list(zip(prior,above))) if yes),None)
    return dict(status=status,coverage=sum(valid)/288,maxGapMinutes=longest*5,lastAbove=last)
