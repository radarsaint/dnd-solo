"""Record the same public bridge journey under four explicit host choices."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_kit_world_response import WorldResponse

results=[]
for choice in ['baseline','wait','reveal','start_combat']:
    case=WorldResponse('test_baseline_commits_stone_without_world_response')
    case.setUp()
    try:
        case.setup_scene(choice!='baseline')
        packet=case.prepare()
        output=case.output(packet,'wait' if choice=='baseline' else choice,
                           [] if choice in ('baseline','wait') else None)
        if choice=='baseline':output['decision'].pop('world_response')
        result=case.bridge.complete(packet['turn_id'],output)
        revision,state=case.runtime.load()
        results.append({'choice':choice,'decision_source':'explicitly authored host decision; no independent model',
                        'player_action':packet['input']['private']['player_action'],
                        'offered':packet['input']['private'].get('world_response'),
                        'decision':output['decision'].get('world_response'),
                        'spoken':result['spoken'],'revision':revision,
                        'actors':state['actors'],'combat':state.get('combat')})
    finally:
        case.doCleanups()
out=Path(__file__).resolve().parents[2]/'behavior-comparison.json'
out.write_text(json.dumps(results,indent=2),encoding='utf-8')
for item in results:
    print(json.dumps({k:item[k] for k in ('choice','spoken','combat')},ensure_ascii=False))
