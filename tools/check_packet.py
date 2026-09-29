#!/usr/bin/env python3
"""Check a G3/G4 packet for freshness and completeness (v18).

Checks: source SHA matches now, every evidence file exists with its recorded sha256, independent review
PASS at the same SHA by an instance that did not author the change, no open BLOCKER, every open
SHOULD-FIX carries a complete unexpired exception signed by Cecilia, and for G4 the artifact digest,
environment and config identity match. It checks structure, not truth: it cannot prove a log is honest
or that a human really approved. Protected branches and environments stay the authority.
"""
import argparse, datetime, hashlib, json, sys
from pathlib import Path

def check(packet,current_sha,root,current_digest=None,current_environment=None,current_config=None):
 errors=[];root=Path(root).resolve()
 for field in ('gate','task_id','source_sha','prepared_by','evidence','review'):
  if not packet.get(field):errors.append('missing '+field)
 if packet.get('gate') not in ('G3','G4'):errors.append('only G3/G4 supported')
 if packet.get('source_sha')!=current_sha:errors.append('stale source SHA')
 review=packet.get('review',{})
 if review.get('verdict')!='PASS':errors.append('independent review not PASS')
 if not review.get('instance') or review.get('instance') in packet.get('author_instances',[]):errors.append('reviewer independence missing')
 if review.get('source_sha')!=current_sha:errors.append('review SHA mismatch')
 # Role/instance fields are declarations. Identity must be checked in host/PR audit.
 for e in packet.get('evidence',[]):
  if e.get('source_sha')!=current_sha:errors.append('evidence SHA mismatch')
  if not e.get('id') or not e.get('method') or not e.get('timestamp_utc'):errors.append('evidence metadata missing')
  if e.get('required',True) and e.get('result')!='PASS':errors.append('required evidence not PASS')
  rel=e.get('path','');p=(root/rel).resolve()
  if not rel or Path(rel).is_absolute() or not p.is_relative_to(root):errors.append('evidence path escapes root');continue
  if not p.is_file():errors.append('evidence file missing');continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=e.get('sha256'):errors.append('evidence hash mismatch')
 for f in packet.get('findings',[]):
  if f.get('status')=='closed':continue
  if f.get('severity')=='BLOCKER':errors.append('open blocker')
  if f.get('severity') in ('SHOULD-FIX','MAJOR'):
   ex=f.get('exception',{})
   if not all(ex.get(k) for k in ('human_owner','rationale','mitigation','expires','approval_ref')):errors.append('SHOULD-FIX exception incomplete')
   else:
    try:
     expiry=datetime.datetime.fromisoformat(ex['expires'].replace('Z','+00:00'))
     if expiry.tzinfo is None or expiry<=datetime.datetime.now(datetime.timezone.utc):errors.append('SHOULD-FIX exception expired/naive')
    except ValueError:errors.append('invalid exception expiry')
 if packet.get('gate')=='G4':
  for k in ('artifact_digest','environment','config_identity','rollback_evidence','staging_evidence','human_trigger_ref'):
   if not packet.get(k):errors.append('release missing '+k)
  for key,current in [('artifact_digest',current_digest),('environment',current_environment),('config_identity',current_config)]:
   if not current or packet.get(key)!=current:errors.append('release identity mismatch '+key)
  for key in ('artifact_digest','environment','config_identity'):
   if review.get(key)!=packet.get(key):errors.append('release review mismatch '+key)
  ids={e.get('id'):e for e in packet.get('evidence',[])}
  for k in ('rollback_evidence','staging_evidence'):
   e=ids.get(packet.get(k))
   if not e or e.get('result')!='PASS':errors.append('release evidence missing/not PASS '+k)
   elif e.get('artifact_digest')!=current_digest or not e.get('environment'):errors.append('release evidence identity incomplete '+k)
 return errors


def _utf8_console() -> None:
    """Windows consoles default to a legacy code page; keep output readable and crash-free."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

def main():
 _utf8_console()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('packet');p.add_argument('--sha',required=True);p.add_argument('--evidence-root',required=True)
 p.add_argument('--digest');p.add_argument('--environment');p.add_argument('--config');a=p.parse_args()
 try:
  errors=check(json.loads(Path(a.packet).read_text(encoding="utf-8-sig")),a.sha,a.evidence_root,a.digest,a.environment,a.config)
  print(json.dumps({'result':'FAIL' if errors else 'STRUCTURALLY_VALID','errors':errors,'limits':'Not approval, authenticity, raw evidence interpretation, or release authorization'},indent=2))
  return bool(errors)
 except (OSError,ValueError,TypeError,KeyError) as e:print('ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
