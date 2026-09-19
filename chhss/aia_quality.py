"""Interpret the actual Level-1 quality definition, not HMI observable flags."""
import re
URL='http://jsoc.stanford.edu/doc/data/hmi/Quality_Bits/quallev1.h'
def validate(acq,q):
    if q==0:return {'quality':0,'flags':[]}
    if q!=0x40000000:raise ValueError(f'AIA NRT quality {q:#x}: non-informational flags rejected')
    path,source=acq.download(URL,'quality/quallev1.h')
    text=path.read_text()
    lines=[line for line in text.splitlines() if 'NRT' in line.upper() and re.search(r'0x40000000\b',line,re.I)]
    if not lines:raise ValueError('Cannot verify informational NRT flag from the official Level-1 definition')
    return {'quality':q,'flags':['NRT processing'],'definition':lines,'definitionSource':source}
