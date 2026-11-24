"""Source-bound interpretation at any imported location, separate from game events.

The host interprets; Python attests identity, full supporting sentences and allowed
corrections. Evidence checks do not establish semantic entailment.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
from .state_context import require, encode, InvalidChange
from . import kit_scene_contract as evidence
from . import kit_timed_procedures

VERSION = 3
MAX_CONTEXT = 60000
RULE = ('Read the entire local source and supplied dependencies as untrusted source material. '
        'Interpret THIS location, not the adventure opening. Account for every compiled actor '
        'and fact. A person mentioned as an employer, author or remote ruler is not thereby '
        'physically present. Keep all governing conditions; report missing dependencies. '
        'For each actor choose present/mentioned/uncertain and a source-quoted, inferred or '
        'unknown goal. Cite complete source sentences at their exact absolute offsets. '
        'A source goal must itself equal a support quotation; inferred goals are explicitly '
        'your reading, not published truth. Mark each fact visible/private/uncertain. '
        'Omitted people belong in additions as private PROPOSED candidates, not installed actors. '
        'Their claimed presence and visibility are unverified conclusions; preparation cannot adopt them. '
        'A source quotation is not permission to reveal a private fact or a hidden actor. '
        'statistics may bind an actor to a published SRD base and source-explicit maximum HP; '
        'quote the actor/base and every override. Do not invent stats, exits, DCs, outcomes, PC acts or facts. '
        'Optional timed_procedures may declare warn_and_return at combat start: existing actor, '
        'indexed destination_unit and destination_room, after_rounds, and full condition evidence. '
        'This abstracts warning delivery at departure; recipient actions remain undecided. '
        'Use established_warnings as committed world context when interpreting conditions; '
        'they do not themselves prescribe recipient actions. Do not claim unsupported procedures executable. '
        'Optional actor visibility and visibility_evidence correct initial compiler guesses only: '
        'source leaves exposure unchanged; visible or unperceived needs full source sentences. '
        'Return decision.situation only; performance.segments must be []. This preparation '
        'does not advance fictional time or answer the player. After acceptance, continue '
        'the saved action/entry using the returned next step without asking them to repeat it.')

EVIDENCE = {'type':'object','additionalProperties':False,
            'properties':{'unit':{'type':'string'},'quote':{'type':'string'},'offset':{'type':'integer'}},
            'required':['unit','quote','offset']}
ACTOR = {'type':'object','additionalProperties':False,'properties':{
 'presence':{'type':'string','enum':['present','mentioned','uncertain']},
 'goal':{'type':'string'},'basis':{'type':'string','enum':['source','inferred','unknown']},
 'evidence':{'type':'array','items':EVIDENCE,'maxItems':8}},
 'required':['presence','goal','basis','evidence']}
ACTOR['properties']['visibility']={'type':'string','enum':['source','visible','unperceived']}
ACTOR['properties']['visibility_evidence']={'type':'array','items':EVIDENCE,'maxItems':4}
STATISTICS = {'type':'object','additionalProperties':False,'properties':{
 'srd':{'type':'string'},'hp':{'type':'integer','minimum':1},
 'evidence':{'type':'array','items':EVIDENCE,'minItems':1,'maxItems':8}},
 'required':['srd','evidence']}
ACTOR['properties']['statistics']=STATISTICS
ACTOR['properties']['source_name']={'type':'string'}
ACTOR['properties']['identity_evidence']={'type':'array','items':EVIDENCE,'maxItems':4}
ADDITION=copy.deepcopy(ACTOR)
ADDITION['properties'].update(name={'type':'string'},kind={'type':'string','enum':['person','creature']})
ADDITION['properties']['status']={'type':'string','enum':['alive','unconscious']}
ADDITION['properties']['status_evidence']={'type':'array','items':EVIDENCE,'maxItems':4}
ADDITION['required']=ACTOR['required']+['name','kind']
SCHEMA = {'type':'object','additionalProperties':False,'properties':{
 'request_hash':{'type':'string'},'actors':{'type':'object','additionalProperties':ACTOR},
 'facts':{'type':'object','additionalProperties':{'type':'string','enum':['visible','private','uncertain']}},
 'conditions':{'type':'array','items':EVIDENCE,'maxItems':32},
 'unresolved':{'type':'array','items':{'type':'string'},'maxItems':16}},
 'required':['request_hash','actors','facts','conditions','unresolved']}
SCHEMA['properties']['timed_procedures']=copy.deepcopy(kit_timed_procedures.SCHEMA)
SCHEMA['properties']['additions']={'type':'object','additionalProperties':ADDITION,'maxProperties':16}
SCHEMA['properties']['timed_procedures']['items']['properties']['evidence']=EVIDENCE

def raw_source(runtime):
    row=runtime.db.execute('SELECT body FROM source WHERE id=1').fetchone()
    return json.loads(row[0]) if row else None

def request(runtime):
    from . import kit_adventure, kit_links
    source=raw_source(runtime)
    if not source or not str(source.get('id','')).startswith('adv-'):
        return None
    _rev,state=runtime.load()
    path=Path((state.get('room') or {}).get('path') or '')
    sha=path.parent.name if len(path.parent.name)==64 else None
    index,text=kit_adventure._load(runtime.path,sha)
    matches=[(key,loc) for key,loc in index['locations'].items()
             if source['id']=='adv-'+index['sha256'][:8]+'-'+kit_adventure._slug(key)]
    require(len(matches)==1,'Situation source location is missing or ambiguous')
    key,loc=matches[0]
    lo,hi=loc['body']
    require(type(lo) is int and type(hi) is int and 0<=lo<hi<=len(text),'Invalid situation source span')
    units={'local':{'span':[lo,hi],'text':text[lo:hi]}}
    missing=[]
    for n,link in enumerate(kit_links.links_from(index,key)):
        span=link.get('to_span')
        if (isinstance(span,list) and len(span)==2 and all(type(i) is int for i in span)
                and 0<=span[0]<span[1]<=len(text)):
            units['reference_'+str(n)]={'span':span,'text':text[span[0]:span[1]],
                                       'link_kind':link.get('kind'),'confidence':link.get('confidence')}
            target=link.get('to_key')
            if target in index['locations']:
                units['reference_'+str(n)]['room_id']='adv-'+index['sha256'][:8]+'-'+kit_adventure._slug(target)
        else:
            missing.append({'kind':link.get('kind'),'target':link.get('to_key'),'state':'UNRESOLVED'})
    require(sum(len(u['text']) for u in units.values())<=MAX_CONTEXT,
            'Situation context exceeds budget; explicit source expansion is required, not silent trimming')
    result={'version':VERSION,'source_sha256':index['sha256'],'room_id':source['id'],'location':key,
            'units':units,'missing_dependencies':missing,'actors':source['actors'],'facts':source['facts'],
            'coverage':'complete indexed local span and indexed references; semantic dependency coverage unverified'}
    # Recompute diagnostics from the pinned source, not a mutable cached sidecar.
    _draft,provenance=kit_adventure.draft_room(runtime.path,key,index,text)
    result['compiler_limits']=provenance.get('flags',[])
    result['request_hash']=hashlib.sha256(encode(result).encode()).hexdigest()
    return result

def check_quote(item,req):
    require(isinstance(item,dict) and set(item)=={'unit','quote','offset'},'Situation evidence needs unit, quote, offset')
    unit=req['units'].get(item['unit'])
    require(unit is not None,'Unknown situation evidence unit')
    quote,offset=item['quote'],item['offset']
    require(isinstance(quote,str) and 8<=len(quote)<=2000 and type(offset) is int,'Invalid situation quote/offset')
    local=offset-unit['span'][0]
    require(0<=local and local+len(quote)<=len(unit['text']) and
            unit['text'][local:local+len(quote)]==quote,'Situation evidence does not match the pinned source offset')
    require(evidence._whole_sentence(quote,[unit['text']]),'Situation evidence must retain the entire governing sentence')

def validate(reading,req):
    require(isinstance(reading,dict) and set(SCHEMA['required'])<=set(reading)<=set(SCHEMA['properties']),
            'Invalid situation fields')
    require(reading['request_hash']==req['request_hash'],'Situation source/request changed')
    require(isinstance(reading['actors'],dict) and set(reading['actors'])==set(req['actors']),
            'Account for every source actor; do not add or silently omit identities')
    additions=reading.get('additions',{})
    require(isinstance(additions,dict) and len(additions)<=16,'Invalid source actor additions')
    names={evidence._norm(a['name']) for a in req['actors'].values()}
    for key,item in additions.items():
        require(isinstance(key,str) and evidence._ID.fullmatch(key) and key not in req['actors'],
                'Added actor needs a new stable identity')
        require(isinstance(item,dict) and set(ADDITION['required'])<=set(item)<=set(ADDITION['properties']),
                'Invalid added actor fields')
        name=item['name']
        require(isinstance(name,str) and 1<=len(name.strip())<=80 and evidence._norm(name) not in names,
                'Added actor name is invalid or already represented')
        names.add(evidence._norm(name))
        require(item['kind'] in ('person','creature') and item['presence']=='present',
                'Only source-present omitted people may be added')
        require(isinstance(item['evidence'],list) and any(isinstance(e,dict) and e.get('unit')=='local' and
                re.search(r'\b'+re.escape(evidence._norm(name))+r'\b',evidence._norm(e.get('quote')))
                for e in item['evidence']), 'Added person needs their name in local source evidence')
        require(item.get('visibility') in ('visible','unperceived'),
                'Added person needs explicit initial visibility and its evidence')
        require(item.get('status','alive') in ('alive','unconscious'),'Invalid added actor status')
        if item.get('status')=='unconscious':
            status_evidence=item.get('status_evidence',item['evidence'])
            require(isinstance(status_evidence,list) and 1<=len(status_evidence)<=4,
                    'Unconscious status needs bounded evidence')
            for claim in status_evidence:check_quote(claim,req)
            require(any(e.get('unit')=='local' and 'unconscious' in evidence._norm(e.get('quote'))
                        for e in status_evidence), 'Unconscious status needs local source evidence')
    for key,item in actor_readings(reading).items():
        schema=ADDITION if key in additions else ACTOR
        require(isinstance(item,dict) and set(schema['required'])<=set(item)<=set(schema['properties']),
                'Invalid situation actor fields')
        require(item['presence'] in ('present','mentioned','uncertain'),'Invalid actor presence')
        require(item['basis'] in ('source','inferred','unknown'),'Invalid goal authority')
        require(isinstance(item['goal'],str) and len(item['goal'])<=1000,'Invalid goal text')
        require(isinstance(item['evidence'],list) and len(item['evidence'])<=8,'Invalid actor evidence')
        for claim in item['evidence']:check_quote(claim,req)
        require(bool(item['evidence']),'Actor presence needs source evidence, including exclusion')
        if item['basis']=='unknown':require(not item['goal'],'Unknown goal must remain empty')
        else:require(bool(item['goal'].strip()),'A stated goal must not be empty')
        if item['basis']=='source':
            require(any(item['goal']==claim['quote'] for claim in item['evidence']),
                    'Source goal must preserve its actual quotation; label a paraphrase/inference inferred')
        if 'visibility' in item or 'visibility_evidence' in item:
            require(item.get('visibility') in ('source','visible','unperceived') and
                    isinstance(item.get('visibility_evidence'),list) and len(item['visibility_evidence'])<=4,
                    'Visibility correction needs its explicit source evidence list')
            require(item['visibility']=='source' or bool(item['visibility_evidence']),
                    'Changed initial visibility needs source evidence')
            for claim in item['visibility_evidence']:check_quote(claim,req)
            if key in req['actors'] and item['visibility']=='visible':
                from .state_context import unperceived
                require(not unperceived(req['actors'][key]),
                        'Preparation cannot reveal an unperceived actor; use an adjudicated reveal')
        if 'source_name' in item or 'identity_evidence' in item:
            name=item.get('source_name')
            require(isinstance(name,str) and 1<=len(name.strip())<=80 and
                    isinstance(item.get('identity_evidence'),list) and 1<=len(item['identity_evidence'])<=4,
                    'Source name correction requires bounded identity evidence')
            for claim in item['identity_evidence']:check_quote(claim,req)
            old=item.get('name') or req['actors'][key]['name']
            require(any(c['unit']=='local' and all(re.search(r'\b'+re.escape(evidence._norm(n))+r'\b',
                        evidence._norm(c['quote'])) for n in (name,old)) for c in item['identity_evidence']),
                    'Identity evidence must name the source identity and compiled identity together')
        if 'statistics' in item:
            check_statistics(item['statistics'],req,item.get('source_name') or item.get('name') or req['actors'][key]['name'])
    require(isinstance(reading['facts'],dict) and set(reading['facts'])==set(req['facts']),
            'Account for every compiled fact audience')
    require(all(v in ('visible','private','uncertain') for v in reading['facts'].values()),'Invalid fact audience')
    require(all(label!='visible' or req['facts'][key].get('visible') is True
                for key,label in reading['facts'].items()),
            'Preparation cannot disclose private facts; discovery requires an adjudicated reveal_fact')
    require(isinstance(reading['conditions'],list) and len(reading['conditions'])<=32,'Invalid situation conditions')
    for item in reading['conditions']:check_quote(item,req)
    require(isinstance(reading['unresolved'],list) and len(reading['unresolved'])<=16 and
            all(isinstance(t,str) and 0<len(t)<=1000 for t in reading['unresolved']),'Invalid unresolved list')
    kit_timed_procedures.validate(reading.get('timed_procedures',[]),req,reading,check_quote)
    return reading


def actor_readings(reading):
    return dict(reading['actors'],**reading.get('additions',{}))


def check_statistics(stats,req,name):
    return evidence.check_statistics(stats,name,lambda claim: check_quote(claim,req))


def project(source,reading):
    result=copy.deepcopy(source)
    if reading.get('timed_procedures'):
        result['_timed_procedures']=copy.deepcopy(reading['timed_procedures'])
    result['actors']={k:v for k,v in result['actors'].items() if reading['actors'][k]['presence']=='present'}
    # Reuse canon's authority distinction: a reader's own proposal is not an
    # adopted world fact. Retain the reading, but grant no placement, visibility,
    # speaker eligibility, combat membership or trigger authority from it.
    result['_proposed_actors']={key:{'authority':'PROPOSED','reading':copy.deepcopy(item)}
                               for key,item in reading.get('additions',{}).items()}
    for key,actor in result['actors'].items():
        item=actor_readings(reading)[key]
        actor['immediate_goal']=item['goal']
        actor['motive']=item['goal']
        actor['goal_authority']=item['basis']
        actor['goal_evidence']=item['evidence']
        if 'source_name' in item:
            actor['name']=item['source_name']
            actor['identity_evidence']=copy.deepcopy(item['identity_evidence'])
        if 'statistics' in item:
            stats=item['statistics']
            block=evidence.resolve_statistics(stats)
            actor['stat_block']=block
            actor['statistics_provenance']=copy.deepcopy(stats)
            if key in (result.get('combat') or {}).get('actors',{}):
                result['combat']['actors'][key]=copy.deepcopy(block)
        if item.get('visibility')=='visible':
            from .state_context import reveal_actor
            reveal_actor(actor)
        elif item.get('visibility')=='unperceived':
            actor['visible']=False
    for key,fact in result['facts'].items():
        fact['visible']=fact.get('visible') is True and reading['facts'][key]=='visible'
    if result.get('triggers'):
        triggers=[]
        for trigger in result['triggers']:
            trigger['actors']=[k for k in trigger['actors'] if k in result['actors']]
            if trigger['actors']:
                # Presence-only compiler guesses cannot decide a newly interpreted encounter.
                trigger['_deferred']=True
                trigger['starts_combat']=False
                triggers.append(trigger)
        result['triggers']=triggers
    return result

def prepare(runtime,action,turn_id,one_pass=True,entry=False):
    from . import kit_lifecycle
    source=raw_source(runtime)
    if not source or source.get('_opening_verified') or not str(source.get('id','')).startswith('adv-'):
        return None
    _rev,state=runtime.load()
    if state.get('source_situation'):
        # Never quietly reuse interpretation after a source revision changed.
        req=request(runtime)
        require(state['source_situation']['request_hash']==req['request_hash'],'Situation source changed; explicit reconciliation required')
        return None
    if state.get('combat') or state.get('pending_check'):
        return None
    req=request(runtime)
    body={'kind':'situation','situation_stage':True,'action':action,'entry':entry,'events':[],
          'request':req,'host_mode':'one_pass','one_pass':one_pass}
    runtime.stage_kit_turn(turn_id,_rev,body)
    packet={'stage':'situation_required','turn_id':turn_id,'committed':False,'fiction_changed':False,
            'instructions':RULE,'schema':{'decision':{'situation':SCHEMA},'performance':{'segments':[]}},
            'input':dict(req,established_warnings=kit_timed_procedures.warnings_here(state,source['id'])),
            'saved_player_action':action,
            'next_command':kit_lifecycle.complete_command(runtime.path,turn_id)}
    runtime.save_kit_packet(turn_id,packet)
    return packet

def accepted_result(runtime,event):
    import shlex
    q=shlex.quote(str(runtime.path))
    return {'stage':'situation_accepted','committed':True,'fiction_changed':False,
            'revision':runtime.load()[0],'resume_action':event['action'],'resume_entry':event['entry'],
            'next_command':'python3 -m runtime.kit_agent prepare --one-pass --world-response --db '+q+
                           (' --opening' if event['entry'] else ' --action-file a.txt'),
            'next_step':'Continue the saved action (write resume_action to a.txt), or entry. Do not ask the player to repeat it. No player-facing line yet.'}

def complete(runtime,turn_id,output):
    row=runtime.db.execute('SELECT body,revision FROM kit_pending WHERE turn_id=?',(turn_id,)).fetchone()
    if row is None:
        past=runtime.db.execute('SELECT body FROM ledger WHERE turn_id=?',(turn_id,)).fetchall()
        events=[json.loads(r[0]) for r in past]
        event=next((e for e in events if e.get('type')=='source_situation'),None)
        if event is None:return None
        require(output=={'decision':{'situation':event['reading']},'performance':{'segments':[]}},
                'Situation replay differs from the accepted reading')
        return dict(accepted_result(runtime,event),already_committed=True)
    body=json.loads(row[0])
    if not body.get('situation_stage'):return None
    require(isinstance(output,dict) and set(output)=={'decision','performance'} and
            isinstance(output['decision'],dict) and set(output['decision'])=={'situation'} and
            output['performance']=={'segments':[]},'Situation completion is a reading, not narration or an action')
    current=request(runtime)
    require(current['request_hash']==body['request']['request_hash'],'Situation source changed while pending')
    reading=validate(output['decision']['situation'],current)
    event={'type':'source_situation','reading':reading,'action':body['action'],'entry':body['entry'],
           'evidence':'Host interpretation with exact source evidence; semantic reading remains host judgment.'}
    runtime._commit(turn_id,row[1],[event],consume_pending=True)
    return accepted_result(runtime,event)

def apply_event(runtime,state,source,event):
    from .state_context import Runtime
    req=request(runtime)
    reading=validate(event['reading'],req)
    require(not state.get('source_situation'),'An existing situation requires explicit reconciliation, not replacement')
    require(not any((state.get('room') or {}).get('turns_in',{}).values()),
            'Cannot retrospectively change narrated source facts; reconcile existing play explicitly')
    projected=project(source,reading)
    runtime._check_source(projected)
    state['source_situation']=copy.deepcopy(reading)
    state['situation_identity']={k:req[k] for k in ('source_sha256','room_id','location','request_hash')}
    state['situation_identity']['authority_version']=VERSION
    state['situation_identity']['compiler_limits']=copy.deepcopy(req['compiler_limits'])
    state['actors']={k:v for k,v in state['actors'].items() if k in projected['actors']}
    for key,actor in projected['actors'].items():
        if key not in state['actors']:state['actors'][key]=copy.deepcopy(actor)
    for key,actor in state['actors'].items():
        for field in ('immediate_goal','motive','goal_authority','goal_evidence'):
            actor[field]=copy.deepcopy(projected['actors'][key][field])
        if 'statistics' in actor_readings(reading)[key]:
            for field in ('stat_block','statistics_provenance'):
                actor[field]=copy.deepcopy(projected['actors'][key][field])
        if 'source_name' in actor_readings(reading)[key]:
            for field in ('name','identity_evidence'):
                actor[field]=copy.deepcopy(projected['actors'][key][field])
        if actor_readings(reading)[key].get('visibility','source')!='source':
            original=projected['actors'][key]
            require(actor.get('status') not in ('dead','fled') or actor.get('status')==original.get('status'),
                    'Initial interpretation cannot undo an actor outcome; reconcile explicitly')
            for field in ('status','visible','hidden','invisible','concealed','unseen','conditions'):
                if field in original:actor[field]=copy.deepcopy(original[field])
    # Preparation may withhold an initial compiler disclosure; it cannot erase
    # knowledge already earned or turn a private source sentence into discovery.
    Runtime._observe(state,projected)
    state['situation_resume']={'action':event['action'],'entry':event['entry']}
    source.clear()
    source.update(projected)  # the remainder of this transaction observes the interpreted projection
