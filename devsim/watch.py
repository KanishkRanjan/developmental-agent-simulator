"""Full-screen terminal view of a running (or finished) simulation; works over plain SSH.

    python3 -m devsim.watch runs/live/RUN_DIR

Left: each person's place (or "in transit") and current mood, or call statistics (s). Right: the
conversation feed built from committed actions, or (l) the engine view: every model call with what
it was asked and what came back. Status line: what the model is working on now, simulation pace and
time remaining. Keys: q quit, up/down/PgUp/PgDn scroll (End follows live), a all decisions or only
speech, l story/engine view, v full text in the engine view, s people/stats, 1-9 one person (0 all),
h help: how to talk to people, with examples,
g graphs (tokens per minute, generation speed, seconds per call, how each person's days felt, what runs now and next),
c call someone on the phone (then t speaks into the call, /bye hangs up),
t talk: '@priya hello' walks up to Priya (then t and type continues, /bye ends), '/call priya' phones,
  '/send Kabir @priya a new classmate, 15' sends your character, '/auto GOAL' lets the model play it;
  text without @name, with no talk going on, is spoken into the most recent active group conversation.
Reading the run never changes it; talking only appends to inbox.jsonl (see devsim.visit).
"""
import argparse
from collections import deque
import json
from math import floor
from pathlib import Path
import textwrap
import time

from .engine import Engine

WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def clock(day):
    minutes = round((day - floor(day)) * 1440)
    return f'd{floor(day)} {minutes // 60:02d}:{minutes % 60:02d}'


def where(engine, action_id):
    """A short label for where an action happened, from the run's own records."""
    runtime = engine.state.get('runtime', {})
    config = engine.state['config'].get('household', {})
    if action_id.startswith('@conversation:'):
        key = action_id.split(':')[1]
        spec = runtime.get('conversations', {}).get(key, {}).get('spec', {})
        if 'channel' in spec:
            place = config.get('channels', {}).get(spec['channel'], {}).get('label', spec['channel'])
        else:
            place = config.get('rooms', {}).get(spec.get('room'), {}).get('label', spec.get('room', '?'))
        if key.startswith('group-'):
            group = key[len('group-'):].rsplit('-', 1)[0]
            place += ' · ' + config.get('groups', {}).get(group, {}).get('label', group)
        return place + (' · interview' if 'questions' in spec else '')
    if action_id.startswith('@invitation:'):
        return 'invitation'
    if action_id.startswith('life-'):
        return 'situation: ' + action_id.split('-', 2)[2].rsplit('-action', 1)[0].replace('_', ' ')
    return action_id.split(':')[0].lstrip('@')


def load(run):
    """Everything the screen shows, read fresh from the run directory."""
    world_path, requests_path = run / 'world.json', run / 'requests.jsonl'
    summary = json.loads((run / 'summary.json').read_text()) if (run / 'summary.json').exists() else {}
    last, calls = None, 0
    if requests_path.exists():
        lines = requests_path.read_text().splitlines()
        calls = len(lines)
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:  # the last line may be mid-write
                continue
            last = {'purpose': row.get('purpose'), 'agent': row.get('agent'), 'day': row.get('simulated_day')}
            break
    data = {'status': summary.get('status', 'running'), 'calls': calls, 'last': last, 'people': [], 'feed': []}
    policy_path = run / 'policy-used.json'
    if policy_path.exists():
        data['horizon'] = json.loads(policy_path.read_text()).get('horizon_days')
        data['started'] = policy_path.stat().st_mtime
    current = run / 'current.json'
    try:
        data['current'] = json.loads(current.read_text())  # the call in flight, written by run_live
    except (OSError, ValueError):
        data['current'] = None
    if requests_path.exists():
        data['last_finished'] = requests_path.stat().st_mtime
    if not world_path.exists():
        return data
    engine = Engine.load(world_path)
    data['habituated'] = sum('reused_appraisal' in m for a in engine.state['agents'].values() for m in a['memory_meta'].values())
    data['skipped'] = len(engine.state.get('runtime', {}).get('skipped_model_steps', []))
    names = {k: e['name'] for k, e in engine.state['entities'].items()}
    rooms = engine.state['config'].get('household', {}).get('rooms', {})
    locations = engine.state.get('household', {}).get('locations', {})
    data['day'] = engine.day
    for owner in sorted(engine.state['agents']):
        agent = engine.agent(owner)
        if not agent['alive']:
            place = 'died'
        elif owner in locations and locations[owner] is None:
            place = 'in transit'
        else:
            place = rooms.get(locations.get(owner), {}).get('label', locations.get(owner) or '')
        data['people'].append({'id': owner, 'name': names.get(owner, owner), 'place': place, 'mood': engine.mood(owner)})
    for action in sorted(engine.state['actions'], key=lambda a: (a['day'], a['id'])):
        decision = action['decision']
        data['feed'].append({'day': action['day'], 'owner': action['owner'], 'name': names.get(action['owner'], action['owner']),
                             'where': where(engine, action['id']), 'choice': decision.get('action_id'),
                             'label': decision.get('action') or '', 'speech': decision.get('speech') or ''})
    visits = engine.state.get('runtime', {}).get('visitor_log', [])
    data['feed'] += [{'day': v['day'], 'owner': v['visitor'], 'name': names.get(v['visitor'], 'Visitor') + ' (you)',
                      'where': where(engine, v['event']), 'choice': 'speak', 'label': '', 'speech': v['text']} for v in visits]
    data['feed'].sort(key=lambda item: item['day'])
    try:
        with open(run / 'inbox.jsonl', 'rb') as inbox:
            inbox.seek(engine.state.get('runtime', {}).get('inbox_offset', 0))
            data['waiting_to_say'] = inbox.read().count(b'\n')
    except OSError:
        data['waiting_to_say'] = 0
    runtime = engine.state.get('runtime', {})
    upcoming = [(d, 'situation ' + k) for k, d in runtime.get('next_opportunities', {}).items() if d is not None]
    upcoming += [(s['next_day'], 'conversation ' + k) for k, s in runtime.get('conversations', {}).items() if s.get('next_day') is not None]
    upcoming += [(g['next_day'], 'meeting ' + k) for k, g in runtime.get('group_meetings', {}).items() if g.get('next_day') is not None]
    upcoming += [(t['day'], 'arrival ' + k) for k, t in runtime.get('trips', {}).items()]
    upcoming += [(d, 'room change ' + k) for k, d in runtime.get('household_moves', {}).items() if d is not None]
    upcoming += [(a['day'], 'activity ends ' + k) for k, a in runtime.get('pending_activities', {}).items()]
    upcoming += [(d, 'recall by ' + names.get(k, k)) for k, d in runtime.get('next_background', {}).items() if d is not None]
    data['upcoming'] = sorted(u for u in upcoming if u[0] >= engine.day)[:5]
    felt = []
    for person in data['people']:
        days = {}
        for o in engine.world.observations.get(person['id'], []):
            days.setdefault(floor(o.day), []).append(o.valence)
        felt.append((person['name'], [sum(days[d]) / len(days[d]) if d in days else None for d in range(max(0, floor(engine.day)) + 1)]))
    data['felt'] = felt
    data['call'] = latest_call(run)
    return data


def latest_call(run):
    """The most recent phone call or face-to-face talk: its events (calls.jsonl) merged with what you said (inbox.jsonl)."""
    from .visit import call_log
    try:
        notes = [json.loads(line) for line in (run / 'inbox.jsonl').read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        notes = []
    placed = [i for i, n in enumerate(notes) if n.get('kind') in ('call', 'talk')]
    if not placed:
        return None
    log = call_log(run)
    newest = max((r['call'] for r in log), default=None)
    events = [r for r in log if r['call'] == newest]
    if events and events[0].get('written', 0) < notes[placed[-1]].get('written', 0):
        events = []  # the latest request has not rung yet; the log's newest call is an earlier one
    start = notes[placed[-1]]
    said = [{'event': 'you', 'text': n.get('text', ''), 'written': n.get('written', 0)}
            for n in notes[placed[-1]:] if n.get('kind') == 'call_line' or (n is start and n.get('text'))]
    merged = sorted(events + said, key=lambda r: r.get('written', 0))
    ends = {'ended', 'missed', 'not answered', 'failed'}
    last = events[-1]['event'] if events else None
    state = (('waiting for the next event' + ('' if start.get('kind') == 'talk' else ' to ring')) if last is None
             else last if last in ('ringing', 'approaching')
             else 'talking' if last in ('answered', 'said', 'joined', 'quiet') else 'ended')
    label = next((r['label'] for r in events if r.get('label')), notes[placed[-1]].get('to'))
    return {'label': label, 'state': state, 'events': merged, 'active': last not in ends,
            'in_person': start.get('kind') == 'talk'}


def feed_lines(data, width, everyone=True, only=None):
    """The conversation feed as wrapped text lines with a style tag: 'head', 'speech' or 'quiet'."""
    lines, previous = [], None
    for item in data['feed']:
        if only and item['owner'] != only:
            continue
        if not everyone and not item['speech']:
            continue
        head = f'{clock(item["day"])}  {item["where"]}'
        if head != previous:
            lines.append(('head', head[:width]))
            previous = head
        if item['speech']:
            text, style = f'{item["name"]}: "{item["speech"]}"', 'speech'
        else:
            label = item['label'] if item['label'] and item['label'].lower() != item['choice'] else item['choice']
            text, style = f'{item["name"]} — {label}', 'quiet'
        lines += [(style, part) for part in textwrap.wrap(text, max(10, width - 2), initial_indent='  ', subsequent_indent='    ')]
    return lines


def _text(value):
    return ' '.join(str(value).split())


def summarize(row):
    """One model call as plain lines: what it was asked (input) and what came back (output)."""
    ctx, out = row.get('context') or {}, row.get('response') or {}
    purpose, situation, given, got = row.get('purpose'), _text(ctx.get('situation', '')), [], []
    if purpose == 'appraisal':
        given.append('perceives: ' + _text(ctx.get('new_observation', {}).get('text', '')))
        if ctx.get('earlier_questions_from_speaker'):
            given.append(f'checks against {len(ctx["earlier_questions_from_speaker"])} earlier questions from the same person')
        if out:
            got.append(f'valence {out.get("valence", 0):+.2f}  arousal {out.get("arousal", 0):.2f}  importance {out.get("importance", 0):.2f}')
            got.append('meaning: ' + _text(out.get('meaning', '')))
            if out.get('asked_before'):
                got.append('asked before: yes')
    elif purpose == 'action':
        given.append('situation: ' + situation)
        given.append('options: ' + ', '.join(a['id'] for a in ctx.get('available_actions', [])))
        for key, label in (('repeated_question', 'was asked this {times_asked_before} times before'),):
            if ctx.get(key):
                given.append(label.format(**ctx[key]))
        if ctx.get('repeat_notice'):
            given.append('re-asked: was about to repeat "' + _text(ctx['repeat_notice']['your_earlier_words']) + '"')
        if out:
            got.append('chooses: ' + _text(out.get('action_id') or out.get('action', '')))
            if out.get('speech'):
                got.append('says: "' + _text(out['speech']) + '"')
            if out.get('plan'):
                got.append('plan: ' + '; '.join(_text(x) for x in out['plan']))
    elif purpose == 'semantic_recall':
        candidates = {m['event']: m for m in ctx.get('memory_candidates', [])}
        given += ['situation: ' + situation, f'{len(candidates)} candidate memories']
        if out:
            got += ['recalls: ' + _text(candidates.get(m, {}).get('text', m)) for m in out.get('memory_ids', [])] or ['recalls nothing']
    elif purpose == 'retrieval_query':
        given.append('situation: ' + situation)
        if out:
            got.append('search terms: ' + ' | '.join(_text(q) for q in out.get('queries', [])))
    elif purpose == 'situation':
        rules = {r['id']: r for r in ctx.get('candidate_signatures', [])}
        given += ['situation: ' + situation, f'{len(rules)} personal if-then rules to check']
        if out:
            got.append('reads it as: ' + _text(out.get('meaning', '')))
            top = sorted((out.get('dimensions') or {}).items(), key=lambda kv: -kv[1])[:3]
            got.append('strongest: ' + ', '.join(f'{k} {v:.1f}' for k, v in top) + f'  control {out.get("controllability", 0):.1f}')
            got += [f'rule fires: if {_text(rules.get(r, {}).get("trigger_context", r))} -> {_text(rules.get(r, {}).get("narrative_shift", ""))}'
                    for r in out.get('active_rule_ids', [])]
    elif purpose == 'signatures':
        given.append('writes personal if-then rules from personality')
        got += [f'if {_text(r.get("trigger_context", r.get("trigger_id", "")))} -> {_text(r.get("narrative_shift", r.get("reaction_id", "")))}'
                for r in out.get('rules', [])]
    elif purpose == 'consolidation':
        given.append(f'{len(ctx.get("episodes_to_consolidate", []))} recent experiences to summarize')
        got += ['gist: ' + _text(g.get('text', '')) for g in out.get('gists', [])]
    else:
        given.append(_text(ctx.get('task') or situation))
        if out:
            got.append(_text(json.dumps(out))[:400])
    repair = ctx.get('output_repair')
    return {'day': row.get('simulated_day'), 'agent': row.get('agent'), 'purpose': purpose, 'seconds': row.get('seconds'),
            'repair': repair and _text(repair.get('validation_error', '')), 'input': given, 'output': got}


def read_calls(path, cache):
    """Fold call records appended since the last read into cache: recent summaries and per-purpose totals."""
    try:
        with open(path, 'rb') as stream:
            stream.seek(cache.get('offset', 0))
            chunk = stream.read()
    except OSError:
        return cache
    end = chunk.rfind(b'\n') + 1  # a half-written last line waits for the next read
    cache['offset'] = cache.get('offset', 0) + end
    recent, stats = cache.setdefault('recent', deque(maxlen=300)), cache.setdefault('stats', {})
    for line in chunk[:end].splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        recent.append(summarize(row))
        usage = row.get('usage') or {}
        cache.setdefault('timeline', deque(maxlen=5000)).append({
            'finished': row.get('finished'), 'seconds': row.get('seconds') or 0, 'purpose': row.get('purpose'),
            'day': row.get('simulated_day'), 'prompt': usage.get('prompt_tokens'), 'output': usage.get('completion_tokens'),
            'speed': usage.get('tokens_per_second')})
        total = stats.setdefault(row.get('purpose'), [0, 0.0, 0])
        total[0] += 1
        total[1] += row.get('seconds') or 0
        total[2] += 'output_repair' in (row.get('context') or {})
    return cache


def engine_lines(calls, width, verbose=False, only=None):
    """The engine view: each call's heading, then -> what it was asked and <- what came back."""
    lines, room = [], max(10, width - 2)
    for call in calls:
        if only and call['agent'] != only:
            continue
        seconds = f'{call["seconds"]:.1f}s' if call.get('seconds') is not None else 'running'
        day = clock(call['day']) if call.get('day') is not None else '-'
        lines.append(('head', f'{day}  {call["agent"] or "-"}  {call["purpose"]}  {seconds}'
                              + ('  REPAIRED' if call.get('repair') else ''))[:width])
        for tag, arrow, items in (('quiet', '-> ', call['input']), ('speech', '<- ', call['output'])):
            for item in items:
                item = item if verbose else (item if len(item) <= 2 * room else item[:2 * room - 1] + '…')
                lines += [(tag, part) for part in textwrap.wrap(arrow + item, room, initial_indent='  ', subsequent_indent='     ')]
        if call.get('repair'):
            lines.append(('quiet', ('  ! repair after: ' + call['repair'])[:width]))
    return lines


def stats_lines(data, cache, width):
    lines = [('head', 'model calls'[:width])]
    for purpose, (count, seconds, repairs) in sorted(cache.get('stats', {}).items(), key=lambda kv: -kv[1][0]):
        lines.append(('quiet', f' {purpose[:13]:<13}{count:>5} {seconds / max(count, 1):>4.1f}s'[:width]))
        if repairs:
            lines.append(('speech', f'   repaired {repairs}'[:width]))
    lines += [('head', 'saved / skipped'[:width]), ('quiet', f' habituated {data.get("habituated", 0)}'[:width]),
              ('quiet', f' skipped    {data.get("skipped", 0)}'[:width])]
    return lines


def status_line(data, width, now=None):
    """What the model is doing now, and the simulation's pace and remaining time."""
    now = time.time() if now is None else now
    current = data.get('current')
    if current:
        doing = f'now: {current.get("agent") or "-"} {current.get("purpose")} for {now - current.get("started", now):.0f}s'
    elif data.get('last_finished') and data['status'] == 'running':
        doing = f'waiting {now - data["last_finished"]:.0f}s since the last call'
    else:
        doing = data['status']
    pace = ''
    if data.get('started') and data.get('day') is not None and now > data['started']:
        rate = data['day'] / ((now - data['started']) / 3600)
        pace = f'  |  {rate:.2f} sim days per hour'
        if data.get('horizon') and rate > 0 and data['day'] < data['horizon']:
            left = (data['horizon'] - data['day']) / rate
            pace += f'  |  day {data["day"]:.1f} of {data["horizon"]:.0f}, about {int(left)}h{int(left % 1 * 60):02d}m left'
    waiting = f'  |  {data["waiting_to_say"]} of your lines waiting for a conversation' if data.get('waiting_to_say') else ''
    return f' {doing}{pace}{waiting} '[:width]


BARS = '▁▂▃▄▅▆▇█'


def spark(values, width):
    """One-line chart of the last `width` values (None = no data), scaled to their own maximum."""
    values = list(values)[-width:]
    top = max((v for v in values if v is not None), default=0)
    return ''.join(' ' if v is None else BARS[min(7, int(v / top * 7.999))] if top > 0 else BARS[0] for v in values)


def per_minute(timeline, field, minutes, now):
    """Sums of `field` per wall-clock minute over the last `minutes` (oldest first); None where nothing finished."""
    buckets = [None] * minutes
    for call in timeline:
        if call.get('finished') is None or (field != 'calls' and call.get(field) is None):
            continue
        age = int((now - call['finished']) // 60)
        if 0 <= age < minutes:
            slot = minutes - 1 - age
            buckets[slot] = (buckets[slot] or 0) + (1 if field == 'calls' else call[field])
    return buckets


def graph_lines(data, cache, width, now=None):
    """Graphs: model throughput per minute, per-call speed and time, how each person's days felt, now and next."""
    now = time.time() if now is None else now
    room = max(10, width - 22)
    timeline = list(cache.get('timeline', []))
    lines = [('head', 'now')]
    current = data.get('current')
    if current:
        situation = ((current.get('context') or {}).get('situation') or (current.get('context') or {}).get('new_observation', {}).get('text') or '')
        lines.append(('speech', f'  {current.get("agent") or "-"} · {current.get("purpose")} · {now - current.get("started", now):.0f}s so far'[:width]))
        if situation:
            lines += [('quiet', part) for part in textwrap.wrap(str(situation), width - 4, initial_indent='    ', subsequent_indent='    ')[:2]]
    else:
        lines.append(('quiet', '  no model call in flight'))
    if data.get('call'):
        lines.append(('speech', f'  {"talking with" if data["call"].get("in_person") else "phone call with"} '
                                f'{data["call"]["label"]}: {data["call"]["state"]}'[:width]))
    if data.get('upcoming'):
        lines.append(('head', 'next in the simulation'))
        lines += [('quiet', f'  {clock(day)}  {what}'[:width]) for day, what in data['upcoming']]
    timed = [c for c in timeline if c.get('finished')]
    if not timed:
        lines.append(('quiet', 'no timed calls yet (runs started before this version log no clock times or tokens)'[:width]))
    else:
        minutes = min(room, 60)
        lines.append(('head', f'last {minutes} minutes, one bar per minute'))
        for label, field in (('output tok/min', 'output'), ('prompt tok/min', 'prompt'), ('calls/min', 'calls')):
            series = per_minute(timed, field, minutes, now)
            known = [v for v in series if v is not None]
            note = f' now {series[-1] or 0:.0f} avg {sum(known) / len(series):.0f}' if known else ' no data'
            lines.append(('speech', f' {label:<15}{spark(series, minutes)}{note}'[:width]))
        lines.append(('head', f'last {min(room, len(timed))} calls, one bar per call'))
        for label, field, unit in (('gen tok/s', 'speed', ''), ('seconds/call', 'seconds', 's')):
            series = [c.get(field) for c in timed][-min(room, 60):]
            known = [v for v in series if v is not None]
            note = f' last {known[-1]:.1f}{unit} avg {sum(known) / len(known):.1f}{unit}' if known else ' no data'
            lines.append(('speech', f' {label:<15}{spark(series, len(series))}{note}'[:width]))
    if data.get('felt'):
        lines.append(('head', 'how each day felt (mean appraisal valence per simulated day; mid bar = 0)'[:width]))
        for name, days in data['felt']:
            shifted = [None if v is None else v + 1 for v in days[-room:]]
            last = next((v for v in reversed(days) if v is not None), 0)
            lines.append(('speech', f' {name[:14]:<15}{spark(shifted + [2.0], len(shifted) + 1)[:-1]} {last:+.2f}'[:width]))
    return lines


def call_lines(call, width):
    """The latest phone call's transcript."""
    lines = [('head', f'{"talking with" if call.get("in_person") else "phone call with"} {call["label"]} · {call["state"]}')]
    for row in call['events']:
        if row['event'] in ('answered', 'said'):
            who = row.get('label') or call['label']  # a sent character's lines carry its own label
            lines += [('speech', part) for part in textwrap.wrap(f'{who}: {row.get("text", "")}', width, subsequent_indent='   ')]
        elif row['event'] == 'quiet':
            lines.append(('quiet', f'{call["label"]} stays quiet'[:width]))
        elif row['event'] == 'you':
            lines += [('quiet', part) for part in textwrap.wrap(f'you: {row["text"]}', width, subsequent_indent='   ')]
        else:
            lines.append(('quiet', f'[{row["event"]}] {row.get("reason") or ""}'[:width]))
    if call['state'] == 'talking':
        lines.append(('quiet', 'press t to speak, /bye to ' + ('walk away' if call.get('in_person') else 'hang up')))
    return lines


def help_lines(data, width):
    """The talk guide (key h): how to reach people from this terminal, with examples using this run's people."""
    people = data.get('people') or []
    who = people[0]['id'] if people else 'priya'
    rows = [('head', 'How to talk to people · press h to close'),
            ('quiet', 'Press t, type a line, press Enter. The run picks it up at its next event, and the world waits while you talk.'),
            ('quiet', 'People: ' + (', '.join(f'@{p["id"]} ({p["name"]})' for p in people) or 'none loaded yet')),
            ('quiet', ''), ('head', 'Talk face to face'),
            ('speech', f'@{who} Hi, how was your day?'), ('quiet', f'   walk up to {who} and say it'),
            ('speech', 'That sounds hard. What happened?'), ('quiet', '   keep talking: each line gets their reply'),
            ('speech', '/bye'), ('quiet', '   walk away'),
            ('quiet', ''), ('head', 'Phone'),
            ('speech', f'/call {who}'), ('quiet', '   or press c; they decide whether to answer'),
            ('quiet', ''), ('head', 'Send your own character (a person you create, who remembers every talk)'),
            ('speech', f'/send Kabir @{who} a new classmate, 15'), ('quiet', '   the first time, add who they are and their age'),
            ('speech', 'Hey, are you in the robotics club?'), ('quiet', "   you type Kabir's lines"),
            ('speech', f'/auto make friends with {who}'), ('quiet', '   the model plays Kabir; type any line to take over again'),
            ('speech', '/bye'), ('quiet', '   Kabir says goodbye and leaves'),
            ('speech', '@kabir How did it go?'), ('quiet', '   later: ask Kabir what happened'),
            ('quiet', ''), ('head', 'Group conversation'),
            ('speech', 'Let everyone have a turn.'), ('quiet', '   with no @name and no talk going on: said into the latest group conversation'),
            ('quiet', ''), ('head', 'Good to know'),
            ('quiet', 'People decide how to respond: they may answer, stay quiet or end it.'),
            ('quiet', 'Someone asleep, busy or travelling cannot be reached; a call to them is missed.'),
            ('quiet', 'Scripted runs answer with placeholders; talk in a live run.'),
            ('quiet', 'Without the watcher: python3 -m devsim.visit RUN_DIR --talk NAME (or --call, --send).')]
    lines = []
    for tag, text in rows:
        lines += [(tag, part) for part in (textwrap.wrap(text, max(10, width), subsequent_indent='   ') or [''])]
    return lines


def people_lines(data, width):
    lines = []
    for n, person in enumerate(data['people'], 1):
        mood = person['mood']['valence']
        lines.append(('head', f'{n} {person["name"]}'[:width]))
        lines.append(('quiet', f'  {person["place"]}'[:width]))
        lines.append(('speech', f'  mood {mood:+.2f} {"▲" if mood > .05 else "▼" if mood < -.05 else "■"}'[:width]))
    return lines


def header(data, run, width):
    when = clock(data['day']) if 'day' in data else 'no checkpoint yet'
    name = run.parent.name if run.name == 'run' else run.name
    return f' {name} · {when} · {data["status"]} · {data["calls"]} model calls '[:width]


def footer(data, everyone, only, width, engine=False, verbose=False, graphs=False):
    last = data['last']
    now = f'last call: {last["agent"] or "-"} · {last["purpose"]} · {clock(last["day"])}' if last and last['day'] is not None else 'waiting'
    view = ('graphs' if graphs else 'engine' + (' · full text' if verbose else '') if engine else 'all decisions' if everyone
            else 'speech only') + (f' · {only}' if only else '')
    if data.get('call') and data['call']['active']:
        view = ('talking' if data['call'].get('in_person') else 'phone call') + ' · t to speak, /bye to end'
    return f' {now}  |  {view}  |  h help  t talk  c call  g graphs  l engine  v full  s stats  a speech  1-9 person  0 all  ↑↓  q quit '[:width]


def ask(screen, prompt):
    """A one-line text prompt on the bottom row; empty when cancelled."""
    import curses
    height, width = screen.getmaxyx()
    screen.timeout(-1)
    curses.echo()
    curses.curs_set(1)
    screen.addnstr(height - 1, 0, prompt.ljust(width), width - 1, curses.A_REVERSE)
    try:
        text = screen.getstr(height - 1, min(len(prompt), width - 2), 600).decode('utf8', 'replace')
    except (curses.error, KeyboardInterrupt):
        text = ''
    curses.noecho()
    curses.curs_set(0)
    screen.timeout(250)
    return text.strip()


def run_screen(screen, run, every_seconds, name='Visitor'):
    import curses
    curses.curs_set(0)
    curses.use_default_colors()
    for pair, color in ((1, curses.COLOR_CYAN), (2, -1), (3, curses.COLOR_YELLOW)):
        curses.init_pair(pair, color, -1)
    style = {'head': curses.color_pair(1) | curses.A_BOLD, 'speech': curses.color_pair(2), 'quiet': curses.color_pair(3)}
    screen.timeout(250)
    everyone, only, offset, data, loaded = True, None, 0, None, 0.0
    engine, verbose, stats, cache, graphs, guide = False, False, False, {}, False, False
    while True:
        if data is None or time.monotonic() - loaded >= every_seconds:
            try:
                data = load(run)
            except (OSError, ValueError, KeyError):
                pass  # a checkpoint being replaced mid-read; try again next tick
            read_calls(run / 'requests.jsonl', cache)
            loaded = time.monotonic()
        height, width = screen.getmaxyx()
        screen.erase()
        if data is not None and height >= 8 and width >= 40:
            left = min(26, width // 3)
            body = height - 3
            screen.addnstr(0, 0, header(data, run, width).ljust(width), width - 1, curses.A_REVERSE)
            panel = stats_lines(data, cache, left - 1) if stats else people_lines(data, left - 1)
            for row, (tag, text) in enumerate(panel[:body]):
                screen.addnstr(row + 1, 0, text, left - 1, style[tag])
            for row in range(body):
                screen.addch(row + 1, left, curses.ACS_VLINE)
            call = data.get('call')
            if guide:
                lines = help_lines(data, width - left - 3)
            elif graphs:
                lines = graph_lines(data, cache, width - left - 2)
            elif call and call['active']:
                lines = call_lines(call, width - left - 3)
            elif engine:
                calls = list(cache.get('recent', []))
                if data.get('current'):
                    calls.append({**summarize(data['current']), 'seconds': None})
                lines = engine_lines(calls, width - left - 2, verbose, only)
            else:
                lines = feed_lines(data, width - left - 2, everyone, only)
            top = max(0, len(lines) - body - offset)
            offset = max(0, min(offset, max(0, len(lines) - body)))
            for row, (tag, text) in enumerate(lines[top:top + body]):
                screen.addnstr(row + 1, left + 2, text, width - left - 3, style[tag])
            screen.addnstr(height - 2, 0, status_line(data, width).ljust(width, '─'), width - 1, style['head'])
            screen.addnstr(height - 1, 0, footer(data, everyone, only, width, engine, verbose, graphs), width - 1, curses.A_REVERSE)
        else:
            screen.addnstr(0, 0, 'Make the terminal at least 40x8.', max(1, width - 1))
        screen.refresh()
        key = screen.getch()
        if key in (ord('q'), ord('Q')):
            return
        if key == curses.KEY_UP:
            offset += 1
        elif key == curses.KEY_DOWN:
            offset = max(0, offset - 1)
        elif key == curses.KEY_PPAGE:
            offset += max(1, height - 4)
        elif key == curses.KEY_NPAGE:
            offset = max(0, offset - max(1, height - 4))
        elif key == curses.KEY_END:
            offset = 0
        elif key == ord('a'):
            everyone = not everyone
        elif key == ord('l'):
            engine, offset = not engine, 0
        elif key == ord('v'):
            verbose = not verbose
        elif key == ord('s'):
            stats = not stats
        elif key == ord('g'):
            graphs, offset = not graphs, 0
        elif key in (ord('h'), ord('?')):
            guide = not guide
            offset = 10 ** 6 if guide else 0  # the feed follows its newest end; the guide opens at its top
        elif key == ord('c'):
            whom = ask(screen, f' {name} calls (id, @handle or name; Enter to ring, empty to cancel): ').strip()
            if whom:
                from .visit import call
                call(run, whom, name)
                graphs, data, loaded = False, None, 0.0
        elif key == ord('t'):
            from .visit import LINE_HELP, talk_line
            text = ask(screen, f' {name} (@name to start, /bye to end, h for help): ').strip()
            if text:
                guide = False
                try:
                    talk_line(run, text, name)
                except ValueError:
                    ask(screen, ' ' + LINE_HELP[:200] + ' (Enter)')
                graphs, data, loaded = False, None, 0.0
        elif data and ord('1') <= key <= ord('9') and key - ord('1') < len(data['people']):
            only, offset = data['people'][key - ord('1')]['id'], 0
        elif key == ord('0'):
            only, offset = None, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='Run directory containing world.json and requests.jsonl')
    parser.add_argument('--every', type=float, default=2.0, help='Seconds between refreshes')
    parser.add_argument('--name', default='Visitor', help='Your name when you talk (key t)')
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error('Give a run directory, such as runs/live/environment-live/run')
    import curses
    curses.wrapper(run_screen, args.run, args.every, args.name)


if __name__ == '__main__':
    main()
