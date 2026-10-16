"""Researcher cockpit: one agent's perspective or a labeled researcher view of a run, as a local web page.

Static:  python3 -m devsim.cockpit RUN_DIR_OR_CHECKPOINT --out cockpit.html
Live:    python3 -m devsim.cockpit RUN_DIR --serve 18090   (loopback only; re-reads files on each poll)

An agent perspective is built only from that person's own received memories, mood, goals, plans,
relationships and actions. The researcher view shows every raw record and is labeled as such.
Reading a checkpoint here never changes it.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from .engine import Engine
from .interview import state_digest

AGENT_SCOPE = ('Agent perspective: only what this person has received and currently holds. Memory text is what is '
               'accessible now (full detail or the encoded gist), not the hidden original.')
RESEARCHER_SCOPE = ('Researcher view: every raw controller event, action and model call. No simulated person has this '
                    'view; spoken claims in it are unverified utterances, not world facts.')


def _paths(target):
    target = Path(target)
    if target.is_dir():
        return target / 'world.json', target / 'requests.jsonl'
    return target, target.with_name('requests.jsonl')


def _requests(path):
    rows = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:  # a live run may be mid-write on its last line
                continue
            response = row.get('response') or {}
            rows.append({'purpose': row.get('purpose'), 'agent': row.get('agent'), 'day': row.get('simulated_day'),
                         'seconds': row.get('seconds'), 'action_id': response.get('action_id'),
                         'speech': response.get('speech') or '', 'repair': 'output_repair' in (row.get('context') or {})})
    return rows


def perspective(engine, owner):
    agent = engine.agent(owner)
    observations = {o.event_id: o for o in engine.world.observations.get(owner, [])}
    if 'cognition' in engine.state['config']:
        from .cognition import views
        accessible = {m['event']: m for m in views(engine, owner, '', len(agent['memory_meta']))}
        access_note = 'Accessibility from the run\'s cognition policy at the current day.'
    else:
        accessible = {}
        access_note = 'This checkpoint has no cognition policy, so memories show received text without an accessibility model.'
    memories = []
    for event_id, obs in sorted(observations.items(), key=lambda item: item[1].day):
        meta = agent['memory_meta'].get(event_id, {})
        view = accessible.get(event_id)
        if accessible and not view:
            continue  # not accessible to this person now
        memories.append({'event': event_id, 'day': obs.day, 'source': obs.source, 'kind': meta.get('kind'),
                         'text': view['text'] if view else obs.text,
                         'representation': view['representation'] if view else 'received_text',
                         'meaning': meta.get('meaning'), 'confidence': meta.get('confidence'),
                         'earlier_meanings': [v.get('meaning') for v in meta.get('versions', [])],
                         'provenance': meta.get('provenance')})
    actions = []
    for action in engine.state['actions']:
        if action['owner'] != owner:
            continue
        outcome = observations.get(action.get('outcome_event'))
        actions.append({'id': action['id'], 'day': action['day'], 'status': action['status'],
                        'action': action['decision'].get('action'), 'speech': action['decision'].get('speech', ''),
                        'goal_id': action['decision'].get('goal_id'), 'outcome': outcome.text if outcome else None})
    return {'owner': owner, 'name': engine.state['entities'].get(owner, {}).get('name', owner), 'scope': AGENT_SCOPE,
            'access_note': access_note, 'alive': agent['alive'],
            'age_years': round((engine.day - agent['birth_day']) / 365.25, 2), 'mood': engine.mood(owner),
            'goals': agent.get('goals', {}), 'relationships': agent.get('relationships', {}),
            'calendar': agent.get('calendar', []), 'memories': memories, 'actions': actions}


def snapshot(target):
    world_path, requests_path = _paths(target)
    data = {'source': str(world_path), 'requests': _requests(requests_path), 'world_available': world_path.exists()}
    if not world_path.exists():
        data['note'] = 'No checkpoint yet (a live run writes world.json when it ends); the model-call timeline is live.'
        return data
    engine = Engine.load(world_path)
    before = state_digest(engine)
    data.update(day=engine.day, people={o: perspective(engine, o) for o in sorted(engine.state['agents'])},
                researcher={'scope': RESEARCHER_SCOPE, 'events': engine.state['events'], 'actions': engine.state['actions'],
                            'pending': engine.state['pending'], 'entities': engine.state['entities']})
    if state_digest(engine) != before:
        raise RuntimeError('Cockpit reading changed the checkpoint')
    return data


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Researcher Cockpit</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{--bg:#f7f7f5;--panel:#fff;--text:#1d1d1b;--muted:#5f5f5a;--line:#dddcd6;--accent:#2d5b8a;--warn:#8a4b12;--chip:#eef2f6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--panel:#1f1f1d;--text:#ecebe6;--muted:#a3a29b;--line:#373733;--accent:#8fb6de;--warn:#e0a466;--chip:#26303a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#161615;--panel:#1f1f1d;--text:#ecebe6;--muted:#a3a29b;--line:#373733;--accent:#8fb6de;--warn:#e0a466;--chip:#26303a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}
header,main{padding-block:16px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header{border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:12px;align-items:center}
h1{font-size:18px;margin:0 12px 0 0}main{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))}
select:focus-visible,input:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
section{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 16px;min-width:0}
h2{font-size:15px;margin:4px 0 8px}.scope{grid-column:1/-1;border-left:4px solid var(--accent)}
.muted{color:var(--muted)}.warn{color:var(--warn)}.chip{background:var(--chip);border-radius:4px;padding:0 6px;font-size:12px}
ul{list-style:none;padding:0;margin:0}li{border-top:1px solid var(--line);padding:8px 0}li:first-child{border-top:0}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;margin:4px 0 0}details summary{cursor:pointer}
select,input{font:inherit;padding:4px 8px;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-top:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
.wide{grid-column:1/-1;overflow-x:auto}
</style></head><body>
<header><h1>Researcher cockpit</h1>
<label>Perspective <select id="who"></select></label>
<label>Filter <input id="filter" type="search" placeholder="text or event id"></label>
<span id="status" class="muted" aria-live="polite"></span></header>
<main id="main"></main>
<script>
const LIVE = __LIVE__; let data = __DATA__;
const $ = s => document.querySelector(s), esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const day = d => d == null ? '' : 'day ' + Number(d).toFixed(2), num = x => x == null ? '' : Number(x).toFixed(2);
function match(o){const f=$('#filter').value.toLowerCase();return !f||JSON.stringify(o).toLowerCase().includes(f)}
function options(){const sel=$('#who'),keep=sel.value;sel.innerHTML='<option value="@researcher">Researcher view (all records)</option>'+
 Object.values(data.people||{}).map(p=>`<option value="${esc(p.owner)}">${esc(p.name)} (agent perspective)</option>`).join('');
 if([...sel.options].some(o=>o.value===keep))sel.value=keep}
function timeline(){const rows=data.requests.filter(match);return `<section class="wide"><h2>Model-call timeline (${rows.length})</h2>
 <table><thead><tr><th>Day</th><th>Agent</th><th>Purpose</th><th>Choice / speech</th><th>s</th></tr></thead><tbody>${rows.map(r=>
 `<tr><td>${num(r.day)}</td><td>${esc(r.agent)}</td><td>${esc(r.purpose)}${r.repair?' <span class="chip warn">repair</span>':''}</td>
 <td>${esc(r.action_id)}${r.speech?' — “'+esc(r.speech)+'”':''}</td><td>${num(r.seconds)}</td></tr>`).join('')}</tbody></table></section>`}
function agent(p){const goals=Object.entries(p.goals),rels=Object.entries(p.relationships);
 return `<section class="scope"><strong>${esc(p.name)}</strong> · age ${p.age_years} · ${p.alive?'alive':'dead'} · ${day(data.day)}<br>
 <span class="muted">${esc(p.scope)} ${esc(p.access_note)}</span></section>
 <section><h2>Mood now</h2>valence ${num(p.mood.valence)} · arousal ${num(p.mood.arousal)}</section>
 <section><h2>Goals and plans</h2><ul>${goals.map(([k,g])=>`<li><strong>${esc(k)}</strong> <span class="chip">${esc(g.status)} ${num(g.progress)}</span><br>${esc(g.description)}
 ${(g.plan||[]).length?'<br><span class="muted">Plan:</span> '+g.plan.map(esc).join(' → '):''}</li>`).join('')||'<li class="muted">None</li>'}</ul></section>
 <section><h2>Relationships</h2><ul>${rels.map(([k,r])=>`<li><strong>${esc(k)}</strong> ${esc(r.role||'')} · trust ${num(r.trust)} · closeness ${num(r.closeness)}
 <span class="muted">· evidence ${esc(r.evidence||'')}</span>${(r.versions||[]).length?`<details><summary>${r.versions.length} earlier values</summary><pre>${esc(JSON.stringify(r.versions,null,1))}</pre></details>`:''}</li>`).join('')||'<li class="muted">None</li>'}</ul></section>
 <section><h2>Calendar</h2><ul>${p.calendar.filter(match).map(c=>`<li>${esc(c.activity)} <span class="chip">${esc(c.status)}</span> ${day(c.start_day)}–${num(c.end_day)}</li>`).join('')||'<li class="muted">Empty</li>'}</ul></section>
 <section class="wide"><h2>Own actions and outcomes</h2><ul>${p.actions.filter(match).map(a=>`<li>${day(a.day)} · <strong>${esc(a.action)}</strong> <span class="chip">${esc(a.status)}</span>
 ${a.speech?`<br>Said: “${esc(a.speech)}” <span class="muted">(unverified claim)</span>`:''}${a.outcome?`<br><span class="muted">Outcome received:</span> ${esc(a.outcome)}`:''}</li>`).join('')||'<li class="muted">None</li>'}</ul></section>
 <section class="wide"><h2>Accessible memories (${p.memories.length})</h2><ul>${p.memories.filter(match).map(m=>`<li>${day(m.day)} · <span class="chip">${esc(m.kind)}</span>
 <span class="chip">${esc(m.representation)}</span> <span class="muted">from ${esc(m.source)} · ${esc(m.event)}</span><br>${esc(m.text)}
 ${m.meaning?`<br><span class="muted">Meaning (confidence ${num(m.confidence)}):</span> ${esc(m.meaning)}`:''}
 ${m.earlier_meanings.length?`<details><summary>${m.earlier_meanings.length} earlier meanings</summary><pre>${esc(m.earlier_meanings.join('\n'))}</pre></details>`:''}</li>`).join('')}</ul></section>`}
function researcher(r){const raw=x=>`<details><summary>${esc(x.id)} · ${day(x.day)} ${esc(x.description||x.owner||'')}</summary><pre>${esc(JSON.stringify(x,null,1))}</pre></details>`;
 return `<section class="scope"><strong>Researcher view</strong> · ${day(data.day)} · ${esc(data.source)}<br><span class="muted">${esc(r.scope)}</span></section>
 ${timeline()}
 <section><h2>Controller events (${r.events.length})</h2><ul>${r.events.filter(match).map(e=>`<li>${raw(e)}</li>`).join('')}</ul></section>
 <section><h2>Actions (${r.actions.length})</h2><ul>${r.actions.filter(match).map(a=>`<li>${raw(a)}</li>`).join('')}</ul></section>
 <section><h2>Pending events (${r.pending.length})</h2><ul>${r.pending.filter(match).map(e=>`<li>${raw(e)}</li>`).join('')||'<li class="muted">None</li>'}</ul></section>
 <section><h2>Committed identities</h2><pre>${esc(JSON.stringify(r.entities,null,1))}</pre></section>`}
function draw(){options();const who=$('#who').value;$('#status').textContent=(LIVE?'Live · ':'')+(data.world_available?day(data.day):'')+' · '+data.requests.length+' model calls';
 $('#main').innerHTML=!data.world_available?`<section class="scope warn">${esc(data.note)}</section>${timeline()}`:
  who==='@researcher'?researcher(data.researcher):agent(data.people[who])}
$('#who').onchange=draw;$('#filter').oninput=draw;draw();
if(LIVE)setInterval(async()=>{try{data=await (await fetch('data.json',{cache:'no-store'})).json();draw()}catch(e){$('#status').textContent='Live · reconnecting'}},5000);
</script></body></html>
"""


def render(data, live=False):
    payload = json.dumps(data, allow_nan=False).replace('</', '<\\/')  # keep embedded text from closing the script tag
    return PAGE.replace('__LIVE__', 'true' if live else 'false').replace('__DATA__', payload)


def make_server(target, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/', '/data.json'):
                self.send_error(404)
                return
            data = snapshot(target)
            body = (render(data, live=True) if self.path == '/' else json.dumps(data, allow_nan=False)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if self.path == '/' else 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', type=Path, help='Run directory (world.json, requests.jsonl) or a checkpoint .json/.sqlite')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path, help='Write a self-contained HTML file')
    mode.add_argument('--serve', type=int, metavar='PORT', help='Serve a live page on 127.0.0.1')
    args = parser.parse_args()
    if args.out:
        if args.out.exists():
            parser.error('Choose a fresh output file')
        args.out.write_text(render(snapshot(args.target)))
        print(args.out)
    else:
        server = make_server(args.target, args.serve)
        print(f'Cockpit at http://127.0.0.1:{server.server_address[1]}/ (loopback only; Ctrl-C stops)', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
