#!/usr/bin/env python3
"""Focused, credential-free diagnostics for actual provider response quirks."""
from __future__ import annotations
import json
import os
import re
import sys
import unittest
import urllib.parse as U
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import check_access as m

# Remove (never load) only standard W3C external SVG DTD declarations.
# Internal subsets, custom declarations and entities remain forbidden.
SVG_DTD = re.compile(rb'<!DOCTYPE\s+svg\s+PUBLIC\s+([\"\'])-//W3C//DTD SVG 1\.[01]//EN\1\s+([\"\'])https?://www\.w3\.org/(?:Graphics/SVG/1\.1/DTD/svg11\.dtd|TR/2001/REC-SVG-20010904/DTD/svg10\.dtd)\2\s*>', re.I)

def strip_svg_dtd(body: bytes) -> bytes:
    if b'<!ENTITY' in body.upper():
        raise m.SafeError('xml_entities_rejected')
    clean, count = SVG_DTD.subn(b'', body)
    if count > 1 or b'<!DOCTYPE' in clean.upper():
        raise m.SafeError('nonstandard_dtd_rejected')
    return clean


def kso_scope(r: m.Response) -> str:
    if r.status not in (301,302,303,307,308):
        raise m.SafeError('no_login_redirect')
    u=U.urlsplit(r.headers.get('location',''))
    if u.scheme!='https' or u.hostname!='sso.s2p.esa.int' or u.path!='/realms/swe/protocol/openid-connect/auth' or u.username or u.password or u.port not in (None,443):
        raise m.SafeError('untrusted_login_redirect')
    q=U.parse_qs(u.query)
    if len(q.get('client_id',[]))!=1 or len(q.get('redirect_uri',[]))!=1:
        raise m.SafeError('ambiguous_login_redirect')
    scope=q['client_id'][0]
    callback=U.urlsplit(q['redirect_uri'][0])
    if callback.scheme!='https' or callback.hostname!='sso.kso.ac.at' or callback.username or callback.password or callback.port not in (None,443) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}',scope):
        raise m.SafeError('untrusted_resource_scope')
    if scope in {'swe_hapiserver','swe_contentproxy'}:
        raise m.SafeError('unexpected_kso_scope')
    return scope


def stamp_summary(body: bytes, xml: bool=False) -> dict:
    values={}
    def note(key,value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,30}',key):return
        if not re.fullmatch(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d{1,9})?)?(?:Z|[+-]\d\d:\d\d)?',value):return
        values.setdefault(key,set()).add(value)
    if xml:
        root=ET.fromstring(body)
        for el in root.iter():
            tag=el.tag.split('}')[-1]
            if tag in {'issuetime','begin','end'}:
                note(tag,el.get('time') or (el.text or '').strip())
    else:
        def walk(v):
            if isinstance(v,list):
                for x in v[:3000]:walk(x)
            elif isinstance(v,dict):
                for k,x in v.items():
                    if any(w in k.lower() for w in ('time','date')):note(k,x)
                    if isinstance(x,(dict,list)):walk(x)
        walk(json.loads(body))
    return {k:{'earliest':min(v),'latest':max(v)} for k,v in values.items()}


def run():
    client=m.M2M(os.environ.get('ESAID',''),os.environ.get('ESASECRET',''))
    results=[]
    token=client.token('swe_contentproxy')
    urls={name:(url,kind,scope) for name,url,kind,scope in m.targets(datetime.now(timezone.utc))}
    for name in ['SIDC Solarmap','SIDC Coronal Holes','SIDC Coronal-Hole Runs','SIDC Flare Forecast','EUHFORIA Provider View']:
        url,kind,scope=urls[name]
        entry={'name':name}
        try:
            r=m.exchange(url,bearer=token,scope=scope)
            if name=='SIDC Solarmap' and r.status==200:
                clean=strip_svg_dtd(r.body)
                entry['standard_svg_doctype_removed']=clean!=r.body
                entry.update(m.inspect_response(m.Response(r.status,r.headers,clean),'svg'))
                if entry['status']=='readable_svg':
                    root=ET.fromstring(clean)
                    refs=[e.get('href') or e.get('{http://www.w3.org/1999/xlink}href','') for e in root.iter() if e.tag.split('}')[-1]=='image']
                    entry['images']={'embedded':sum(x.startswith('data:image/') for x in refs),'external':sum(not x.startswith('data:image/') for x in refs),'external_hosts':sorted({U.urlsplit(U.urljoin(url,x)).hostname for x in refs if not x.startswith('data:image/')})}
            else:
                entry.update(m.inspect_response(r,kind))
                if entry['status'] in {'readable_json','readable_xml'}:entry['provider_times']=stamp_summary(r.body,kind=='xml')
                if name=='EUHFORIA Provider View' and entry['status']=='provider_page_only':
                    # Only same-origin public-path image filenames, never auth/session queries.
                    refs=re.findall(r'(?:src|href)\s*=\s*[\"\']([^\"\']+)[\"\']',r.body.decode('utf-8','replace'),re.I)
                    images=[]
                    for ref in refs:
                        u=U.urlsplit(U.urljoin(url,ref))
                        if u.scheme=='https' and u.hostname==U.urlsplit(url).hostname and re.fullmatch(r'/[A-Za-z0-9_./%-]+\.(?:gif|png|jpg|jpeg|mp4|webm)',u.path,re.I):images.append(u.path)
                    entry['same_origin_media_paths']=sorted(set(images))[:20]
        except m.SafeError as e:entry['status']=str(e)
        except Exception:entry['status']='response_inspection_failed'
        results.append(entry)
    url=urls['KSO H-Alpha'][0]
    entry={'name':'KSO H-Alpha Scoped Authentication'}
    try:
        r=m.exchange(url)
        scope=kso_scope(r)
        entry['resource_scope']=scope
        m.AUTH_HOSTS['sso.kso.ac.at']=scope
        m.ALLOWED_SCOPES.add(scope)
        ktoken=client.token(scope)
        entry['authentication']='token_issued'
        r=m.exchange(url,bearer=ktoken,scope=scope)
        entry.update(m.inspect_response(r,'kso'))
        if entry['status']=='image_url_received':
            target=r.body.decode().strip().strip('\"')
            u=U.urlsplit(target)
            if u.hostname=='sso.kso.ac.at' and u.path.startswith('/prod/') and not u.query and not u.fragment:
                entry['image_fetch']=m.inspect_response(m.exchange(target,bearer=ktoken,scope=scope),'image')['status']
    except m.SafeError as e:entry['status']=str(e)
    except Exception:entry['status']='response_inspection_failed'
    results.append(entry)
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'products':results,'notice':'No credentials, tokens, cookies or bulk provider payloads. Access checks are not dashboard deployment.'}
    serialized=json.dumps(report,indent=2)
    for secret in [client.client,client.secret]+[v[0] for v in client.tokens.values()]:
        if secret:serialized=serialized.replace(secret,'[REDACTED]').replace(json.dumps(secret)[1:-1],'[REDACTED]')
    out=Path(os.environ.get('ESA_REPORT_DIR','esa-access-report'));out.mkdir(parents=True,exist_ok=True)
    (out/'esa_followup_report.json').write_text(serialized+'\n')
    rows=['# ESA Product Follow-Up','','| Product | Result |','| --- | --- |']
    for x in json.loads(serialized)['products']:rows.append(f"| {x['name']} | {x.get('status','unknown')} |")
    text='\n'.join(rows)+'\n';(out/'esa_followup_report.md').write_text(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('\n'+text)
    print(text)


class SafetyTests(unittest.TestCase):
    def test_standard_svg_declaration_removed(self):
        self.assertEqual(strip_svg_dtd(b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg/>'),b'<svg/>')
    def test_internal_subset_and_unknown_host_rejected(self):
        for b in [b'<!DOCTYPE svg [<!ENTITY x "boom">]><svg/>',b'<!DOCTYPE svg SYSTEM "http://evil.test/x"><svg/>',b'<!DOCTYPE html><html/>']:
            with self.assertRaises(m.SafeError):strip_svg_dtd(b)
    def test_normal_xml_unchanged(self):
        self.assertEqual(strip_svg_dtd(b'<svg/>'),b'<svg/>')
    def test_scope_bound_to_kso(self):
        base='https://sso.s2p.esa.int/realms/swe/protocol/openid-connect/auth?'
        q=U.urlencode({'client_id':'fixture-kso','redirect_uri':'https://sso.kso.ac.at/callback'})
        self.assertEqual(kso_scope(m.Response(302,{'location':base+q},b'')),'fixture-kso')
        with self.assertRaises(m.SafeError):kso_scope(m.Response(302,{'location':base+q.replace('sso.kso.ac.at','evil.test')},b''))
    def test_metadata_only_times(self):
        r=stamp_summary(b'{"ImageTime":"2026-09-27T00:00:00Z","label":"private"}')
        self.assertEqual(r['ImageTime']['latest'],'2026-09-27T00:00:00Z')
        self.assertNotIn('private',json.dumps(r))


if __name__=='__main__':
    if '--self-test' in sys.argv:unittest.main(argv=[sys.argv[0]])
    else:
        try:run()
        except m.SafeError as e:print('Follow-up unavailable: '+str(e));sys.exit(1)
        except Exception:print('Follow-up stopped without logging sensitive exception details.');sys.exit(2)
