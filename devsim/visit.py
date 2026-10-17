"""Talk to people in a running simulation: in person, by phone, or into an active group conversation.

    python3 -m devsim.visit runs/live/RUN_DIR --talk priya --name Kanishk      (face to face; /bye walks away)
    python3 -m devsim.visit runs/live/RUN_DIR --call priya --name Kanishk      (a phone call; /bye hangs up)
    python3 -m devsim.visit runs/live/RUN_DIR --send Kabir --to priya --who "a new classmate" --age 15 --name Kanishk
        (your own character: you type its lines, '/auto GOAL' or --goal lets the model play it, /bye or --recall recalls it)
    python3 -m devsim.visit runs/live/RUN_DIR "Rohan, let Priya finish." --to rohan --name Kanishk

--talk walks up to the person at the run's next event boundary and the world waits while you two talk: they
reply to each line (or stay quiet, or end it), seeing the exchange so far. A call rings the person instead; they decide whether to answer (someone mid-conversation
may step away), and you chat until either side hangs up. The world waits while you talk: no simulated time passes.
Replies are written to RUN_DIR/calls.jsonl.

The watcher (key t) and this command append to RUN_DIR/inbox.jsonl. run_live delivers new lines at the
next event boundary, into the active conversation that includes --to (or the most recent active one),
as speech from a visitor entity. Lines wait in the inbox while no conversation is active. A delivered
line is a researcher intervention: the event says so and runtime.visitor_log records it. It does not
use up a conversation turn; the participants hear it, appraise it and may answer it in their next turns.
"""
import argparse
import json
from pathlib import Path
import re
import time

from . import household


def say(run, text, to=None, name='Visitor'):
    text, name = ' '.join(str(text).split()), ' '.join(str(name).split())
    if not text or len(text) > 600 or not name or len(name) > 40:
        raise ValueError('Say 1-600 characters, with a name of 1-40 characters')
    with (Path(run) / 'inbox.jsonl').open('a') as inbox:
        inbox.write(json.dumps({'text': text, 'to': to, 'name': name, 'written': time.time()}) + '\n')


def _target(engine, to):
    """The active conversation to speak into: one including `to` (an id or name), else the most recent."""
    names = {k: e['name'].lower() for k, e in engine.state['entities'].items()}
    handles = {k: e['facts'].get('handle') for k, e in engine.state['entities'].items()}
    sessions = [(k, s) for k, s in engine.state['runtime'].get('conversations', {}).items()
                if s['status'] != 'closed' and s['active']]
    if to:
        wanted = to.lower()
        wanted = wanted.lstrip('@')
        sessions = [(k, s) for k, s in sessions if any(wanted in (p, names.get(p), handles.get(p)) for p in s['active'])]
    return max(sessions, key=lambda ks: (ks[1]['turns'][-1]['day'] if ks[1]['turns'] else ks[1]['spec']['day'], ks[0]), default=None)


def call(run, to, name='Visitor'):
    """Ring a person (id, @handle or unique name). Then call_say lines, and hang_up. Replies land in RUN/calls.jsonl."""
    to, name = str(to).strip(), ' '.join(str(name).split())
    if not to or not name or len(name) > 40:
        raise ValueError('Call someone by id, @handle or name, with your name of 1-40 characters')
    _append(run, {'kind': 'call', 'to': to, 'name': name})


def talk(run, to, text, name='Visitor'):
    """Walk up to a person (id, @handle or unique name) and say text; continue with call_say, end with hang_up."""
    to, name, text = str(to).strip(), ' '.join(str(name).split()), ' '.join(str(text).split())
    if not to or not name or len(name) > 40 or not text or len(text) > 600:
        raise ValueError('Talk to someone by id, @handle or name, saying 1-600 characters, with your name of 1-40 characters')
    _append(run, {'kind': 'talk', 'to': to, 'name': name, 'text': text})


def send(run, character, to, name='Visitor', who=None, age=None, goal=None):
    """Send your own character to a person. A new character needs who (how it presents itself) and age.
    Without a goal you type its lines (call_say); with one, or after auto(), the model plays it. hang_up recalls it."""
    character, name = ' '.join(str(character).split()), ' '.join(str(name).split())
    if not character or len(character) > 40 or not str(to).strip() or not name or len(name) > 40 or len(str(goal or '')) > 300:
        raise ValueError('Send a character (1-40 characters) to someone, with your name and an optional goal of at most 300 characters')
    _append(run, {'kind': 'talk', 'to': str(to).strip(), 'name': name, 'as': character, 'who': who, 'age': age, 'goal': goal})


def auto(run, goal):
    """Hand your character in the current talk to the model, toward goal; typing a line takes it back."""
    goal = ' '.join(str(goal).split())
    if not goal or len(goal) > 300:
        raise ValueError('Give a goal of 1-300 characters')
    _append(run, {'kind': 'auto', 'goal': goal})


LINE_HELP = ("@priya hello walks up to Priya · then just type · /bye ends · /call priya phones · "
             "/send Kabir @priya a new classmate, 15 sends your character (who and age the first time) · /auto GOAL lets the model play it")


def talk_line(run, text, name='Visitor'):
    """One typed line, as in the watcher's t key and the cockpit's box; returns what was done (ValueError if nothing)."""
    from .watch import latest_call
    text = ' '.join(str(text).split())
    if not text:
        raise ValueError(LINE_HELP)
    command, _, rest = text.partition(' ')
    if command in ('/bye', '/hangup', '/recall'):
        hang_up(run)
        return 'ending the talk'
    if command == '/auto':
        auto(run, rest)
        return 'the model now plays your character'
    if command == '/call':
        call(run, rest, name)
        return f'calling {rest}'
    if command == '/send':
        match = re.fullmatch(r'(\S+)\s+@(\S+)(?:\s+(.+?))?(?:,\s*(\d+(?:\.\d+)?))?', rest)
        if not match:
            raise ValueError('Use /send NAME @PERSON, adding who and age the first time: /send Kabir @priya a new classmate, 15')
        character, to, who, age = match.groups()
        send(run, character, to, name, who, float(age) if age else None)
        return f'sending {character} to {to}: type their lines'
    if command.startswith('/'):
        raise ValueError(LINE_HELP)
    current = latest_call(Path(run))
    if current and current['active']:
        call_say(run, text)
        return 'said'
    if text.startswith('@') and rest:
        talk(run, command[1:], rest, name)
        return f'walking over to {command[1:]}'
    say(run, text, None, name)
    return 'said into the most recent group conversation (start with @name to talk to one person)'


def call_say(run, text):
    text = ' '.join(str(text).split())
    if not text or len(text) > 600:
        raise ValueError('Say 1-600 characters')
    _append(run, {'kind': 'call_line', 'text': text})


def hang_up(run):
    _append(run, {'kind': 'hangup'})


def _append(run, note):
    with (Path(run) / 'inbox.jsonl').open('a') as inbox:
        inbox.write(json.dumps({**note, 'written': time.time()}) + '\n')


def call_log(run):
    """Every call event written so far (ringing, answered, said, ended...), oldest first."""
    try:
        return [json.loads(line) for line in (Path(run) / 'calls.jsonl').read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def _next_note(controller, path, wait_seconds):
    """The next complete call inbox line (consumed), waiting up to wait_seconds of real time; None on timeout.

    A note of another kind (a new call or talk, or a line for a group conversation) is left in the inbox and
    returned as {'kind': 'other'}: the researcher has moved on. Before, the open call swallowed it (a line meant
    for a conversation was spoken on the phone; a second call vanished).
    """
    runtime = controller.engine.state['runtime']
    end = time.monotonic() + wait_seconds
    while True:
        try:
            with open(path, 'rb') as stream:
                stream.seek(runtime.get('inbox_offset', 0))
                line = stream.readline()
        except OSError:
            line = b''
        if line.endswith(b'\n'):
            try:
                note = json.loads(line)
            except ValueError:
                runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line)  # unreadable: skip it
                continue
            if not isinstance(note, dict) or note.get('kind') not in ('call_line', 'hangup', 'auto'):
                return {'kind': 'other'}  # not consumed: deliver_inbox handles it once this call ends
            runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line)
            return note
        if time.monotonic() >= end:
            return None
        time.sleep(.2)


def _character(engine, note):
    """The researcher's own character, created on first use as a full agent (sampled personality, own memory).

    Only characters made this way can be voiced or sent; people of the simulated world keep their own will.
    """
    key = re.sub(r'[^a-z0-9]+', '-', str(note['as']).lower()).strip('-')
    entity = engine.state['entities'].get(key)
    if entity is None:
        who, age = ' '.join(str(note.get('who') or '').split())[:200], note.get('age')
        if not who or isinstance(age, bool) or not isinstance(age, (int, float)) or not 1 <= age <= 100:
            raise ValueError('A new character needs --who (how they present themselves) and --age (1-100)')
        engine.entity(key, ' '.join(str(note['as']).split())[:40],
                      {'sent_by': str(note.get('name') or 'Visitor'), 'description': who, 'birth_day': engine.day - age * 365.25})
        engine.materialize_for_interaction(key)
    elif 'sent_by' not in entity['facts']:
        raise ValueError(f'{entity["name"]} belongs to the simulated world; send a character you created')
    if key not in engine.state['agents'] or not engine.agent(key)['alive']:
        raise ValueError('That character is not available')
    return key


def _ring(controller, path, note):
    """A phone call, or (kind 'talk') a face-to-face conversation. The world waits (no simulated time passes) while
    the researcher and the person talk, and every researcher line gets that person's reply turn.

    Phone: the person decides whether to answer; someone mid-conversation may step away. People in the same room
    notice the ringing and hear only the person's side. Unknown callers show as an unknown number.
    Face to face: the researcher walks up to the person, who may reply, stay quiet or end it. People in the room
    see the visitor come and go but do not appraise every line (keeps a reply to ~3 model calls). This replaces
    speaking into a group conversation, where lines were ignored and the 6-turn session ended before a second line
    arrived (environment-v2 run-2, days 9-11). Both end on hanging up or walking away, the researcher's silence,
    or 30 exchanges. Each reply decision sees the exchange so far, not only search-ranked memories.
    Sent character (note 'as'): the visitor is the researcher's own persistent character, who remembers both sides.
    The researcher types its lines, or with a goal ('goal', or a later '/auto') the model plays it; typing takes it
    back, and hanging up recalls it.
    """
    engine = controller.engine
    runtime = engine.state['runtime']
    face = note.get('kind') == 'talk'
    calls = runtime.setdefault('calls', [])
    n = len(calls)
    outbox = Path(path).parent / 'calls.jsonl'
    def log(event, **extra):
        with outbox.open('a') as stream:
            stream.write(json.dumps({'call': n, 'event': event, 'day': engine.day, **extra, 'written': time.time()}) + '\n')
    wanted = str(note.get('to') or '').lower().lstrip('@')
    exact = [k for k, e in engine.state['entities'].items() if wanted in (k, e['facts'].get('handle'))]
    named = [k for k, e in engine.state['entities'].items() if e['name'].lower() == wanted]
    match = [k for k in (exact or named) if k in engine.state['agents'] and engine.agent(k)['alive']]
    record = {'to': note.get('to'), 'day': engine.day, 'written': note.get('written'), 'turns': 0,
              'mode': 'in_person' if face else 'phone'}
    calls.append(record)
    name = ' '.join(str(note.get('name') or 'Visitor').split())[:40]
    try:
        caller = _character(engine, note) if face and note.get('as') else None
    except ValueError as exc:
        record['outcome'] = str(exc)
        return log('failed', reason=str(exc))
    if len(match) != 1 or match[0] == caller:
        record['outcome'] = 'no such person' if not match or match[0] == caller else 'ambiguous name'
        return log('failed', reason=record['outcome'] + ': use an id or @handle')
    owner = match[0]
    if caller is None:
        caller = 'visitor-' + (re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'guest')
        if caller not in engine.state['entities']:
            engine.entity(caller, name, {'visitor': True})
    character = caller in engine.state['agents']  # a sent character perceives and remembers its own side
    record.update(owner=owner, caller=caller, **({'character': caller} if character else {}))
    shown = engine.label(caller) if face or caller in engine.agent(owner)['relationships'] else 'an unknown number'
    me = engine.label(owner)
    room = household.location(engine, owner)
    nearby = [] if room is None else [p for p in engine.state['agents'] if p not in (owner, caller)
                                      and household.available(engine, p) and household.present(engine, p, room)]
    def event(tag, description, own, heard=None, action_id=None, source='self', theirs=None):
        # Face to face, the visitor is physically met: a firsthand encounter for the person (and anyone watching).
        observations = {owner: {'text': own, 'source': source, 'kind': 'direct', **({'encountered': [caller]} if face else {}),
                                **({'addressed': [owner]} if source != 'self' else {})}}  # the caller speaks to them
        if heard:
            observations.update({p: {'text': heard, 'source': owner, 'kind': 'direct',
                                     'encountered': [owner, caller] if face else [owner]} for p in nearby})
        if character and theirs:
            observations[caller] = {'text': theirs, 'source': 'self', 'kind': 'direct', 'encountered': [owner]}
        household.deliver(controller, f'@call:{n}:{tag}', description, observations, action_id)
    def decide(who, tag, situation, menu, fallback):
        # Seeing (or hearing) someone brings back memories of them. Without this, run-2 Priya's three memories of the
        # researcher ranked below topic matches and her context showed only "acquaintance". This exchange is in "So far".
        other, meta = caller if who == owner else owner, engine.agent(who)['memory_meta']
        about = [o.event_id for o in engine.world.observations.get(who, []) if not o.event_id.startswith(f'@call:{n}:')
                 and (o.source == other or other in meta[o.event_id].get('encountered', []))]
        engine.agent(who)['retrieval_focus'] = {'day': engine.day, 'situation': situation, 'ids': about[-4:],
                                                'policy': 'person_cued_recall'}
        if controller.scripted:
            proposal = {'owner': who, 'day': engine.day, 'context': engine.context(who, situation, ['social'], menu),
                        'decision': {'action_id': fallback[0], 'action': 'Respond.', 'speech': fallback[1],
                                     'goal_id': None, 'plan': [], 'memory_ids': []}}
        else:
            proposal = engine.propose(who, situation, cues=['social'], options=menu, api=controller.api, model=controller.model)
        engine.commit_action(f'@call:{n}:{tag}:action', proposal)
        return proposal['decision']
    log('approaching' if face else 'ringing', to=owner, label=me)
    owner_sent = 'sent_by' in engine.state['entities'][owner]['facts']  # your own character can be talked to anywhere
    if not household.available(engine, owner) or (face and room is None and not owner_sent):
        record['outcome'] = 'unavailable' if face else 'missed'
        if face:  # asleep, busy or travelling: they never notice the visitor
            return log('failed', reason=f'{me} is not available now (asleep, busy or travelling)')
        event('missed', 'A phone call goes unanswered.', f'I missed a phone call from {shown}.', source=caller)
        return log('missed', reason=f'{me} is not available now (asleep or busy)')
    session = next((k for k, s in runtime.get('conversations', {}).items() if s['status'] != 'closed' and owner in s['active']), None)
    place = household_place(engine, session) if session else \
        'in ' + engine.state['config'].get('household', {}).get('rooms', {}).get(room, {}).get('label', 'this room')
    transcript = []  # (speaker, text or None for silence): this exchange, shown in each decision from that side
    def so_far(person):
        return ' So far: ' + ' / '.join(('You' if who == person else engine.label(who)) + (f': {text}' if text else ' stayed quiet')
                                        for who, text in transcript[-8:]) if transcript else ''
    if face:
        about = engine.state['entities'][caller]['facts'].get('description')
        first_meeting = about and caller not in engine.agent(owner)['relationships']
        event('pickup', 'A visitor (the researcher) comes over to talk with a person; spoken claims are not world facts.',
              f'{shown}' + (f' ({about})' if first_meeting else '') + ' came over to talk with me' +
              (', so I stepped aside from the conversation.' if session else '.'),
              f'{shown} came over to talk with {me}.', source=caller, theirs=f'I went over to talk with {me}.')
        log('joined', label=me)
    else:
        doing = (f'You are in the middle of a conversation ({place}).' if session else 'You are not in a conversation right now.')
        pick = decide(owner, 'pickup', f'Your phone rings: {shown} is calling. {doing} People often step away mid-conversation to '
                      'take a call, or let it ring; decide as yourself. If you answer, speech is your first words on the phone.',
                      [{'id': 'answer', 'label': 'Answer the phone.', 'speech_allowed': True, 'plan_allowed': False},
                       {'id': 'ignore', 'label': 'Let it ring.', 'speech_allowed': False, 'plan_allowed': False}], ('answer', 'Hello?'))
        if pick['action_id'] != 'answer':
            record['outcome'] = 'not answered'
            event('pickup', 'A phone rings and is not answered.', f'My phone rang ({shown}); I let it ring.',
                  f"{me}'s phone rang; they let it ring.", f'@call:{n}:pickup:action')
            return log('not answered')
        hello = pick.get('speech') or 'Hello?'
        away = ' stepped away from the conversation to answer a phone call.' if session else ' answered a phone call.'
        event('pickup', 'A person answers a phone call; spoken claims are not world facts.', f'I answered a phone call from {shown}. I said: {hello}',
              me + away, f'@call:{n}:pickup:action')
        transcript.append((owner, hello))
        log('answered', text=hello, label=me)
    first = ' '.join(str(note.get('text') or '').split())[:600] if face else ''
    goal = ' '.join(str(note.get('goal') or '').split())[:300] if character else ''
    wait = getattr(controller, 'call_wait_seconds', 300)
    for turn in range(30):
        line = {'kind': 'call_line', 'text': first} if first else _next_note(controller, path, 0 if goal else wait)
        first = ''
        if line is not None and line.get('kind') == 'auto':
            goal = ' '.join(str(line.get('goal') or '').split())[:300] if character else ''
            if not goal:
                continue
            line = None
        elif line is not None and line.get('kind') == 'call_line':
            goal = ''  # typing takes the character back
        left, departing = False, ''
        if line is None and goal:  # the model plays the character, toward the researcher's aim
            pick = decide(caller, f'envoy-{turn}', f'You are {shown}, {engine.state["entities"][caller]["facts"]["description"]}. '
                          f'{name} asked you to go and talk with {me} {place}. Your aim: {goal}. Pursue it as yourself, one '
                          f'spoken turn at a time, and end the conversation when you are done or it is going nowhere.{so_far(caller)}',
                          [{'id': 'speak', 'label': 'Say something (one spoken turn, usually one to three sentences).',
                            'speech_allowed': True, 'plan_allowed': False},
                           {'id': 'end', 'label': 'Say goodbye and leave.', 'speech_allowed': True, 'plan_allowed': False}],
                          ('speak', 'How are things going?'))
            line = {'kind': 'call_line', 'text': pick.get('speech') or ''}
            if pick['action_id'] == 'end':
                left, departing = True, line['text']
                line = {'kind': 'hangup', 'goodbye': departing}
            else:
                log('said', text=line['text'], label=shown)
        if line is not None and line.get('kind') == 'other':
            line = {'kind': 'hangup'}  # the researcher's next note is something else: they have hung up and moved on
        if line is None or line.get('kind') == 'hangup':
            record['outcome'] = 'caller went silent' if line is None else ('character left' if left else 'caller hung up')
            if face:
                goodbye = f' {shown} said: {departing}' if departing else ''
                event(f'end-{turn}', 'A visitor leaves.', f'{shown} stopped talking, so I turned back to what I was doing.' if line is None
                      else f'{shown} said goodbye and walked away.' + goodbye, f'{shown} walked away from {me}.', source=caller,
                      action_id=f'@call:{n}:envoy-{turn}:action' if left else None,
                      theirs=f'I said goodbye to {me} and left.' + (f' I said: {departing}' if departing else ''))
            else:
                event(f'end-{turn}', 'A phone call ends.', 'The caller went silent, so I ended the call.' if line is None else 'The caller hung up.',
                      source='self' if line is None else caller)
            log('ended', reason=record['outcome'])
            break
        text = ' '.join(str(line.get('text', '')).split())[:600]
        if not text:
            continue
        record['turns'] += 1
        transcript.append((caller, text))
        event(f'heard-{turn}', 'A visitor speaks to a person face to face; spoken claims are not world facts.' if face else
              'A caller speaks on the phone; spoken claims are not world facts.',
              f'{shown} said to me: {text}' if face else f'{shown} (on the phone): {text}', source=caller,
              action_id=f'@call:{n}:envoy-{turn}:action' if goal else None, theirs=f'I said to {me}: {text}')
        if face:
            reply = decide(owner, f'reply-{turn}', f'{shown} is standing with you {place} and talking to you directly; they have just '
                           f'spoken and are waiting for your reply.{so_far(owner)} Reply as yourself, stay quiet, or end the conversation.',
                           [{'id': 'speak', 'label': 'Say something to them (one spoken turn, usually one to three sentences).',
                             'speech_allowed': True, 'plan_allowed': False},
                            {'id': 'listen', 'label': 'Stay quiet.', 'speech_allowed': False, 'plan_allowed': False},
                            {'id': 'end', 'label': 'End the conversation and turn away.', 'speech_allowed': True, 'plan_allowed': False}],
                           ('speak', 'Mm-hm.'))
        else:
            reply = decide(owner, f'reply-{turn}', f'You are on a phone call with {shown}.{so_far(owner)} Reply as yourself, or hang up.',
                           [{'id': 'speak', 'label': 'Say something on the phone (one spoken turn).', 'speech_allowed': True, 'plan_allowed': False},
                            {'id': 'hang_up', 'label': 'End the call.', 'speech_allowed': True, 'plan_allowed': False}], ('speak', 'Mm-hm.'))
        said = '' if reply['action_id'] == 'listen' else reply.get('speech') or ''
        if said:
            transcript.append((owner, said))
            event(f'reply-{turn}', 'A person speaks; spoken claims are not world facts.',
                  (f'I said to {shown}: ' if face else 'I said on the phone: ') + said,
                  None if face else f'{me} said on the phone: {said}', f'@call:{n}:reply-{turn}:action', theirs=f'{me} said to me: {said}')
            log('said', text=said, label=me)
        elif reply['action_id'] == 'listen':
            transcript.append((owner, None))
            event(f'reply-{turn}', 'A person stays quiet.', 'I stayed quiet.', None, f'@call:{n}:reply-{turn}:action', theirs=f'{me} stayed quiet.')
            log('quiet', label=me)
        if reply['action_id'] in ('hang_up', 'end'):
            record['outcome'] = 'they hung up' if not face else 'they ended it'
            event(f'end-{turn}', 'A phone call ends.' if not face else 'A person ends a conversation.',
                  'I ended the call.' if not face else 'I ended the conversation and turned away.',
                  f'{me} hung up the phone.' if not face else f'{me} turned away from {shown}.',
                  None if said else f'@call:{n}:reply-{turn}:action', theirs=f'{me} turned away from me.')
            log('ended', reason=f'{me} hung up' if not face else f'{me} ended the conversation')
            break
    else:
        record['outcome'] = 'call limit'
        log('ended', reason='30 exchanges')
    if session and runtime['conversations'][session]['status'] != 'closed' and nearby:
        event('back', 'A person returns to a conversation after a call.', 'I came back to the conversation.', f'{me} came back to the conversation.')


def household_place(engine, key):
    spec = engine.state['runtime']['conversations'][key]['spec']
    cfg = engine.state['config'].get('household', {})
    if 'channel' in spec:
        return 'a written chat'
    return 'in ' + cfg.get('rooms', {}).get(spec.get('room'), {}).get('label', 'this room')


def deliver_inbox(controller, path):
    """Deliver complete inbox lines that have a conversation to go into; True if anything was delivered."""
    engine = controller.engine
    runtime = engine.state['runtime']
    try:
        with open(path, 'rb') as stream:
            stream.seek(runtime.get('inbox_offset', 0))
            chunk = stream.read()
    except OSError:
        return False
    delivered = False
    for line in chunk.split(b'\n')[:-1]:  # the last piece is empty or still being written
        try:
            note = json.loads(line)
            if note.get('kind') in ('call', 'talk'):
                runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line) + 1
                _ring(controller, path, note)  # consumes the call's own lines from the inbox
                return True
            if note.get('kind') in ('call_line', 'hangup', 'auto'):  # no call in progress: nothing to say it into
                runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line) + 1
                continue
            text, name = str(note['text']), str(note['name'])
        except (ValueError, KeyError, TypeError):
            runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line) + 1  # unreadable: skip it
            continue
        target = _target(engine, note.get('to'))
        if target is None:
            break  # wait, in order, until a conversation is active
        key, session = target
        visitor = 'visitor-' + (re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'guest')
        if visitor not in engine.state['entities']:
            engine.entity(visitor, name, {'visitor': True})
        spec = session['spec']
        channel = 'channel' in spec
        if channel:
            hearers = [p for p in engine.state['config']['household']['channels'][spec['channel']]['members']
                       if household.available(engine, p)]
        else:
            audible = [spec['room'], *engine.state['config']['household']['rooms'][spec['room']].get('audible_to', [])]
            hearers = [p for p in engine.state['agents'] if household.available(engine, p)
                       and any(household.present(engine, p, r) for r in audible)]
        hearers = list(dict.fromkeys([*session['active'], *hearers]))
        number = len(runtime.setdefault('visitor_log', []))
        event_id = f'@conversation:{key}:visitor-{number}'
        # Name the addressee: without it, every hearer took the line as meant for them (environment-v2 run-2, day 11).
        to = str(note.get('to') or '').lower().lstrip('@')
        exact = [k for k, e in engine.state['entities'].items() if to and to in (k, e['facts'].get('handle'))]
        named = [k for k, e in engine.state['entities'].items() if to and e['name'].lower() == to]
        match = exact or named
        addressee = engine.label(match[0]) if len(match) == 1 else None  # a shared name names nobody in particular
        verb = (' wrote' if channel else ' said') + (' to ' + addressee if addressee else '') + ': '
        observations = {p: {'text': engine.label(visitor) + verb + text, 'source': visitor, 'kind': 'direct',
                            'encountered': [] if channel or not household.present(engine, p, spec.get('room')) else [visitor],
                            'provenance': event_id, **({'addressed': [match[0]]} if addressee else {})} for p in hearers}
        household.deliver(controller, event_id, 'A visitor (the researcher) speaks; spoken claims are not world facts.', observations)
        runtime['visitor_log'].append({'event': event_id, 'day': engine.day, 'conversation': key, 'visitor': visitor,
                                       'text': text, 'hearers': hearers, 'written': note.get('written')})
        runtime['inbox_offset'] = runtime.get('inbox_offset', 0) + len(line) + 1
        delivered = True
    return delivered


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='The live run directory (where requests.jsonl is written)')
    parser.add_argument('text', nargs='?', help='What you say (omit with --call)')
    parser.add_argument('--talk', metavar='PERSON', help='Walk up to a person (id, @handle or name) and talk until /bye')
    parser.add_argument('--call', metavar='PERSON', help='Phone a person (id, @handle or name) and chat until /bye')
    parser.add_argument('--send', metavar='CHARACTER', help='Send your own character (created on first use) to --to')
    parser.add_argument('--who', help='--send, first time: how the character presents itself, e.g. "a new classmate"')
    parser.add_argument('--age', type=float, help='--send, first time: the character\'s age in years')
    parser.add_argument('--goal', help='--send: let the model play the character toward this aim (type to take over)')
    parser.add_argument('--recall', action='store_true', help='Recall your character (or end the current talk or call)')
    parser.add_argument('--to', help='The person to send a character to, or whose active conversation you speak into')
    parser.add_argument('--name', default='Visitor', help='The name people will know you by')
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error('Give the live run directory')
    if args.recall:
        hang_up(args.run)
        return print('Recalled; it takes effect at the talk\'s next turn.')
    if args.send:
        if not args.to:
            parser.error('--send needs --to PERSON')
        return send_and_follow(args.run, args.send, args.to, args.name, args.who, args.age, args.goal)
    if args.call or args.talk:
        return phone(args.run, args.call or args.talk, args.name, in_person=bool(args.talk))
    if not args.text:
        parser.error('Give what you say, or --call PERSON')
    say(args.run, args.text, args.to, args.name)
    print('Queued; it is delivered at the next event in an active conversation.')


def _show(row, person):
    label = row.get('label') or person
    if row['event'] in ('ringing', 'approaching'):
        return f"  {row['event']} {label}..."
    if row['event'] == 'joined':
        return f'  [{label} turns to you]'
    if row['event'] == 'quiet':
        return f'  {label}: (stays quiet)'
    if row['event'] == 'said':
        return f"  {label}: {row.get('text', '')}"
    if row['event'] == 'answered':
        return f"  [answered] {row.get('text', '')}"
    return f"  [{row['event']}] {row.get('reason', '')}"


def send_and_follow(run, character, person, name, who=None, age=None, goal=None):
    """Send your character and follow the talk: type its lines, '/auto GOAL' hands it to the model, '/bye' recalls it.
    While the model plays it, typing a line takes it back."""
    from threading import Event, Thread
    seen = len(call_log(run))
    send(run, character, person, name, who, age, goal)
    print(f'Sending {character} to {person} (at the simulation\'s next event). Type {character}\'s lines; '
          "'/auto GOAL' lets the model play them, '/bye' recalls them.")
    done = Event()
    def follow():
        nonlocal seen
        while not done.is_set():
            for row in call_log(run)[seen:]:
                seen += 1
                print(_show(row, person), flush=True)
                if row['event'] in ('ended', 'failed'):
                    print('  (press Enter)', flush=True)
                    done.set()
            time.sleep(.5)
    Thread(target=follow, daemon=True).start()
    while not done.is_set():
        try:
            text = input().strip()
        except (EOFError, KeyboardInterrupt):
            text = '/bye'
        if done.is_set():
            break
        if text in ('/bye', '/recall'):
            hang_up(run)
            done.wait()
        elif text.startswith('/auto'):
            try:
                auto(run, text[5:])
            except ValueError as exc:
                print('  ' + str(exc))
        elif text:
            call_say(run, text)


def phone(run, person, name, in_person=False):
    """Interactive call or face-to-face talk from a terminal: type lines, /bye to end. Starts at the next event boundary."""
    seen = len(call_log(run))
    if in_person:
        first = ''
        while not first:
            first = input(f'{name} (to {person}): ').strip()
        if first in ('/bye', '/hangup'):
            return
        talk(run, person, first, name)
        print(f'Walking over to {person}... (at the simulation\'s next event; /bye walks away)')
    else:
        call(run, person, name)
        print(f'Calling {person}... (it rings at the simulation\'s next event; /bye hangs up)')
    def wait_for(kinds):
        nonlocal seen
        while True:
            log = call_log(run)
            for row in log[seen:]:
                seen += 1
                print(_show(row, person))
                if row['event'] in kinds:
                    return row['event']
            time.sleep(.5)
    if in_person:
        if wait_for({'said', 'quiet', 'failed', 'ended'}) in ('failed', 'ended'):
            return
    elif wait_for({'answered', 'not answered', 'missed', 'failed', 'ended'}) != 'answered':
        return
    while True:
        try:
            text = input(f'{name}: ').strip()
        except (EOFError, KeyboardInterrupt):
            text = '/bye'
        if text in ('/bye', '/hangup'):
            hang_up(run)
            wait_for({'ended'})
            return
        if text:
            call_say(run, text)
            if wait_for({'said', 'quiet', 'ended'}) == 'ended':
                return


if __name__ == '__main__':
    main()
