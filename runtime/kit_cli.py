"""Command-line dispatch for the Kit bridge.

The engine stays in kit_agent. This module owns argument parsing and the command
switch. `python3 -m runtime.kit_agent` and `python3 runtime/kit_agent.py` still
enter through kit_agent.main, which is this function re-exported.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import kit_campaign, kit_rooms
from .state_context import (HostSequenceError, InvalidChange, Runtime, StaleTurn,
                            load_voice, personality_core_text)


def persona_text(folder=None):
    """The exact persona text the bridge sends (personality_core_text), any voice-cap
    warning, and the authority note. No database, no scene, no state."""
    warning = load_voice(folder)[1]
    parts = [personality_core_text(folder).rstrip('\n')]
    if warning:
        parts.append(f'Voice warning: {warning}')
    parts.append(PERSONA_AUTHORITY_NOTE)
    return '\n\n'.join(parts) + '\n'


def _cli_stamps(items):
    out = {}
    for item in items or ():
        name, _, value = item.partition('=')
        try:
            out[name.strip()] = float(value)
        except ValueError:
            raise InvalidChange(f'--stamp takes NAME=EPOCH_SECONDS, got {item!r}') from None
    return out


def _carry_lobby_question(db, packet, turn_id):
    pending = kit_campaign.carry_question(db, turn_id)
    if pending:
        packet['lobby_question'] = {
            'id': pending['id'], 'table_line': pending['table_line'],
            'instruction': 'Not yet delivered from the lobby. Ask it in your own voice in this '
                           "turn's spoken, out of character, before or after the scene. Name each item "
                           'it asks about; its words do not count against the length caps. It is marked '
                           'asked only when your committed reply actually asks it.'}


def _lobby_question_delivery(args, result):
    """A lobby question not yet confirmed delivered rides on the next play packet (prepare, or the
    start --room opening); the commit of that turn confirms it only when the committed spoken
    actually asks it (docs/architecture/LOBBY_QUESTIONS.md)."""
    try:
        if args.command == 'prepare' and not args.table_talk and result.get('turn_id'):
            _carry_lobby_question(args.db, result, result['turn_id'])
        elif args.command == 'start' and isinstance(result.get('prepared'), dict) \
                and result['prepared'].get('turn_id'):
            _carry_lobby_question(args.db, result['prepared'], result['prepared']['turn_id'])
        elif args.command in ('complete', 'finish') and result.get('committed') is not False:
            if kit_campaign.confirm_question_delivered(args.db, turn_id=args.turn_id,
                                                       spoken=result.get('spoken')):
                result['lobby_question_delivered'] = True
            elif kit_campaign.carried_question(args.db, args.turn_id):
                result['lobby_question_delivered'] = False
                result['lobby_question_note'] = ('The reply did not ask the lobby question; it stays '
                                                 'pending and rides the next turn.')
    except Exception:  # noqa: BLE001 - bookkeeping must never break a turn
        pass


def _reject(message, missing=()):
    """Refuse a command the host can fix. Exit 2, one JSON object on stderr, same as a bridge rejection.

    ``missing`` names the flags or fields the command cannot run without. The message is the
    sentence the CLI used to print after argparse's usage dump.
    """
    body = {'stage': 'rejected', 'committed': False, 'message': message}
    if missing:
        body['missing'] = list(missing)
    print(json.dumps(body, ensure_ascii=False), file=sys.stderr)
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start', 'init', 'view', 'prepare', 'decide', 'finish', 'complete',
                                            'abandon', 'feedback', 'character', 'notes', 'play', 'trace',
                                            'timing', 'persona', 'stamp', 'rehydrate', 'rest'])
    parser.add_argument('--db', default='kit.sqlite')
    parser.add_argument('--kind', choices=['short', 'long'], help='rest: a short or a long rest (slots and uses '
                                                                  'come back; re-sending the sheet does not)')
    parser.add_argument('--room', help='start/init: a room file to mount. With no --room, start reports '
                                       'what Kit is available for and does not open a room (runtime/kit_campaign.py).')
    parser.add_argument('--regression', action='store_true',
                        help='start/init: mount a stub or fixture_only room. Engineering only. '
                             'Does nothing if --room is omitted.')
    parser.add_argument('--campaign',
                        help='start/init: a game the player asked for by name. '
                             'Omit it unless they named one. "dotmm" is Dungeon of the Mad Mage.')
    parser.add_argument('--intent', choices=kit_campaign.INTENTS,
                        help='start: the player chose play (Kit DMs) or build (DM assistant) at the greeting')
    parser.add_argument('--table', choices=kit_campaign.TABLE_MODES,
                        help='start: solo (one player) or shared (several players taking turns); '
                             'recorded in the save')
    parser.add_argument('--question-delivered', dest='question_delivered', metavar='ID',
                        help='start: confirm the lobby question with this question_id was shown to the player '
                             '(until confirmed, it is raised again)')
    parser.add_argument('--modules', help='start: a folder of module/room files the player attached '
                                          '(default: rooms/). Only loadable, non-stub files are offered.')
    parser.add_argument('--area', help='start: begin in this area of the room (default: its starting_area)')
    parser.add_argument('--model', help='Optional standalone Responses API model for play')
    parser.add_argument('--perception', type=int, help='Test character Wisdom (Perception) modifier')
    parser.add_argument('--insight', type=int, help='Test character Wisdom (Insight) modifier')
    parser.add_argument('--sleight-of-hand', dest='sleight_of_hand', type=int,
                        help='Test character Dexterity (Sleight of Hand) modifier, for card play')
    parser.add_argument('--no-memory', action='store_true', help='Ablation: hide Kit’s prior episodes from her decision stage')
    parser.add_argument('--one-pass', action='store_true', help='One model output for live chat; use complete to commit')
    parser.add_argument('--performance-variant', choices=PERFORMANCE_VARIANTS,
                        help=f'Performer instructions: for prepare --one-pass or decide (default '
                             f'{DEFAULT_BRIDGE_VARIANT}), or for play (default current)')
    parser.add_argument('--opening', action='store_true', help='Prepare the initial scene entry instead of a player action')
    parser.add_argument('--table-talk', dest='table_talk', action='store_true',
                        help='prepare: the host marks this line as table talk to Kit mid-scene (meta mode, '
                             'not adjudicated, not logged as the PC speaking; leak guards still apply)')
    parser.add_argument('--action', help='Player action for prepare')
    parser.add_argument('--action-file', help='UTF-8 player action file for prepare')
    parser.add_argument('--turn-id', help='Turn ID returned by prepare')
    parser.add_argument('--input-file', help='JSON plan, speech, or combined output; - reads stdin')
    parser.add_argument('--text', help='feedback: the player’s out-of-character comment')
    parser.add_argument('--evidence', action='append',
                        help='feedback: committed turn ID the comment is about (repeatable; '
                             'default: latest turn)')
    parser.add_argument('--name', help='character: the player character\'s name')
    parser.add_argument('--ancestry', help='character: the player character\'s ancestry (e.g. Harengon)')
    parser.add_argument('--class-name', dest='class_name', help='character: class (optional)')
    parser.add_argument('--level', type=int, help='character: level (optional)')
    parser.add_argument('--sheet', help='start/character: a character_sheet_v1 JSON file. '
                                        'Player-facing start does not load a character until this is passed.')
    parser.add_argument('--held', help='character: comma list of what the PC holds now ("" for nothing)')
    parser.add_argument('--active', help='character: comma list of spells/conditions active now')
    parser.add_argument('--replaces', default='none', help='feedback: note id this feedback supersedes')
    parser.add_argument('--degraded', action='store_true',
                        help=f'finish/complete: accept style misses as warnings (only after '
                             f'{DEGRADED_AFTER_REJECTIONS} rejections on the turn)')
    parser.add_argument('--stamp', action='append', default=[],
                        help='prepare/complete/stamp: a host time NAME=EPOCH_SECONDS, one of '
                             + ', '.join(HOST_STAMPS) + ' (docs/architecture/HOST_TIMING.md); repeatable')
    parser.add_argument('--full', action='store_true',
                        help='prepare --one-pass/start: send the whole packet, not the three layers '
                             '(docs/architecture/MANIFESTS.md)')
    parser.add_argument('--pretty', action='store_true',
                        help='prepare/decide/finish/complete: indent the JSON for reading (default compact)')
    args = parser.parse_args()
    if args.command == 'persona':
        # Kit before any game: the persona text the bridge uses, with no database or scene.
        sys.stdout.write(persona_text())
        return 0
    if args.command == 'start' and args.question_delivered:
        done = kit_campaign.confirm_question_delivered(args.db, question_id=args.question_delivered)
        print(json.dumps({'question_delivered': args.question_delivered, 'confirmed': done}))
        return 0 if done else 2
    if args.command == 'start':
        try:
            if args.room and not args.regression:
                source = kit_rooms.load_room(args.room)
                refusal = kit_campaign.player_room_refusal(args.room, source)
                if refusal:
                    print(json.dumps(refusal, ensure_ascii=False), file=sys.stderr)
                    return 2
                if not args.sheet:
                    print(json.dumps(kit_campaign.need_character(args.room, source), ensure_ascii=False))
                    return 0
            result = start_session(args.db, args.sheet, room=args.room, area=args.area,
                                   manifests=not args.full, campaign=args.campaign,
                                   intent=args.intent, table=args.table, modules=args.modules)
            if args.room and args.table and isinstance(result, dict):
                kit_campaign.record_table_mode(args.db, args.table)
                result['table_mode'] = args.table
            if args.room and isinstance(result, dict):
                _lobby_question_delivery(args, result)
        except kit_rooms.RoomMountError as exc:
            print(json.dumps(exc.host_view(), ensure_ascii=False), file=sys.stderr)
            return 2
        except (InvalidChange, PendingRuling) as exc:
            print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False,
                         **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
        return 0
    if args.command == 'init':
        if not args.room:
            print(json.dumps(kit_campaign.campaign_entry(args.db, args.sheet, campaign=args.campaign),
                             ensure_ascii=False))
            return 0
        try:
            source = kit_rooms.load_room(args.room)
        except kit_rooms.RoomMountError as exc:
            print(json.dumps(exc.host_view(), ensure_ascii=False), file=sys.stderr)
            return 2
        if not args.regression:
            refusal = kit_campaign.player_room_refusal(args.room, source)
            if refusal:
                print(json.dumps(refusal, ensure_ascii=False), file=sys.stderr)
                return 2
        runtime = Runtime(args.db)
        try:
            runtime.initialize(source, source['starting_area'])
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        finally:
            runtime.close()
        return 0
    runtime = Runtime(args.db)
    try:
        if args.command == 'view':
            print(json.dumps(runtime.player_view(), indent=2, ensure_ascii=False))
        elif args.command == 'trace':
            print(json.dumps(runtime.recent_kit_turns(), indent=2, ensure_ascii=False))
        elif args.command == 'timing':
            print(json.dumps([{**row, 'latency': turn_latency(row)} for row in runtime.recent_kit_timings()],
                             indent=2, ensure_ascii=False))
        elif args.command == 'rehydrate':
            if not args.turn_id:
                return _reject('rehydrate requires --turn-id', ('turn-id',))
            try:
                print(json.dumps(KitChatBridge(runtime).rehydrate(args.turn_id), ensure_ascii=False))
            except InvalidChange as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
                return 2
        elif args.command == 'stamp':
            if not args.turn_id or not args.stamp:
                missing = [name for name, present in (('turn-id', args.turn_id), ('stamp', args.stamp)) if not present]
                return _reject('stamp requires --turn-id and at least one --stamp NAME=EPOCH_SECONDS', missing)
            try:
                print(json.dumps(KitChatBridge(runtime).stamp(args.turn_id, **_cli_stamps(args.stamp)),
                                 ensure_ascii=False))
            except (InvalidChange, ValueError) as exc:
                print(json.dumps({'stage': 'rejected', 'message': str(exc)}, ensure_ascii=False), file=sys.stderr)
                return 2
        elif args.command == 'rest':
            if args.kind not in ('short', 'long'):
                return _reject('rest requires --kind short or --kind long', ('kind',))
            print(json.dumps(runtime.rest(args.kind), indent=2, ensure_ascii=False))
        elif args.command == 'notes':
            print(json.dumps(runtime.player_notes(), indent=2, ensure_ascii=False))
        elif args.command == 'character' and args.sheet:
            sheet = json.loads(Path(args.sheet).read_text(encoding='utf-8'))
            print(json.dumps(runtime.set_player_sheet(sheet), indent=2, ensure_ascii=False))
        elif args.command == 'character' and (args.held is not None or args.active is not None):
            lists = {key: [v.strip() for v in value.split(',') if v.strip()]
                     for key, value in (('held', args.held), ('active', args.active)) if value is not None}
            print(json.dumps(runtime.set_pc_state(**lists), indent=2, ensure_ascii=False))
        elif args.command == 'character':
            if not (args.name and args.ancestry):
                return _reject('character requires --sheet, or --name and --ancestry',
                               ('sheet', 'name', 'ancestry'))
            print(json.dumps(runtime.set_player_character(args.name, args.ancestry, args.class_name,
                                                          args.level), indent=2, ensure_ascii=False))
        elif args.command in ('prepare', 'decide', 'finish', 'complete', 'abandon', 'feedback'):
            bridge = KitChatBridge(runtime, RoomAdjudicator(args.perception, args.insight,
                                                             sleight_of_hand=args.sleight_of_hand),
                                   manifests=not args.full)
            try:
                if args.command == 'abandon':
                    if not args.turn_id:
                        return _reject('abandon requires --turn-id', ('turn-id',))
                    result = bridge.abandon(args.turn_id)
                elif args.command == 'feedback':
                    if not args.text:
                        return _reject('feedback requires --text', ('text',))
                    result = bridge.feedback(args.text, args.evidence, args.replaces)
                elif args.command == 'prepare':
                    if args.opening:
                        if args.action is not None or args.action_file is not None:
                            return _reject('--opening does not take an action')
                        action = None
                    else:
                        if (args.action is None) == (args.action_file is None):
                            return _reject('prepare requires exactly one of --action or --action-file',
                                           ('action', 'action-file'))
                        action = (args.action if args.action_file is None else
                                  Path(args.action_file).read_text(encoding='utf-8').strip())
                    if args.performance_variant and not args.one_pass:
                        return _reject('--performance-variant on prepare needs --one-pass; '
                                       'staged turns choose it at decide', ('one-pass',))
                    result = bridge.prepare(action, args.turn_id, use_memory=not args.no_memory,
                                            one_pass=args.one_pass, opening=args.opening,
                                            performance_variant=args.performance_variant,
                                            table_talk=args.table_talk, host_stamps=_cli_stamps(args.stamp))
                else:
                    if not args.turn_id or not args.input_file:
                        missing = [name for name, present in (('turn-id', args.turn_id),
                                                              ('input-file', args.input_file)) if not present]
                        return _reject(f'{args.command} requires --turn-id and --input-file', missing)
                    raw = sys.stdin.read() if args.input_file == '-' else Path(args.input_file).read_text(encoding='utf-8')
                    submitted = json.loads(raw)
                    variant = args.performance_variant or DEFAULT_BRIDGE_VARIANT
                    result = (bridge.decide(args.turn_id, submitted, variant) if args.command == 'decide' else
                              bridge.finish(args.turn_id, submitted, degraded=args.degraded)
                              if args.command == 'finish' else
                              bridge.complete(args.turn_id, submitted, degraded=args.degraded,
                                              host_stamps=_cli_stamps(args.stamp)))
            except PendingRuling as exc:
                result = pending_ruling_result(exc)
            except InvalidChange as exc:
                rejected = {'stage': 'rejected', 'message': str(exc), 'committed': False}
                if isinstance(exc, HostSequenceError):
                    rejected['next_step'] = exc.next_step
                elif isinstance(exc, StaleTurn):
                    rejected['next_step'] = 'prepare_again'
                if isinstance(exc, PerformanceRejected):
                    rejected.update(exc.guidance)
                if args.command in ('finish', 'complete') and not isinstance(exc, StaleTurn):
                    pending = None
                    try:
                        pending = runtime.pending_kit_turn(args.turn_id)
                    except InvalidChange:
                        pass
                    if pending and pending['plan'] is not None:
                        rejected.update(decision_fixed=True, retry_instruction=retry_instruction(exc),
                                        host_retry=HOST_RETRY_NOTE)
                print(json.dumps(rejected, ensure_ascii=False), file=sys.stderr)
                return 2
            if isinstance(result, dict):
                _lobby_question_delivery(args, result)
            # Compact by default: the chat host reads this whole packet every turn, and
            # indentation alone added about a quarter to its size. --pretty for people.
            print(json.dumps(result, ensure_ascii=False,
                             **({'indent': 2} if args.pretty else {'separators': (',', ':')})))
        else:
            if not args.model:
                return _reject('standalone play requires --model; for ChatGPT use prepare/decide/finish', ('model',))
            if not os.environ.get('OPENAI_API_KEY'):
                return _reject('standalone play requires OPENAI_API_KEY; for ChatGPT use prepare/decide/finish',
                               ('OPENAI_API_KEY',))
            model = OpenAIResponsesModel(args.model)
            agent = KitAgent(runtime, model, RoomAdjudicator(args.perception, args.insight,
                                                               sleight_of_hand=args.sleight_of_hand),
                             performance_variant=args.performance_variant or 'current')
            print(f"Kit's table: {runtime.source().get('id')}. Enter an action, or /quit. Private traces: separate trace command.")
            if runtime.load()[0] == 0:
                try:
                    print(agent.opening()['spoken'])
                except InvalidChange as exc:
                    print(f'Opening rejected; no state was saved: {exc}', file=sys.stderr)
                    return 2
            else:
                print(f"Resuming in {runtime.player_view()['area']}.")
            while True:
                try:
                    action = input('\nYou> ').strip()
                except EOFError:
                    break
                if action == '/quit':
                    break
                if not action:
                    continue
                try:
                    result = agent.turn(action, use_memory=not args.no_memory)
                    print(f"\n{result['spoken']}")
                except PendingRuling as exc:
                    print(f'\n{exc}')
                except InvalidChange as exc:
                    print(f'\nTurn rejected; no state was saved: {exc}', file=sys.stderr)
    finally:
        runtime.close()
    return 0

# Bound after these functions exist. kit_agent is already loading this module and
# re-exports main once this import returns. Call-time lookup, not import-time work.
from .kit_agent import (  # noqa: E402
    DEFAULT_BRIDGE_VARIANT,
    DEGRADED_AFTER_REJECTIONS,
    HOST_RETRY_NOTE,
    HOST_STAMPS,
    KitAgent,
    KitChatBridge,
    OpenAIResponsesModel,
    PERFORMANCE_VARIANTS,
    PERSONA_AUTHORITY_NOTE,
    PendingRuling,
    PerformanceRejected,
    RoomAdjudicator,
    pending_ruling_result,
    retry_instruction,
    start_session,
    turn_latency,
)
