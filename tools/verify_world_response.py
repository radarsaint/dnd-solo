"""Bounded verification: owned child, explicit timeout, durable receipt."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
NAMES=['test_kit_world_response','test_kit_source_ambush_gpt','test_kit_scene_contract_gpt',
       'test_kit_source_invariants','test_kit_combat_acts_acceptance','test_kit_combat_checkpoints',
       'test_kit_manifests','test_kit_moves_eval','test_kit_agenda','test_kit_turn_timing']
code="import sys,unittest; sys.path.insert(0,'tests'); suite=unittest.defaultTestLoader.loadTestsFromNames("+repr(NAMES)+"); result=unittest.TextTestRunner(verbosity=1).run(suite); sys.exit(not result.wasSuccessful())"
start=time.monotonic()
try:
    run=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],cwd=str(ROOT),capture_output=True,
                       text=True,encoding='utf-8',timeout=90,env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
    receipt={'exit_code':run.returncode,'timed_out':False,'stdout':run.stdout,'stderr':run.stderr}
except subprocess.TimeoutExpired as exc:
    receipt={'exit_code':None,'timed_out':True,'stdout':str(exc.stdout or ''),'stderr':str(exc.stderr or '')}
receipt.update(seconds=round(time.monotonic()-start,3),timeout_seconds=90,modules=NAMES,
               python=sys.version,paid_api_calls=0)
receipt['files']={}
for name in ['runtime/kit_world_response.py','runtime/kit_agent.py','runtime/kit_combat.py','runtime/kit_opening.py']:
    data=(ROOT/name).read_bytes()
    ast.parse(data.decode('utf-8-sig'),feature_version=(3,8))
    receipt['files'][name]=hashlib.sha256(data).hexdigest()
receipt['python38_syntax']='passed; not Python 3.8 execution'
out=ROOT.parent/'verification.json'
out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('stdout','stderr','files')},indent=2))
print(receipt['stderr'][-5000:])
sys.exit(1 if receipt['timed_out'] or receipt['exit_code'] else 0)
