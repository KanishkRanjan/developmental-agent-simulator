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
from functools import lru_cache
import json
from math import cos, floor, pi, sin
from pathlib import Path
import textwrap
import time

from . import household
from .engine import Engine
from .tui import ask, choose

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
    data['skip_until'] = engine.state.get('runtime', {}).get('skip_until')
    data['seed'] = engine.state.get('seed')
    thoughts, said = {}, {}
    for event in reversed(engine.state['events']):
        if event['id'].startswith('@thought:'):
            who = event['id'].split(':')[1]
            if who not in thoughts and who in event['observations']:
                thoughts[who] = event['observations'][who]['text']
    for action in reversed(engine.state['actions']):
        if action['decision'].get('speech') and action['owner'] not in said:
            said[action['owner']] = action['decision']['speech']
    household_cfg = engine.state['config'].get('household', {})
    data['rooms'] = {k: {'label': r['label'], 'audible_to': r.get('audible_to', []), 'site': r.get('site'), 'kind': r.get('kind')}
                     for k, r in household_cfg.get('rooms', {}).items()}
    data['locations'] = dict(locations)
    data['creatures'] = {c['name'] + ' the ' + c['kind']: engine.state.get('living', {}).get('creatures', {}).get(c['id'], {}).get('room')
                         for c in household_cfg.get('creatures', [])}
    data['my_characters'] = [{'id': k, 'name': e['name'], 'about': e['facts'].get('description', '')}
                             for k, e in sorted(engine.state['entities'].items()) if 'sent_by' in e['facts'] and k in engine.state['agents']]
    for owner in sorted(engine.state['agents']):
        agent = engine.agent(owner)
        if not agent['alive']:
            place = 'died'
        elif owner in locations and locations[owner] is None:
            place = 'in transit'
        else:
            place = rooms.get(locations.get(owner), {}).get('label', locations.get(owner) or '')
        person = {'id': owner, 'name': names.get(owner, owner), 'place': place, 'mood': engine.mood(owner)}
        if agent['alive']:
            person['card'] = card(engine, owner, thoughts, said)
            person['awake'] = household.available(engine, owner) if household_cfg else True
        if 'living' in engine.state['config'] and agent['alive']:
            from . import living
            doing = engine.state.get('living', {}).get('doing', {}).get(owner)
            person['doing'] = doing['verb'] if doing and doing['phase'] == 'busy' else ''
            person['feel'] = ', '.join(living.words(engine, owner))
        data['people'].append(person)
    for action in sorted(engine.state['actions'], key=lambda a: (a['day'], a['id'])):
        decision = action['decision']
        data['feed'].append({'day': action['day'], 'owner': action['owner'], 'name': names.get(action['owner'], action['owner']),
                             'where': where(engine, action['id']), 'choice': decision.get('action_id'),
                             'label': decision.get('action') or '', 'speech': decision.get('speech') or ''})
    visits = engine.state.get('runtime', {}).get('visitor_log', [])
    data['feed'] += [{'day': v['day'], 'owner': v['visitor'], 'name': names.get(v['visitor'], 'Visitor') + ' (you)',
                      'where': where(engine, v['event']), 'choice': 'speak', 'label': '', 'speech': v['text']} for v in visits]
    # The living world: thoughts, activities, and what happened around people (one line per event).
    for event in engine.state['events']:
        kind, _, rest = event['id'].partition(':')
        if kind not in ('@thought', '@living', '@happening', '@creature', '@weather') or not event['observations']:
            continue
        owner = rest.split(':')[0] if kind in ('@thought', '@living') else None
        text = (event['observations'].get(owner) or next(iter(event['observations'].values())))['text']
        room = rooms.get(rest.split('/')[0], {}).get('label', '') if kind == '@happening' else ''  # only happenings record their room
        data['feed'].append({'day': event['day'], 'owner': owner or 'world', 'name': names.get(owner, 'Around them'),
                             'where': room, 'choice': 'thinks' if kind == '@thought' else 'notices',
                             'label': ('(thinks) ' if kind == '@thought' else '') + text, 'speech': ''})
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
    elif not call.get('in_person'):
        lines.append(('quiet', 'press Tab and choose End the talk to hang up'))
    return lines


def help_lines(data, width):
    """The talk guide (key h): how to reach people from this terminal, with examples using this run's people."""
    people = data.get('people') or []
    who = people[0]['id'] if people else 'priya'
    rows = [('head', 'Watching · press h to close'),
            ('quiet', 'p opens the character panel (face, feelings, hormones, needs, goals, people); 1-9 or Tab picks the person.'),
            ('quiet', 'm shows the room map, m again the relationship web of the picked person, m again the feed.'),
            ('quiet', ''), ('head', 'Talking: press t and choose'),
            ('quiet', 't opens a menu: talk face to face, phone, introduce a new character (name, who they are, age, '
                      'whom they meet and how they know them), send one of your characters again, or speak to the group. '
                      'During a talk, t types your next line and Tab offers "let the model play" and "end the talk".'),
            ('quiet', 'The run picks it up at its next event, and the world waits while you talk.'),
            ('quiet', ''), ('head', 'Typed commands (still work, for power users)'),
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


def card(engine, owner, thoughts, said):
    """What the character panel shows about one person, read from the run (never changed)."""
    from .personality import describe
    from .sleep import dials as sleep_dials
    from .sleep import HIDDEN
    agent = engine.agent(owner)
    meta = agent['memory_meta']
    mood = engine.mood(owner)
    label = lambda k: engine.label(k) if k in engine.state['entities'] else k
    out = {'age': (engine.day - agent['birth_day']) / 365.25, 'arousal': mood['arousal'], 'valence': mood['valence'],
           'about': describe(agent['facets'])['tendencies'][:3],
           'goals': [{'text': g['description'], 'progress': g.get('progress', 0.0), 'status': g['status']} for g in agent['goals'].values()],
           'ties': sorted(({'id': k, 'name': label(k), 'role': r.get('role') or '', 'trust': r.get('trust', .5), 'closeness': r.get('closeness', 0.0)}
                           for k, r in agent['relationships'].items()), key=lambda t: (-t['closeness'], -t['trust'], t['name'])),
           'memories': [sum(m.get('tier') not in HIDDEN for m in meta.values()), len(meta)],
           'beliefs': len(agent.get('beliefs', {})), 'thought': thoughts.get(owner), 'said': said.get(owner),
           'facets': dict(agent['facets']), 'dials': sleep_dials(agent),
           'handle': engine.state['entities'][owner]['facts'].get('handle'),
           'goal_ids': list(agent['goals']), 'role': 'yours' if 'sent_by' in engine.state['entities'][owner]['facts'] else 'simulated'}
    stress, sleepy, drive = mood['arousal'], 0.0, 0.0
    if 'hormones' in engine.state['config']:
        from . import hormones
        snap = hormones.read(engine, owner)
        out['hormones'] = {'stress': snap.stress, 'sleep pressure': snap.sleep_pressure, 'dopamine': snap.dopamine}
        stress, sleepy, drive = snap.stress, snap.sleep_pressure, snap.dopamine
    if 'living' in engine.state['config']:
        from . import living
        out['needs'] = living.needs(engine, owner)
    if 'skills' in engine.state['config']:
        from . import skills
        rows = sorted(engine.agent(owner).get('skills', {}).values(), key=lambda s: -skills.level(engine, owner, s['key']))[:6]
        out['skills'] = [{'key': s['key'], 'label': s.get('label') or s['key'], 'level': skills.level(engine, owner, s['key']),
                          'now': skills.performance(engine, owner, s['key']),
                          'tier': skills.tier_of(skills.cfg(engine), skills.performance(engine, owner, s['key']))} for s in rows]
        doing = engine.state.get('living', {}).get('doing', {}).get(owner)
        out['doing'] = doing['verb'] if doing and doing['phase'] == 'busy' else ''
        if 'hormones' not in engine.state['config']:
            sleepy = 1 - out['needs']['energy']
    out['face'] = {'mood': round(mood['valence'], 2), 'stress': round(stress, 2), 'sleepy': round(sleepy, 2), 'drive': round(drive, 2)}
    return out


def bar(value, low, high, cells):
    """A block bar: filled share of [low, high]."""
    full = max(0, min(cells, round((value - low) / (high - low) * cells)))
    return '█' * full + '░' * (cells - full)


@lru_cache(maxsize=256)
def face_lines(seed, owner, age, mood, stress, sleepy, drive, cols):
    from .ascii_art import portrait
    return tuple(portrait(seed, owner, age, mood, stress, sleepy, drive, cols, max(6, cols // 2)))


def person_card(data, person, width):
    """The character panel: ASCII face, description, feelings, hormones, needs, goals, people, thoughts."""
    c = person.get('card')
    if c is None:
        return [('head', f'{person["name"]} (died)'[:width])]
    lines = []
    cols = max(8, min(22, width - 2))
    pad = ' ' * max(0, (width - cols) // 2)
    lines += [('speech', (pad + row)[:width]) for row in face_lines(data.get('seed'), person['id'], round(c['age']), cols=cols, **c['face'])]
    lines.append(('head', f'{person["name"]}, {c["age"]:.0f}'[:width]))
    lines.append(('quiet', (person['place'] + (f', {c["doing"]}' if c.get('doing') else ''))[:width]))
    for text in c['about']:
        lines += [('quiet', part) for part in textwrap.wrap(text, width, initial_indent='· ', subsequent_indent='  ')]
    n = max(4, min(14, width - 22))
    row = lambda name, value, low, high, shown: ('speech', f' {name:<15}{bar(value, low, high, n)} {shown}'[:width])
    lines.append(('head', 'feeling'))
    lines.append(row('mood', c['valence'], -1, 1, f'{c["valence"]:+.2f}'))
    lines.append(row('arousal', c['arousal'], 0, 1, f'{c["arousal"]:.2f}'))
    if 'hormones' in c:
        lines.append(('head', 'hormones'))
        for name, value in c['hormones'].items():
            lines.append(row(name, value, -1 if name == 'dopamine' else 0, 1, f'{value:+.2f}' if name == 'dopamine' else f'{value:.2f}'))
    if 'needs' in c:
        lines.append(('head', 'needs (full = met)'))
        for name, value in c['needs'].items():
            lines.append(row(name, value, 0, 1, f'{value:.2f}'))
    if c.get('skills'):
        lines.append(('head', 'skills (stored, today)'))
        for skill in c['skills']:
            lines.append(row(skill['label'][:14], skill['level'], 0, 1, f'{skill["level"]:.2f} {skill["tier"]}'))
    if c['goals']:
        lines.append(('head', 'goals'))
        for goal in c['goals']:
            lines += [('quiet', part) for part in textwrap.wrap(goal['text'], width, initial_indent=' ', subsequent_indent='  ')]
            lines.append(row(goal['status'], goal['progress'], 0, 1, f'{goal["progress"]:.0%}'))
    if c['ties']:
        lines.append(('head', 'people (closeness · trust)'))
        k = max(3, min(6, (width - 18) // 2))
        for tie in c['ties'][:5]:
            lines.append(('speech', f' {tie["name"].split(" (@")[0][:13]:<14}{bar(tie["closeness"], 0, 1, k)} {bar(tie["trust"], 0, 1, k)}'[:width]))
    for title, text in (('thinking', c.get('thought')), ('last said', c.get('said'))):
        if text:
            lines.append(('head', title))
            lines += [('quiet', part) for part in textwrap.wrap(text, width, initial_indent=' ', subsequent_indent=' ')[:4]]
    lines.append(('quiet', f' {c["memories"][0]}/{c["memories"][1]} memories recallable · {c["beliefs"]} beliefs'[:width]))
    return lines


def numbers(data):
    return {p['id']: n for n, p in enumerate(data['people'], 1)}


def map_lines(data, selected, width):
    """Rooms as boxes grouped by site, joined where one room hears the other; people by panel number."""
    rooms, number = data.get('rooms') or {}, numbers(data)
    if not rooms:
        return [('quiet', 'No rooms in this run.')]
    inside = {k: [] for k in rooms}
    for p in data['people']:
        where = data['locations'].get(p['id'])
        if where in inside:
            inside[where].append(('*' if p['id'] == selected else ' ') + f'{number[p["id"]]} {p["name"]}')
    for name, where in data.get('creatures', {}).items():
        if where in inside:
            inside[where].append(f' ~ {name}')
    linked = lambda a, b: b in rooms[a]['audible_to'] or a in rooms[b]['audible_to']
    sites = {}
    for k, r in rooms.items():
        sites.setdefault(r.get('site') or 'places', []).append(k)
    lines = [('head', 'Room map · numbers open the panel · * selected · ── can hear each other'[:width])]
    for site, keys in sites.items():
        order, seen = [], set()
        for start in keys:  # walk the hearing links so neighbours sit side by side
            stack = [start]
            while stack:
                k = stack.pop()
                if k in seen:
                    continue
                seen.add(k)
                order.append(k)
                stack += [o for o in reversed(keys) if o not in seen and linked(k, o)]
        lines.append(('head', f'{site}'[:width]))
        boxes = []
        for k in order:
            body = inside[k] or ['']
            inner = min(max(10, len(rooms[k]['label']) + 2, *(len(b) for b in body)), max(10, width // 2 - 4))
            top = '┌ ' + rooms[k]['label'][:inner - 1] + ' ' + '─' * max(0, inner - len(rooms[k]['label'][:inner - 1]) - 2) + '┐'
            boxes.append((k, [top, *('│' + b[:inner].ljust(inner) + '│' for b in body), '└' + '─' * inner + '┘']))
        row, used, drawn = [], 0, set()
        def flush(row):
            height = max(len(b) for _, b in row)
            for i in range(height):
                text = ''
                for j, (k, box) in enumerate(row):
                    blank = ' ' * len(box[0])
                    piece = box[i] if i < len(box) else blank
                    if j:
                        text += '──' if i == 1 and linked(row[j - 1][0], k) else '  '
                    text += piece
                lines.append(('speech', text[:width]))
            for (a, _), (b, _) in zip(row, row[1:]):
                if linked(a, b):
                    drawn.add(frozenset((a, b)))
        for k, box in boxes:
            if row and used + 2 + len(box[0]) > width:
                flush(row)
                row, used = [], 0
            row.append((k, box))
            used += len(box[0]) + 2
        if row:
            flush(row)
        rest = sorted({frozenset((a, b)) for a in keys for b in keys if a < b and linked(a, b)} - drawn, key=sorted)
        if rest:
            text = 'also hear each other: ' + ', '.join(' ↔ '.join(rooms[r]['label'] for r in sorted(pair)) for pair in rest)
            lines += [('quiet', part) for part in textwrap.wrap(text, width)]
    away = [f'{number[p["id"]]} {p["name"]}' for p in data['people'] if p['place'] == 'in transit']
    if away:
        lines.append(('quiet', ('in transit: ' + ', '.join(away))[:width]))
    return lines


def web_lines(data, selected, width, height):
    """The selected person in the middle, the people they have records of around them; # close, = warm, - known, . distant."""
    person = next((p for p in data['people'] if p['id'] == selected), None)
    if person is None or 'card' not in person:
        return [('quiet', 'Pick a person with 1-9 or Tab.')]
    ties = person['card']['ties'][:10]
    w, h = max(30, width), max(11, min(height - 2, 25))
    canvas = [[' '] * w for _ in range(h)]
    cx, cy = w // 2, h // 2
    rx, ry = max(8, w // 2 - 12), max(3, h // 2 - 1)
    nodes = []
    for i, tie in enumerate(ties):
        angle = 2 * pi * i / max(1, len(ties)) - pi / 2
        nodes.append((cx + round(rx * cos(angle)), cy + round(ry * sin(angle)), tie))
    for x, y, tie in nodes:
        mark = '#' if tie['closeness'] >= .6 else '=' if tie['closeness'] >= .3 else '-' if tie['closeness'] > 0 else '.'
        x0, y0, dx, dy = cx, cy, abs(x - cx), -abs(y - cy)
        sx, sy, err = (1 if x > cx else -1), (1 if y > cy else -1), abs(x - cx) - abs(y - cy)
        while (x0, y0) != (x, y):  # Bresenham
            if 0 <= y0 < h and 0 <= x0 < w and canvas[y0][x0] == ' ':
                canvas[y0][x0] = mark
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
    def put(x, y, text):
        start = max(0, min(w - len(text), x - len(text) // 2))
        for i, ch in enumerate(text[:w]):
            if 0 <= y < h:
                canvas[y][start + i] = ch
    for x, y, tie in nodes:
        put(x, y, f' {tie["name"][:10]} c{tie["closeness"]:.1f} t{tie["trust"]:.1f} ')
    put(cx, cy, f'[ {person["name"]} ]')
    head = ('head', f'Relationship web of {person["name"]} · from their own records only · c closeness, t trust'[:width])
    return [head, *(('speech', ''.join(r).rstrip()) for r in canvas)] if ties else [head, ('quiet', 'No relationship records yet.')]


def people_lines(data, width):
    lines = []
    for n, person in enumerate(data['people'], 1):
        mood = person['mood']['valence']
        lines.append(('head', f'{n} {person["name"]}'[:width]))
        lines.append(('quiet', f'  {person["place"]}' + (f', {person["doing"]}' if person.get('doing') else '')[:width]))
        if person.get('feel'):
            lines.append(('quiet', f'  feels {person["feel"]}'[:width]))
        lines.append(('speech', f'  mood {mood:+.2f} {"▲" if mood > .05 else "▼" if mood < -.05 else "■"}'[:width]))
    return lines


def header(data, run, width):
    when = clock(data['day']) if 'day' in data else 'no checkpoint yet'
    name = run.parent.name if run.name == 'run' else run.name
    skipping = f' · fast-forwarding to {clock(data["skip_until"])}' if data.get('skip_until') is not None else ''
    return f' {name} · {when}{skipping} · {data["status"]} · {data["calls"]} model calls '[:width]


def footer(data, everyone, only, width, engine=False, verbose=False, graphs=False):
    last = data['last']
    now = f'last call: {last["agent"] or "-"} · {last["purpose"]} · {clock(last["day"])}' if last and last['day'] is not None else 'waiting'
    view = ('graphs' if graphs else 'engine' + (' · full text' if verbose else '') if engine else 'all decisions' if everyone
            else 'speech only') + (f' · {only}' if only else '')
    if data.get('call') and data['call']['active']:
        view = ('talking' if data['call'].get('in_person') else 'phone call') + ' · t to speak, Tab for options'
    return f' {now}  |  {view}  |  t talk  p panel  m map/web  Tab next  h help  c call  f skip time  g graphs  l engine  v full  s stats  a speech  1-9 person  0 all  ↑↓  q quit '[:width]


ACTIONS = ['Talk to someone face to face', 'Phone someone', 'Introduce a new character', 'Send one of your characters again',
           'Say something to the current group conversation']
AGES = [('a child, about 10', 10), ('a teenager, about 15', 15), ('a young adult, about 22', 22), ('an adult, about 35', 35),
        ('middle-aged, about 50', 50), ('older, about 70', 70), ('type an age', None)]


def perform(run, name, action, **values):
    """What a finished menu does: the same inbox notes the typed commands write (devsim.visit)."""
    from . import visit
    if action == 'talk':
        visit.talk(run, values['to'], values['text'], name)
    elif action == 'call':
        visit.call(run, values['to'], name)
    elif action == 'send':
        visit.send(run, values['character'], values['to'], name, values.get('who'), values.get('age'),
                   relationship=values.get('relationship'))
    elif action == 'say':
        visit.say(run, values['text'], None, name)
    elif action == 'auto':
        visit.auto(run, values['goal'])
    elif action == 'end':
        visit.hang_up(run)
    else:
        raise ValueError(f'Unknown action {action}')


def pick_person(screen, data, title):
    people = [p for p in data['people'] if 'card' in p]
    if not people:
        return None
    labels = [f'{p["name"]} · {p["place"] or "somewhere"}' + ('' if p.get('awake', True) else ' (asleep or busy)') for p in people]
    i = choose(screen, title, labels)
    return None if i is None else people[i]


def interact(screen, run, data, name):
    """The talk menu (key t): every step is a choice or a short answer; no commands to remember. Returns a status line."""
    action = choose(screen, 'What would you like to do?', ACTIONS)
    if action is None:
        return ''
    if action == 0:
        person = pick_person(screen, data, 'Who do you walk up to?')
        text = person and ask(screen, f' What do you say to {person["name"]}? ')
        if text:
            perform(run, name, 'talk', to=person['id'], text=text)
            return f'walking over to {person["name"]}: type your lines with t, Tab for options'
    elif action == 1:
        person = pick_person(screen, data, 'Who do you call?')
        if person:
            perform(run, name, 'call', to=person['id'])
            return f'calling {person["name"]}'
    elif action == 2:
        character = ask(screen, ' Your character\'s name: ')
        who = character and ask(screen, f' Who is {character}? (e.g. Priya\'s cousin from Delhi, studying engineering): ')
        if not who:
            return ''
        a = choose(screen, f'How old is {character}?', [label for label, _ in AGES])
        if a is None:
            return ''
        age = AGES[a][1]
        if age is None:
            try:
                age = float(ask(screen, ' Age (1-100): '))
            except ValueError:
                return 'age must be a number'
        person = pick_person(screen, data, f'Who does {character} go to meet?')
        if person is None:
            return ''
        from .visit import RELATIONSHIPS
        kinds = [*RELATIONSHIPS, 'something else (type it)']
        k = choose(screen, f'{character} is {person["name"]}\'s ...', kinds)
        if k is None:
            return ''
        relationship = kinds[k] if k < len(RELATIONSHIPS) else ask(screen, f' {character} is {person["name"]}\'s (a few words): ')
        summary = f'{character}, {age:g}: {who}. {person["name"]}\'s {relationship}; meets them in person.'
        if choose(screen, 'Send this character?', ['Send', 'Cancel'], summary[:120]) != 0:
            return 'cancelled'
        perform(run, name, 'send', character=character, to=person['id'], who=who, age=age, relationship=relationship)
        return f'sending {character} to {person["name"]}: type their lines with t, Tab for options'
    elif action == 3:
        mine = data.get('my_characters') or []
        if not mine:
            return 'you have no characters yet: introduce one first'
        c = choose(screen, 'Which of your characters?', [f'{m["name"]} · {m["about"]}' for m in mine])
        person = None if c is None else pick_person(screen, data, f'Who does {mine[c]["name"]} go to?')
        if person:
            perform(run, name, 'send', character=mine[c]['name'], to=person['id'])
            return f'sending {mine[c]["name"]} to {person["name"]}'
    elif action == 4:
        text = ask(screen, ' Say to the group: ')
        if text:
            perform(run, name, 'say', text=text)
            return 'said into the most recent group conversation'
    return ''


def talk_options(screen, run, name):
    """Tab during a talk: let the model play your character, or end the talk."""
    i = choose(screen, 'This talk', ['Let the model play your character (give it a goal)', 'End the talk', 'Back'])
    if i == 0:
        goal = ask(screen, ' Goal for your character (e.g. make friends with Priya): ')
        if goal:
            perform(run, name, 'auto', goal=goal)
            return 'the model now plays your character; press t and type to take over'
    elif i == 1:
        perform(run, name, 'end')
        return 'ending the talk'
    return ''


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
    panel, panel_w, chosen, surroundings, notice = False, 0, None, None, ''
    while True:
        if data is None or time.monotonic() - loaded >= every_seconds:
            try:
                data = load(run)
            except (OSError, ValueError, KeyError):
                pass  # a checkpoint being replaced mid-read; try again next tick
            read_calls(run / 'requests.jsonl', cache)
            loaded = time.monotonic()
        ended = data and data.get('call') and not data['call']['active'] and data['call']['events']
        if ended and notice.startswith('calling '):  # the call is over: say how, instead of 'calling' forever
            last = data['call']['events'][-1]
            notice = f'call with {data["call"]["label"]}: {last["event"]}' + (f' ({last["reason"]})' if last.get('reason') else '')
        height, width = screen.getmaxyx()
        screen.erase()
        target = min(48, max(30, width * 2 // 5)) if panel and width >= 70 else 0
        if panel_w != target:  # the panel slides in or out over a few frames
            step = max(4, (target or panel_w) // 4)
            panel_w = min(target, panel_w + step) if panel_w < target else max(target, panel_w - step)
        screen.timeout(40 if panel_w != target else 250)
        people = data['people'] if data else []
        if people and chosen not in [p['id'] for p in people]:
            chosen = only or people[0]['id']
        if data is not None and height >= 8 and width >= 40:
            left = min(26, width // 3)
            body = height - 3
            right = width - left - 2 - (panel_w + 1 if panel_w else 0)
            screen.addnstr(0, 0, header(data, run, width).ljust(width), width - 1, curses.A_REVERSE)
            panel = stats_lines(data, cache, left - 1) if stats else people_lines(data, left - 1)
            for row, (tag, text) in enumerate(panel[:body]):
                screen.addnstr(row + 1, 0, text, left - 1, style[tag])
            for row in range(body):
                screen.addch(row + 1, left, curses.ACS_VLINE)
            call = data.get('call')
            if guide:
                lines = help_lines(data, right - 1)
            elif surroundings == 'map':
                lines = map_lines(data, chosen, right - 1)
            elif surroundings == 'web':
                lines = web_lines(data, chosen, right - 1, body)
            elif graphs:
                lines = graph_lines(data, cache, width - left - 2)
            elif call and call['active']:
                lines = call_lines(call, right - 1)
            elif engine:
                calls = list(cache.get('recent', []))
                if data.get('current'):
                    calls.append({**summarize(data['current']), 'seconds': None})
                lines = engine_lines(calls, right, verbose, only)
            else:
                lines = feed_lines(data, right, everyone, only)
            top = max(0, len(lines) - body - offset)
            offset = max(0, min(offset, max(0, len(lines) - body)))
            for row, (tag, text) in enumerate(lines[top:top + body]):
                screen.addnstr(row + 1, left + 2, text, max(1, right - 1), style[tag])
            if panel_w:
                x0 = width - panel_w
                person = next((p for p in people if p['id'] == chosen), None)
                card_lines = person_card(data, person, max(20, target or panel_w) - 2) if person else []
                for row in range(body):
                    screen.addch(row + 1, x0 - 1, curses.ACS_VLINE)
                    screen.addnstr(row + 1, x0, ' ' * (panel_w - 1), panel_w - 1)
                for row, (tag, text) in enumerate(card_lines[:body]):
                    screen.addnstr(row + 1, x0 + 1, text, max(1, panel_w - 2), style[tag])
            if notice:
                screen.addnstr(height - 2, 0, f' {notice} '.ljust(width), width - 1, curses.A_REVERSE)
            if not notice:
                screen.addnstr(height - 2, 0, status_line(data, width).ljust(width, '─'), width - 1, style['head'])
            screen.addnstr(height - 1, 0, footer(data, everyone, only, width, engine, verbose, graphs), width - 1, curses.A_REVERSE)
        else:
            screen.addnstr(0, 0, 'Make the terminal at least 40x8.', max(1, width - 1))
        screen.refresh()
        key = screen.getch()
        if key != -1:
            notice = ''
        if key in (ord('q'), ord('Q'), 27):  # Esc too: back to the control panel when embedded
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
            person = pick_person(screen, data or {'people': []}, 'Who do you call?')
            if person:
                perform(run, name, 'call', to=person['id'])
                notice = f'calling {person["name"]}'
                graphs, data, loaded = False, None, 0.0
        elif key == ord('f'):
            hours = ask(screen, ' Skip how many hours? (everything in them still happens, just without waiting): ').strip()
            if hours:
                from .visit import skip
                try:
                    skip(run, hours, name)
                    notice = f'skipping {hours} hours at the next event'
                except ValueError as exc:
                    notice = str(exc)[:200]
                data, loaded = None, 0.0
        elif key == ord('t'):
            call_now = data.get('call') if data else None
            try:
                if call_now and call_now['active']:  # in a talk: just type the next line
                    from .visit import call_say, typing
                    typing(run)  # they wait for your line instead of taking you as silent
                    text = ask(screen, f' {name} says (Enter to send, empty to cancel; Tab for options): ').strip()
                    if text.startswith('/'):
                        from .visit import talk_line
                        notice = talk_line(run, text, name)  # power users: the typed commands still work
                    elif text:
                        call_say(run, text)
                else:
                    notice = interact(screen, run, data or {'people': []}, name)
            except ValueError as exc:
                notice = str(exc)[:200]
            guide, graphs, surroundings, data, loaded = False, False, None, None, 0.0
        elif key == 9:  # Tab: talk options during a talk, otherwise the next person
            if data and data.get('call') and data['call']['active']:
                try:
                    notice = talk_options(screen, run, name)
                except ValueError as exc:
                    notice = str(exc)[:200]
                data, loaded = None, 0.0
            elif people:
                ids = [p['id'] for p in people]
                chosen = ids[(ids.index(chosen) + 1) % len(ids)] if chosen in ids else ids[0]
        elif key == ord('p'):
            panel = not panel
        elif key == ord('m'):
            surroundings = {None: 'map', 'map': 'web', 'web': None}[surroundings]
            offset = 0
        elif data and ord('1') <= key <= ord('9') and key - ord('1') < len(data['people']):
            only, offset = data['people'][key - ord('1')]['id'], 0
            chosen = only
        elif key == ord('0'):
            only, offset = None, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='Run directory containing world.json and requests.jsonl')
    parser.add_argument('--every', type=float, default=2.0, help='Seconds between refreshes')
    args = parser.parse_args()
    from .visit import your_name
    if not args.run.is_dir():
        parser.error('Give a run directory, such as runs/live/environment-live/run')
    import curses
    curses.wrapper(run_screen, args.run, args.every, your_name())


if __name__ == '__main__':
    main()
