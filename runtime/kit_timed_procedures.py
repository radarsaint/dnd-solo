"""Source-attested combat sorties, advanced only by committed combat rounds.

Host declarations interpret source semantics. Native state owns execution and replay.
Warning delivery is abstracted with departure; no recipient action is invented.
"""
import copy
from .state_context import require

FIELDS = {'id','kind','actor','destination_unit','destination_room','after_rounds','evidence'}
SCHEMA = {'type':'array','maxItems':8,'items':{'type':'object','additionalProperties':False,
 'required':sorted(FIELDS),'properties':{
 'id':{'type':'string'},'kind':{'type':'string','enum':['warn_and_return']},
 'actor':{'type':'string'},'destination_unit':{'type':'string'},'destination_room':{'type':'string'},
 'after_rounds':{'type':'integer','minimum':1,'maximum':20},
 'evidence':{'type':'object'}}}}

def validate(items,req,reading,check_quote):
    require(isinstance(items,list) and len(items)<=8,'Invalid timed procedure list')
    ids=set(); actors=set()
    for item in items:
        require(isinstance(item,dict) and set(item)==FIELDS,'Invalid timed procedure fields')
        key=item['id']; actor=item['actor']
        require(isinstance(key,str) and 0<len(key)<=60 and key not in ids,'Invalid or duplicate procedure id')
        require(item['kind']=='warn_and_return','Unsupported timed procedure kind')
        require(actor in reading['actors'] and reading['actors'][actor]['presence']=='present'
                and actor not in actors,'Timed procedure needs a distinct present actor')
        require(type(item['after_rounds']) is int and 1<=item['after_rounds']<=20,'Invalid return round delay')
        unit=req['units'].get(item['destination_unit']) or {}
        require(item['destination_unit']!='local' and unit.get('room_id')==item['destination_room']
                and bool(item['destination_room']),'Destination must name its indexed source dependency')
        check_quote(item['evidence'],req)
        require(item['evidence'] in reading['conditions'],'Procedure evidence must be a retained governing condition')
        ids.add(key);actors.add(actor)

def pending(fight):
    return [p for p in (fight or {}).get('source_procedures',[]) if p['status']=='away']

def actor_here(fight,key,actor,area):
    for p in (fight or {}).get('source_procedures',[]):
        if p['actor']!=key:continue
        if p['status']=='away':return False
        if p['status']=='returned' and actor.get('location')==p['away_location']:
            return p['origin']==area
    return actor.get('location')==area

def start(fight):
    declarations=fight.source.get('_timed_procedures') or []
    if not declarations:return
    fight.fight['source_procedures']=[]
    for declaration in declarations:
        key=declaration['actor']; actor=fight.state['actors'].get(key) or {}
        require(key in fight.fight['hp'] and fight.active(key),'Procedure actor cannot depart this encounter')
        item=copy.deepcopy(declaration)
        item.update(status='away',origin=actor['location'],started_round=1,
                    due_round=1+declaration['after_rounds'],away_location='away:'+declaration['destination_room'])
        fight.fight['source_procedures'].append(item)
        fight.lines.append('The '+fight.label(key)+' leaves the fight.')
        fight.trace.append('source procedure '+item['id']+': departure; warning; return due round '+str(item['due_round']))

def advance(fight):
    for item in pending(fight.fight):
        key=item['actor']; actor=fight.state['actors'].get(key) or {}
        # A later death, flight or relocation cancels the return; never overwrite it.
        allowed_locations={item['origin'],item['away_location']}
        if actor.get('status')!='alive' or fight.statuses.get(key, 'alive')!='alive' or \
                actor.get('location') not in allowed_locations or fight.fight['hp'].get(key,0)<=0:
            item['status']='cancelled'
        elif fight.fight['round']>=item['due_round']:
            item['status']='returned'
            fight.lines.append('The '+fight.label(key)+' returns to the fight.')
            fight.trace.append('source procedure '+item['id']+': returned at round '+str(fight.fight['round']))

def synchronize(state,source,combat):
    declared={p['id']:p for p in source.get('_timed_procedures') or []}
    schedules=combat.get('source_procedures') or []
    require(isinstance(schedules,list) and len(schedules)<=8,'Invalid combat procedure state')
    seen=set()
    for item in schedules:
        original=declared.get(item.get('id'))
        require(original and item['id'] not in seen and all(item.get(k)==v for k,v in original.items()),
                'Combat procedure differs from its source declaration')
        require(item.get('status') in ('away','returned','cancelled') and
                item.get('started_round')==1 and item.get('due_round')==1+original['after_rounds'] and
                item.get('away_location')=='away:'+original['destination_room'] and
                item.get('origin') in source['areas'],'Invalid procedure execution state')
        require(item['status']!='returned' or combat.get('round',0)>=item['due_round'],
                'Procedure returned before its deadline')
        seen.add(item['id']); actor=state['actors'][item['actor']]
        if item['status']=='away' and actor.get('status')=='alive' and actor.get('location')==item['origin']:
            actor['location']=item['away_location']
        elif item['status']=='returned' and actor.get('status')=='alive' and actor.get('location')==item['away_location']:
            actor['location']=item['origin']
        # Session-level ledger travels with the PC and survives destination revisits.
        warnings=state.setdefault('source_warnings',{})
        key=source['id']+'/'+item['id']
        record={'origin_room':source['id'],'destination_room':original['destination_room'],
                'actor':item['actor'],'procedure':item['id'],'evidence':copy.deepcopy(item['evidence']),
                'timing':'Warning abstracted at source-prescribed combat-start departure; no recipient action implied.'}
        require(key not in warnings or warnings[key]==record,'Conflicting source warning')
        warnings[key]=record

def warnings_here(state,room_id):
    return [copy.deepcopy(v) for v in (state.get('source_warnings') or {}).values()
            if v['destination_room']==room_id]
