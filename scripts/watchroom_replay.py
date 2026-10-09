"""Scripted replay of the 2026-10-04 watchroom session (tests/playtests/2026-10-04-watchroom-nik.md).

Replays Nik's player turns through the one-pass bridge (prepare, complete) with a scripted Kit
that writes the decision Kit wrote on her first try in the live game, and corrects it only from
the rejection message, as she did. No model, no paid API, dice pinned. Per turn it records the
engine time of each call, the packet bytes, the decision and speech bytes Kit had to write,
stalls (prepare raised a pending ruling), misreads (the engine did something other than the
player meant), and rejections.

    env -u PYTHONPATH python3 scripts/watchroom_replay.py [--json out.json]
"""
import argparse
import copy
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_detail, kit_manifest  # noqa: E402
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import InvalidChange, Runtime  # noqa: E402

ROOM = 'tests/fixtures/rooms/watchroom.json'
NIK = ROOT / 'tests/fixtures/characters/nik.json'

# Kit's live decisions ran long: every free-text field was a sentence or two.
LONG = ('Nik is on the landing outside the watchroom, careful and quiet, and the warden inside is awake, '
        'humming, and watching the stair; the scene is about whether he gets past the post unchallenged.')


# Model-time estimate (no model is called): each model trip reads the packet and writes the
# output. These rates are assumptions for comparing builds, not measurements; pass your own.
MODEL = {'overhead_s': 1.0, 'prefill_tps': 2500.0, 'decode_tps': 50.0, 'bytes_per_token': 4.0}


def model_trip_s(packet_bytes, output_bytes):
    tokens_in = packet_bytes / MODEL['bytes_per_token']
    tokens_out = output_bytes / MODEL['bytes_per_token']
    return MODEL['overhead_s'] + tokens_in / MODEL['prefill_tps'] + tokens_out / MODEL['decode_tps']


def pct(values, q):
    values = sorted(values)
    if not values:
        return None
    k = (len(values) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 3)


def nbytes(value):
    return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))


KIT_COPY = {}
ROOM_COPY = {}
NONCES = {}


def hold(packet):
    """Kit keeps the bodies she is sent and applies a room diff to the copy she holds, with the
    nonce of each copy."""
    for layer in ('session', 'room'):
        item = packet.get(f'{layer}_manifest') or {}
        if item.get('nonce') and ('body' in item or 'diff' in item):
            NONCES[layer] = item['nonce']
    if 'body' in (packet.get('session_manifest') or {}):
        KIT_COPY.clear()
        KIT_COPY.update(packet['session_manifest']['body'])
    room = packet.get('room_manifest') or {}
    if 'body' in room:
        ROOM_COPY.clear()
        ROOM_COPY.update(room['body'])
    elif 'diff' in room:
        assert kit_manifest.digest(ROOM_COPY) == room['base'], 'room diff against a copy Kit does not hold'
        updated = kit_manifest.apply_diff(ROOM_COPY, room['diff'])
        ROOM_COPY.clear()
        ROOM_COPY.update(updated)
        assert kit_manifest.digest(ROOM_COPY) == room['hash'], 'room diff did not land on the new hash'


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def answer_check(packet):
    """Kit echoes the nonce of each copy she holds (#99 review: a nonce per layer and diff)."""
    return {layer: NONCES.get(layer, '') for layer in packet['manifest_check']['lines']}


def kit_decision(packet, turn):
    """The decision Kit writes on her first try, shaped to what the packet's schema requires."""
    private = packet['input']['private']
    hold(packet)  # the copies Kit keeps from the full sends (and room diffs)
    schema = (packet.get('schema') or KIT_COPY['schema'])['properties']['decision']
    action = private.get('player_action') or ''
    opening = private['action_kind'] == 'opening'
    focus = turn.get('focus', 'none')
    full = {
        'observed_event': private['accepted_public_event'],
        'goal': 'roleplay',
        'appraisal': {'label': turn.get('appraisal', 'interest'), 'intensity': 1,
                      'cause': 'The player is ' + (action[:120] or 'arriving at the landing.'),
                      'goal_effect': 'advances', 'target': 'player'},
        'memory_refs': [],
        'improv_read': {
            'player_bid': 'The player ' + (action[:200] or 'arrives on the landing and takes in the door.'),
            # Live T0: Kit anchored the opening on the room's story, which the bridge did not offer.
            'story_anchor': 'scene', 'story_basis': turn.get('story_basis', 'scene_state'),
            'actor_ref': focus, 'actor_basis': 'motive' if focus != 'none' else 'none',
            'connection': LONG, 'kit_choice': 'Kit lets the warden be a real obstacle: ' + LONG[:140]},
        'move': turn.get('move', 'world_description'),
        'public_brief': {
            'objective': 'Give the player a clear picture and a real choice. ' + LONG[:120],
            'tactic': turn.get('tactic', 'The warden keeps his post and wants answers before anything else.'),
            'visible_cue': 'Lamplight through the gap, the hum of four notes, a chair creaking. ' + LONG[:80],
            'player_opening': 'The player can listen, knock, speak, go in, or take the stair down past the door.',
            # Live T0: Kit quoted the scene on the entry turn instead of 'none'.
            'reply_to': turn.get('reply_to', action[:40] if action else 'the landing'),
            'scope': turn.get('scope', 'exchange'),
            'kit_focus': 'Spotlight the warden at his post and the stranger at the door. ' + LONG[:100],
            'callback': 'none',
            'mirror': 'steady energy, standard, dry humor: meet the player\'s careful pace and let the moment land.',
            'npc_notice': 'none'},
        'focus_actor': focus,
        'table_presence': turn.get('presence') or ('brief' if any(sp == 'Kit' for sp, _ in turn['speech']) else 'quiet'), 'tone': 'wry',
        'player_note': {'note': 'none', 'evidence_turns': [], 'replaces': 'none'},
        'player_mood': {'read': 'neutral', 'cue': 'none'},
        'turn_mode': (private.get('table_read') or {}).get('mode_hint') or 'banter',
        'detail': dict(kit_detail.NO_DETAIL, inventions=[]),
    }
    if turn.get('roll_call'):
        full['roll_call'] = {'skill': turn['roll_call'][0], 'mode': 'normal', 'target': turn['roll_call'][1],
                             'cause': {'kind': 'position', 'ref': 'none', 'roots': []}}
    if 'player_bid' not in schema['properties']['improv_read']['required']:
        # One line of ~160 characters: the bid, the pressure it meets, and Kit's choice (PR3 b).
        full['improv_read']['kit_choice'] = ('Nik ' + (action[:60] or 'arrives at the door') +
                                             '; the warden is awake; Kit lets him be a real obstacle.')[:160]
    if (private.get('compute') or {}).get('tier') == 'routine':
        # The engine says routine: Kit leaves out what it may (PR4); her choices stay.
        for key in private['compute']['may_omit']:
            if key.startswith('improv_read.'):
                full['improv_read'].pop(key.split('.', 1)[1], None)
            else:
                full.pop(key, None)
        full['focus_actor'] = 'none'
    if opening and not turn.get('stall'):
        full['public_brief']['scope'] = 'feature'
    return shape(full, schema)


OMITTED = {'appraisal', 'memory_refs', 'tone', 'player_note', 'player_mood', 'turn_mode',
           'story_anchor', 'story_basis', 'actor_ref', 'actor_basis'}


def shape(value, schema):
    """Keep what the schema has, and only what it requires or the turn set beyond the required."""
    if not isinstance(value, dict) or schema.get('type') != 'object':
        return value
    props, required = schema.get('properties') or {}, set(schema.get('required') or ())
    out = {}
    for key, item in value.items():
        if key not in props:
            continue
        if key in required or key in ('roll_call',):
            out[key] = shape(item, props[key])
    for key in required - set(out) - OMITTED:
        if key == 'kit_choice':
            out[key] = 'Kit lets the warden be a real obstacle.'
    return out


def correct(decision, message, packet):
    """Kit's fix for a rejection, read off the message (what she did live)."""
    private = packet['input']['private']
    read = decision.get('improv_read') or {}
    if 'Story basis' in message or 'Story anchor' in message:
        read.update(story_anchor='none', story_basis='none')
    elif 'reply_to must be none' in message:
        decision['public_brief']['reply_to'] = 'none'
    elif 'reply_to must quote' in message:
        decision['public_brief']['reply_to'] = (private.get('player_action') or '')[:30]
    elif 'Actor is not available' in message or 'not an actor present' in message:
        read.update(actor_ref='none', actor_basis='none')
        decision['focus_actor'] = 'none'
    elif 'Actor basis' in message:
        bases = private['discernment_candidates']['actor_bases'].get(read.get('actor_ref'), ['none'])
        read['actor_basis'] = bases[0]
    elif 'scope was flat' in message:
        return 'pad'
    else:
        return False
    return True


PAD = ['Somewhere below, a door closes and the sound climbs the stair and fades.',
       'Oil smoke drifts along the ceiling beams and gathers in the corner by the slit.',
       'The wind finds the arrow slit and the lamp flame leans and steadies again.']

TURNS = [
    {'id': 'T0', 'opening': True, 'story_basis': 'tease', 'focus': 'none', 'move': 'world_description',
     'speech': [
         ('Narrator', 'Lamplight leaks through the gap in the iron door and lays a thin bright stripe across the '
                      'landing stones. Behind the door someone hums the same four notes over and over, and a chair '
                      'creaks when he shifts. A stair winds on down past the door into the dark.'),
         ('Narrator', 'The post is awake. Whoever keeps it is watching the stair, not sleeping on it, and the door '
                      'stands ajar the width of a hand, the light inside steady and close.')]},
    {'id': 'T1', 'line': 'Nik creeps to the hinge side of the gap and puts one eye to the opening without touching the door.',
     'expect': {'stays': True}, 'reword': 'Nik edges up beside the gap and peeks in. Can I make a check?',
     'reword_expect': {'kind': 'check_request'},
     'move': 'ruling', 'scope': 'call', 'roll_call': ('stealth', 'warden'),
     'speech': [('Kit', 'Easing up to that gap with a man awake on the other side? Give me a Dexterity (Stealth) check.')]},
    {'id': 'T2', 'line': 'Stealth check: 1d20 (13) + 2 = 15', 'expect': {'stays': True, 'peek_view': True}, 'move': 'world_description',
     'scope': 'feature',
     'speech': [
         ('Narrator', 'Through the gap: a warden in a padded coat on a stool, a short spear across his knees, humming '
                      'at a hooded lamp. Behind him a plain chest sits under an arrow slit, a brass bell hangs by the '
                      'slit, and a back stair drops away in the far corner.'),
         ('Narrator', 'He has not looked up. The hum goes round again, the same four notes, and the lamp hisses softly '
                      'between him and the door while the stair below stays dark and still.')]},
    {'id': 'T3', 'line': ('Nik watches the man for a moment. Is the chest locked? Is there a bell, a horn, or a cord he '
                          'could use to raise an alarm? Can I make a check?'),
     'expect': {'kind': 'check_request'},
     'reword': 'Nik watches the man for a moment and studies the room. Can I make a check?',
     'reword_expect': {'kind': 'check_request'},
     'move': 'ruling', 'scope': 'call', 'roll_call': ('perception', 'none'),
     'speech': [('Kit', 'Watching him and the room from the gap. Make a Wisdom (Perception) check.')]},
    {'id': 'T4', 'line': 'Perception check: 2d20kh1 (18, 16) + 4 = 22', 'expect': {'stays': True},
     'move': 'world_description', 'scope': 'feature',
     'speech': [
         ('Narrator', 'At that angle the details come clear: the bell cord hangs within an arm of the stool, the spear '
                      'rests where his hand already is, and the chest has no lock you can see from here, only a heavy '
                      'lid and iron straps.'),
         ('Narrator', 'He hums, glances at the stair head once, and settles back on the stool. Nobody else is in the '
                      'room, and nothing moves on the back stair behind him. The lamp burns low and even on its hook.')]},
    {'id': 'T5', 'line': ('Nik eases the door open just enough to show himself, stays on the threshold, and says: '
                          '"Evening. I am not here for trouble."'),
     'expect': {'stays': True}, 'focus': 'warden', 'move': 'npc_reply',
     'speech': [
         ('Narrator', 'The hum stops. The warden comes up off the stool with the spear already level, and the lamp '
                      'swings its light across the stranger in the doorway. He keeps the length of the spear between them.'),
         ('Watch warden', 'Who sent you? Where are you going? Answer from there.')]},
    {'id': 'T6', 'line': 'Nik steps through the iron door. "Easy. Just passing through."', 'expect': {'area': 'watchroom', 'kit_last': True},
     'focus': 'warden', 'move': 'npc_reply',
     'speech': [
         ('Narrator', 'Two steps in and the spear point finds the middle of his coat and stays there. The warden does '
                      'not blink, and his free hand drifts toward the bell cord, close enough to ring it without looking.'),
         ('Watch warden', 'Passing through to where? Who sent you? Nobody passes my post.')]},
    {'id': 'T7', 'line': ('"I was sent to check the stair," Nik says. He watches whether the guard\'s eyes flick toward '
                          'the stair or the chest.'),
     'expect': {'not_kind': 'inspect_feature'}, 'focus': 'warden', 'move': 'npc_reply',
     'roll_call': ('persuasion', 'warden'),
     'speech': [
         ('Narrator', 'His eyes go to the back stair, quick, and come straight back to Nik. The spear does not move, '
                      'and the lamp ticks on its hook in the quiet while he waits for a better answer.'),
         ('Watch warden', 'Nobody sent anyone to check my stair. Convince me.'),
         ('Kit', 'Make that pitch a Charisma (Persuasion) check.')]},
    {'id': 'T8', 'line': 'Nik says: "Let me through and you will never see me again." His Persuasion comes up 3.',
     'focus': 'warden', 'move': 'npc_reply', 'appraisal': 'anger',
     'speech': [
         ('Narrator', 'The warden\'s jaw sets. He takes one step closer and the spear point comes up an inch, level '
                      'with Nik\'s throat, and his other hand closes on the bell cord without ringing it yet, his eyes never leaving the stranger.'),
         ('Watch warden', 'No. Hands out. Now.')]},
    {'id': 'T9', 'line': 'Nik feints left, then dashes for the back stair.', 'expect': {'kind': 'exit_contested'},
     'focus': 'warden', 'move': 'npc_reply',
     'speech': [
         ('Narrator', 'Nik breaks left and cuts back for the stair head, and the warden swings the spear across to '
                      'block the way, quicker than a man on a stool has any right to be, the shaft hissing through the lamplight.'),
         ('Watch warden', 'Stop there!'),
         ('Kit', 'Dexterity (Acrobatics) to get past him.')]},
    {'id': 'T10', 'line': 'Acrobatics 3', 'expect': {'area': 'watchroom'}, 'focus': 'warden', 'move': 'npc_reply',
     'speech': [
         ('Narrator', 'Nik\'s foot catches the stool and he goes down hard at the warden\'s feet, the stair head an '
                      'arm\'s length away, the spear point already over him and the lamp swinging on its hook and throwing his shadow up the wall.'),
         ('Watch warden', 'Stay down.')]},
]


# --short-beats: Kit opens the room entry on a fitting check call (a stall check); the player
# rolls in Avrae and the next turn delivers the held description scaled to the roll.
STALL_T0 = {'id': 'T0', 'opening': True, 'stall': True, 'focus': 'none', 'move': 'ruling', 'scope': 'call',
            'presence': 'quiet', 'roll_call': ('perception', 'none'),
            'speech': [('Narrator', 'Lamplight through a gap in an iron door, and someone humming behind it. '
                                    'Roll Perception.')]}
HELD_T0 = {'id': 'T0r', 'line': 'Perception check: 1d20 (13) + 2 = 15', 'expect': {'stays': True},
           'move': 'world_description', 'scope': 'feature', 'speech': TURNS[0]['speech']}


def short_beat_turns():
    return [STALL_T0, HELD_T0] + TURNS[1:]


def misread(turn, packet, runtime):
    expect = turn.get('expect') or {}
    private = packet['input']['private']
    kind = private['action_kind']
    area = private['dm_context']['scene']['current_area'] if 'dm_context' in private else None
    events = runtime.load()[1]
    if expect.get('stays') and kind in ('move', 'exit', 'stealth_exit') or (
            expect.get('stays') and private.get('story_brief', {}).get('area') not in (None, 'landing')):
        return f'moved ({kind})'
    if expect.get('peek_view') and not private.get('threshold_view'):
        return 'no view into the next area'
    if 'kind' in expect and kind != expect['kind']:
        return f'kind {kind}, expected {expect["kind"]}'
    if 'not_kind' in expect and kind == expect['not_kind']:
        return f'kind {kind}'
    return None


def run(out=None, turns=None, manifests=False):
    for copy_held in (KIT_COPY, ROOM_COPY, NONCES):
        copy_held.clear()  # a fresh Kit: nothing held from an earlier run in this process
    folder = Path(tempfile.mkdtemp())
    db = folder / 'replay.sqlite'
    t = time.perf_counter()
    started = start_session(db, NIK, room=ROOM, manifests=manifests)
    start_ms = (time.perf_counter() - t) * 1000
    runtime = Runtime(db)
    bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 10, npc_roll=lambda: 10), manifests=manifests)
    rows = []
    for turn in turns or TURNS:
        row = {'turn': turn['id'], 'stalls': 0, 'misreads': 0, 'rejects': 0, 'reasons': [],
               'prepare_ms': [], 'complete_ms': []}
        if turn.get('opening'):
            packet = started['prepared']
            row['prepare_ms'].append(round(start_ms, 1))
        else:
            line = turn['line']
            while True:
                t = time.perf_counter()
                try:
                    packet = bridge.prepare(line, one_pass=True)
                except PendingRuling as exc:
                    row['prepare_ms'].append(round((time.perf_counter() - t) * 1000, 1))
                    row['stalls'] += 1
                    row['reasons'].append(f'stall: {exc}'[:160])
                    if 'reword' in turn and line != turn['reword']:
                        line = turn['reword']
                        continue
                    packet = None
                    break
                row['prepare_ms'].append(round((time.perf_counter() - t) * 1000, 1))
                row.setdefault('kinds', []).append(packet['input']['private']['action_kind'])
                wrong = misread(dict(turn, expect=turn.get('reword_expect')) if line == turn.get('reword') else turn,
                                packet, runtime)
                if wrong and 'reword' in turn and line != turn['reword']:
                    row['misreads'] += 1
                    row['reasons'].append(f'misread: {wrong}')
                    bridge.abandon(packet['turn_id'])
                    line = turn['reword']
                    continue
                if wrong:
                    row['misreads'] += 1
                    row['reasons'].append(f'misread: {wrong}')
                break
        if packet is None:
            rows.append(row)
            continue
        row['packet_bytes'] = nbytes(packet)
        if 'session_manifest' in packet:
            row['manifest_sent'] = [layer for layer in ('session', 'room')
                                    if 'body' in packet[f'{layer}_manifest'] or 'diff' in packet[f'{layer}_manifest']]
        decision = kit_decision(packet, turn)
        quote = ' '.join((packet['input']['private'].get('player_action') or '').split()[:4])
        speech = {'segments': [{'speaker': s, 'text': x, **({'reacts_to': quote} if s == 'Kit' else {})}
                               for s, x in turn['speech']]}
        row['decision_bytes'] = nbytes(decision)
        row['speech_bytes'] = nbytes(speech)
        for _ in range(6):
            t = time.perf_counter()
            try:
                output = {'decision': decision, 'performance': speech}
                if 'session_manifest' in packet:  # Kit echoes the nonces of the copies she holds
                    output['manifest'] = {}
                    if 'manifest_check' in packet:
                        output['manifest']['check'] = answer_check(packet)
                        row['manifest_check'] = True
                    row['manifest_out_bytes'] = nbytes(output['manifest'])
                result = bridge.complete(packet['turn_id'], output)
                row['complete_ms'].append(round((time.perf_counter() - t) * 1000, 1))
                row['spoken_tail'] = result['spoken'][-120:]
                last = speech['segments'][-1]['text']
                if (turn.get('expect') or {}).get('kit_last') and not result['spoken'].rstrip().endswith(last.rstrip()):
                    row['misreads'] += 1
                    row['reasons'].append('misread: engine line printed after the committed reply')
                break
            except InvalidChange as exc:
                row['complete_ms'].append(round((time.perf_counter() - t) * 1000, 1))
                row['rejects'] += 1
                message = str(exc)
                row['reasons'].append(f'reject: {message}'[:200])
                fixed = correct(decision, message, packet)
                if fixed == 'pad':  # Kit adds a visible beat and resubmits
                    speech['segments'].insert(1, {'speaker': 'Narrator', 'text': PAD[row['rejects'] % len(PAD)]})
                    continue
                if not fixed:
                    row['unresolved'] = True
                    bridge.abandon(packet['turn_id'])
                    break
        rows.append(row)
    runtime.close()
    for r in rows:
        trips = []
        # Everything Kit writes: the decision, the speech and the private manifest echo (hashes and
        # nonces, every layered turn).
        packet = r.get('packet_bytes', 60000)
        written = r.get('decision_bytes', 0) + r.get('speech_bytes', 0) + r.get('manifest_out_bytes', 0)
        if 'packet_bytes' in r:
            r['output_bytes'] = written
        # A stall or misread costs Kit a trip to read the ruling and reword (about 200 bytes out);
        # every reject repeats the whole trip with the full output.
        trips += [model_trip_s(packet, 200)] * (r['stalls'] + r['misreads'])
        trips += [model_trip_s(packet, written)] * (r['rejects'] + (1 if 'packet_bytes' in r else 0))
        r['model_est_s'] = round(sum(trips), 3)
        r['end_to_end_est_s'] = round(r['model_est_s'] + (sum(r['prepare_ms']) + sum(r['complete_ms'])) / 1000, 3)
    total = {key: sum(r[key] for r in rows) for key in ('stalls', 'misreads', 'rejects')}
    e2e = [r['end_to_end_est_s'] for r in rows]
    total.update(end_to_end_est_median_s=pct(e2e, 0.5), end_to_end_est_p95_s=pct(e2e, 0.95),
                 engine_ms_median=pct([sum(r['prepare_ms']) + sum(r['complete_ms']) for r in rows], 0.5),
                 engine_ms_p95=pct([sum(r['prepare_ms']) + sum(r['complete_ms']) for r in rows], 0.95),
                 model_assumptions=MODEL)
    total['unresolved'] = sum(1 for r in rows if r.get('unresolved'))
    total['engine_ms'] = round(sum(sum(r['prepare_ms']) + sum(r['complete_ms']) for r in rows), 1)
    sized = [r for r in rows if 'packet_bytes' in r]
    for key in ('packet_bytes', 'decision_bytes', 'speech_bytes'):
        total[f'mean_{key}'] = round(sum(r[key] for r in sized) / len(sized)) if sized else 0
        total[f'median_{key}'] = pct([r[key] for r in sized], 0.5)
    report = {'turns': rows, 'total': total}
    for r in rows:
        print(f"{r['turn']:>4} {r.get('kinds')} stall {r['stalls']} misread {r['misreads']} reject {r['rejects']} "
              f"packet {r.get('packet_bytes', '-')} decision {r.get('decision_bytes', '-')} "
              f"speech {r.get('speech_bytes', '-')} sent {r.get('manifest_sent', '-')}"
              f"{' check' if r.get('manifest_check') else ''} prepare_ms {r['prepare_ms']} complete_ms {r['complete_ms']}")
        for reason in r['reasons']:
            print('       ', reason)
    print('TOTAL', json.dumps(total))
    if out:
        Path(out).write_text(json.dumps(report, indent=1), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json')
    parser.add_argument('--manifests', action='store_true',
                        help='three-layer packets (SessionManifest, RoomManifest, TurnDelta), as the live CLI sends')
    parser.add_argument('--short-beats', action='store_true',
                        help='T0 opens on a stall check (Roll Perception); the roll delivers the description')
    for key, value in MODEL.items():
        parser.add_argument('--' + key.replace('_', '-'), type=float, default=value)
    args = parser.parse_args()
    MODEL.update({key: getattr(args, key) for key in MODEL})
    run(args.json, short_beat_turns() if args.short_beats else None, manifests=args.manifests)
