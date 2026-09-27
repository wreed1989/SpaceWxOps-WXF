#!/usr/bin/env python3
"""Publish only the esa-live data branch; never modify main or other branches."""
from __future__ import annotations
import base64,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from validate_products import validate
REPO='wreed1989/SpaceWxOps-WXF'
BRANCH='esa-live'
REMOTE='https://github.com/'+REPO+'.git'
ROOT=Path(os.environ.get('ESA_OUTPUT_DIR','esa-live-output'))

def git(args,cwd=None,env=None,check=True):
 r=subprocess.run(['git',*args],cwd=cwd,env=env,capture_output=True,text=True,timeout=180)
 if check and r.returncode:raise RuntimeError('git_'+args[0]+'_failed')
 return r

def head():
 r=git(['ls-remote','--heads',REMOTE,'refs/heads/'+BRANCH])
 lines=r.stdout.strip().splitlines()
 if not lines:return ''
 parts=lines[0].split()
 if len(parts)!=2 or parts[1]!='refs/heads/'+BRANCH or len(parts[0])!=40:raise RuntimeError('unexpected_branch_ref')
 return parts[0]

def copy_bundle(source,target):
 target.mkdir(parents=True,exist_ok=True)
 for name in ('latest.json','health.json','README.md'):
  f=source/name
  if f.is_file() and not f.is_symlink():shutil.copy2(f,target/name)
 assets=source/'assets'
 if assets.is_dir() and not assets.is_symlink():
  (target/'assets').mkdir(exist_ok=True)
  for f in assets.iterdir():
   if f.is_file() and not f.is_symlink() and __import__('harvest').ASSET_RE.fullmatch('assets/'+f.name):shutil.copy2(f,target/'assets'/f.name)

def restore():
 if ROOT.exists() and any(ROOT.iterdir()):raise RuntimeError('restore_destination_not_empty')
 if not head():print('No previous solar cache; initial collection will create it.');return
 with tempfile.TemporaryDirectory() as tmp:
  git(['clone','--quiet','--depth','1','--single-branch','--branch',BRANCH,REMOTE,tmp+'/cache'])
  copy_bundle(Path(tmp)/'cache',ROOT)
 print('Restored previous passive solar cache.')

def publish():
 if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise RuntimeError('unexpected_repository')
 if os.environ.get('GITHUB_REF_NAME') not in ('main','esa-product-delivery'):raise RuntimeError('unapproved_source_branch')
 if os.environ.get('GITHUB_EVENT_NAME') not in ('push','workflow_dispatch','schedule'):raise RuntimeError('unapproved_trigger')
 validate(ROOT)
 token=os.environ.get('GITHUB_TOKEN','')
 if not token:raise RuntimeError('missing_publication_token')
 # The ESA credentials are not passed to this process or stored in git config.
 if os.environ.get('ESAID') or os.environ.get('ESASECRET'):raise RuntimeError('provider_credentials_in_publication_process')
 expected=head()
 with tempfile.TemporaryDirectory() as tmp:
  work=Path(tmp)/'cache';copy_bundle(ROOT,work)
  git(['init','--quiet','--initial-branch='+BRANCH],work)
  git(['config','user.name','github-actions[bot]'],work)
  git(['config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],work)
  git(['add','--','latest.json','health.json','README.md','assets'],work)
  stamp=json.loads((work/'latest.json').read_text())['checked_at']
  git(['commit','--quiet','-m','Refresh passive solar products '+stamp],work)
  # This branch is an explicitly rolling cache, not a source/history branch.
  credential=base64.b64encode(('x-access-token:'+token).encode()).decode()
  if os.environ.get('GITHUB_ACTIONS')=='true':print('::add-mask::'+credential,flush=True)
  env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0';env['GIT_CONFIG_COUNT']='1'
  env['GIT_CONFIG_KEY_0']='http.https://github.com/.extraheader';env['GIT_CONFIG_VALUE_0']='AUTHORIZATION: basic '+credential
  git(['push','--quiet','--force-with-lease=refs/heads/'+BRANCH+':'+expected,REMOTE,'HEAD:refs/heads/'+BRANCH],work,env)
  sha=git(['rev-parse','HEAD'],work).stdout.strip()
  report={'repository':REPO,'branch':BRANCH,'commit':sha,'checked_at':stamp,'source_commit':os.environ.get('GITHUB_SHA'),'manifest_url':'https://raw.githubusercontent.com/'+REPO+'/'+BRANCH+'/latest.json'}
  Path('esa-publication.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':
 try:
  if sys.argv[1:] == ['--restore']:restore()
  elif not sys.argv[1:]:publish()
  else:raise RuntimeError('unsupported_arguments')
 except Exception as e:print('Solar publication stopped:',type(e).__name__,str(e)[:120]);sys.exit(1)
