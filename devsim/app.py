"""The control panel: one terminal app to design, start, watch, stop, resume and steer simulations.

    python3 -m devsim.app [--api http://127.0.0.1:8081]

Tabs (Tab or 1-4): Runs (every simulation; Enter for watch, characters, stop, resume; n starts a new run),
Watch (the full watcher: p panel, m map/web, t talk; Esc back), Characters (search, open, notify, change values),
New (the step-by-step builder; the model fills each character, with Pip the robot keeping you company).
Reading never changes a run. Live changes go through the run's inbox at its next event boundary and are logged as
researcher interventions; a stopped run's changes are applied to a staged copy when it is resumed.
"""
import argparse
from pathlib import Path
import time

from . import builder, runs, tui
from .tui import ask, choose

TABS = ['Runs', 'Watch', 'Characters', 'New']
SETTINGS = runs.ROOT / 'work' / 'control-panel.json'  # remembers your name between sessions
ICONS = {'running': '●', 'completed': '■', 'stopped': '‖', 'failed': '✗', 'interrupted': '?', 'not started': '·'}
UNTIL = [('1 simulated day', 1), ('3 days', 3), ('a week', 7), ('a month', 30), ('the whole scenario', None), ('type a number of days', 'ask')]
PACE = [('Real time: 1 simulated second per second (the world waits while the model thinks)', 1.0),
        ('Faster: 1 simulated hour per real minute', 60.0), ('As fast as the model allows', 0.0)]
DOMAINS = [('O', 'openness'), ('C', 'conscientiousness'), ('E', 'extraversion'), ('A', 'agreeableness'), ('N', 'neuroticism')]


class App:
    def __init__(self, api, name):
        self.api, self.name = api, name
        self.tab, self.cursor, self.selected = 0, 0, None
        self.last_tab = 0  # sub-screens return to Runs, so Tab cycles from the last tab opened
        self.items, self.loaded, self.notice = [], 0.0, ''
        self.pending = {}  # run path -> edits waiting for a resume
        self.model_ok = None

    # Main loop

    def run(self, screen):
        import curses
        curses.curs_set(0)
        self.style = tui.init_colors()
        self.splash(screen)
        self.who_are_you(screen, first=True)
        screen.timeout(250)
        frame = 0
        while True:
            if time.monotonic() - self.loaded > 3:
                self.refresh()
            self.draw(screen, frame)
            key = screen.getch()
            frame += 1
            if key == -1:
                continue
            self.notice = ''
            if key in (ord('q'), ord('Q')):
                if choose(screen, 'Leave the control panel?', ['Yes, quit (running simulations keep going)', 'No']) == 0:
                    return
            elif key == 9:
                self.switch(screen, (self.last_tab + 1) % len(TABS))
            elif ord('1') <= key <= ord('4'):
                self.switch(screen, key - ord('1'))
            elif self.tab == 0:
                self.runs_key(screen, key)

    def refresh(self):
        self.items = runs.discover()
        self.cursor = max(0, min(self.cursor, len(self.items) - 1))
        if self.selected:
            self.selected = next((r for r in self.items if r['path'] == self.selected['path']), self.selected)
        self.loaded = time.monotonic()

    def switch(self, screen, tab):
        self.tab = self.last_tab = tab
        if tab == 1:
            self.watch(screen)
        elif tab == 2:
            self.characters(screen)
        elif tab == 3:
            self.new(screen)

    def splash(self, screen):
        import curses
        screen.timeout(120)
        for frame in range(14):
            screen.erase()
            h, w = screen.getmaxyx()
            y = max(0, h // 2 - 8)
            for i, line in enumerate(tui.LOGO):
                screen.addnstr(y + i, max(0, (w - len(line)) // 2), line, w - 1, self.style['head'])
            screen.addnstr(y + 6, max(0, (w - len(tui.TAGLINE)) // 2), tui.TAGLINE, w - 1, self.style['quiet'])
            for i, line in enumerate(tui.mascot(frame // 3)):
                screen.addnstr(y + 8 + i, max(0, (w - 9) // 2), line, w - 1, self.style['accent'])
            hello = 'Hi, I am Pip. Press any key.'
            screen.addnstr(y + 14, max(0, (w - len(hello)) // 2), hello[:max(1, frame * 3)], w - 1)
            screen.refresh()
            if screen.getch() != -1:
                break
        try:
            runs.check_model(self.api)
            self.model_ok = True
        except Exception:
            self.model_ok = False

    def who_are_you(self, screen, first=False):
        """The name people in the world know you by: asked once, remembered, changed with y."""
        import json
        saved = {}
        try:
            saved = json.loads(SETTINGS.read_text())
        except (OSError, ValueError):
            pass
        if first and saved.get('name'):
            self.name = saved['name']
            return
        typed = ' '.join(ask(screen, f' What should people in the world call you? (Enter keeps {self.name}): ').split())[:40]
        self.name = typed or self.name
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({**saved, 'name': self.name}, indent=2) + '\n')
        self.notice = f' People will know you as {self.name}.'

    def frame(self, screen, title):
        import curses
        h, w = screen.getmaxyx()
        screen.erase()
        screen.addnstr(0, 0, (' ' + tui.tabs_line(TABS, self.tab, w - 30)).ljust(w), w - 1, curses.A_REVERSE)
        model = 'model ● up' if self.model_ok else 'model ✗ down' if self.model_ok is False else 'model ?'
        screen.addnstr(0, max(0, w - 16), model, 15, self.style['good' if self.model_ok else 'bad'] | curses.A_REVERSE)
        you = f'you: {self.name}  '
        screen.addnstr(0, max(0, w - 16 - len(you)), you, len(you), curses.A_REVERSE)
        screen.addnstr(1, 1, title, w - 2, self.style['head'])
        foot = self.notice or ' Tab/1-4 switch · ↑↓ choose · Enter open · n new run · 4 new world · s stop · y your name · q quit'
        screen.addnstr(h - 1, 0, foot.ljust(w), w - 1, curses.A_REVERSE)
        return h, w

    def draw(self, screen, frame):
        h, w = self.frame(screen, 'Simulations')
        if not self.items:
            screen.addnstr(3, 2, 'No simulations yet. Press n to start one, or 4 to design a new world.', w - 4)
        left = max(40, w - 30)
        for i, r in enumerate(self.items[:h - 5]):
            day = f'day {r["day"]:.1f}' if isinstance(r['day'], (int, float)) else ''
            row = f' {ICONS.get(r["status"], "·")} {r["name"][:24]:<24} {r["status"]:<12} {day:<10} {r["calls"]:>6} calls'
            tone = {'running': 'good', 'failed': 'bad', 'stopped': 'quiet', 'interrupted': 'quiet'}.get(r['status'], 'speech')
            import curses
            screen.addnstr(3 + i, 1, row[:left - 2], left - 2, self.style[tone] | (curses.A_REVERSE if i == self.cursor else 0))
        if w - left >= 14:
            for i, line in enumerate(tui.mascot(frame // 4)):
                screen.addnstr(3 + i, left + 2, line, w - left - 3, self.style['accent'])
            if self.items:
                r = self.items[self.cursor]
                facts = [r['name'], r['status'], f'pid {r["pid"]}' if r['pid'] else '', f'pace {r["pace"]}' if r.get('pace') is not None else '',
                         f'until day {r["horizon"]:.0f}' if r.get('horizon') else '', (r.get('error') or '')[:60]]
                for i, line in enumerate(f for f in facts if f):
                    screen.addnstr(10 + i, left + 2, line, w - left - 3, self.style['quiet'])
        screen.refresh()

    # Runs

    def runs_key(self, screen, key):
        import curses
        if key in (curses.KEY_UP, ord('k')):
            self.cursor = max(0, self.cursor - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            self.cursor = min(max(0, len(self.items) - 1), self.cursor + 1)
        elif key == ord('n'):
            self.start_new(screen)
        elif key == ord('s') and self.items:
            self.stop(screen, self.items[self.cursor])
        elif key == ord('y'):
            self.who_are_you(screen)
        elif key == ord('r'):
            self.refresh()
        elif key in (10, 13, curses.KEY_ENTER) and self.items:
            r = self.items[self.cursor]
            self.selected = r
            actions = ['Watch', 'Characters', *(['Stop'] if r['status'] == 'running' else []),
                       *(['Resume from its last checkpoint'] if r['status'] != 'running' and Path(r['path'], 'world.json').exists() else []), 'Back']
            pick = choose(screen, r['name'], actions)
            if pick is None or actions[pick] == 'Back':
                return
            label = actions[pick]
            if label == 'Watch':
                self.tab = 1
                self.watch(screen)
            elif label == 'Characters':
                self.tab = 2
                self.characters(screen)
            elif label == 'Stop':
                self.stop(screen, r)
            else:
                self.resume(screen, r)

    def ask_until(self, screen, horizon, start=0.0):
        i = choose(screen, 'Run until', [label for label, _ in UNTIL], f'scenario ends at day {horizon:.0f}' if horizon else '')
        if i is None:
            return None
        value = UNTIL[i][1]
        if value == 'ask':
            try:
                value = float(ask(screen, ' Days to run: '))
            except ValueError:
                return None
        return (horizon if value is None else start + value) if horizon or value is not None else None

    def ask_pace(self, screen):
        i = choose(screen, 'How fast?', [label for label, _ in PACE])
        return None if i is None else PACE[i][1]

    def start_new(self, screen):
        options = runs.designs()
        i = choose(screen, 'Start a run from', ['Design a new world…', *[f'{d["name"]}' + (f' · {d["horizon"]:.0f} days' if d['horizon'] else '') for d in options]])
        if i is None:
            return
        if i == 0:
            return self.switch(screen, 3)
        design = options[i - 1]
        name = ask(screen, ' Name for this run (letters, numbers, dashes): ')
        if not name:
            return
        out = runs.ROOT / 'runs' / 'live' / builder.slug(name).replace('_', '-') / 'run'
        from .engine import Engine
        start_day = Engine.load(Path(design['path']) / 'initial.json').day
        until = self.ask_until(screen, design['horizon'], start_day)
        pace = None if until is None else self.ask_pace(screen)
        if pace is None:
            return
        policy = __import__('json').loads(Path(design['path'], 'policy.json').read_text())
        extra = {}
        missing = [m for m in ('sleep', 'attention', 'hormones', 'skills') if m not in policy]
        if missing and choose(screen, 'Also switch on?', [f'Yes: {", ".join(missing)} (recommended)', 'No'], 'modules not yet in this world\'s policy') == 0:
            extra = {m: {} for m in missing}
        try:
            pid = runs.start(Path(design['path']) / 'initial.json', Path(design['path']) / 'policy.json', out, until, pace, self.api, extra=extra)
            self.notice = f' Started {name} (pid {pid}). Open it with Enter → Watch.'
        except Exception as exc:
            self.notice = f' Could not start: {str(exc)[:150]}'
        self.refresh()

    def stop(self, screen, r):
        if r['status'] != 'running':
            self.notice = ' That run is not running.'
            return
        if choose(screen, f'Stop {r["name"]}?', ['Stop it (its last checkpoint stays; you can resume later)', 'Keep it running']) != 0:
            return
        stopped = tui.loading(screen, f'Stopping {r["name"]}', lambda progress: (progress('asking it to stop at a safe point', .3),
                                                                                  runs.stop(r['path']))[1])
        self.notice = ' Stopped.' if stopped else ' It has not stopped yet; it may be in the middle of a model call.'
        self.refresh()

    def resume(self, screen, r):
        policy_path = Path(r['path'], 'policy-used.json')
        horizon = __import__('json').loads(policy_path.read_text()).get('horizon_days') if policy_path.exists() else None
        until = self.ask_until(screen, horizon, r['day'] or 0)
        pace = None if until is None else self.ask_pace(screen)
        if pace is None:
            return
        edits = self.pending.pop(r['path'], [])
        try:
            pid, out = runs.resume(r['path'], until, pace, self.api, edits=edits)
            self.notice = f' Resumed as {out.parent.name} (pid {pid})' + (f' with {len(edits)} change(s)' if edits else '') + '.'
        except Exception as exc:
            self.pending[r['path']] = edits
            self.notice = f' Could not resume: {str(exc)[:150]}'
        self.refresh()

    # Watch

    def need_run(self, screen):
        if self.selected is None and self.items:
            self.selected = self.items[self.cursor]
        if self.selected is None:
            self.notice = ' Pick a simulation in the Runs tab first.'
            self.tab = 0
        return self.selected

    def watch(self, screen):
        from .watch import run_screen
        r = self.need_run(screen)
        if r:
            run_screen(screen, Path(r['path']), 2, self.name)
            self.tab = 0

    # Characters

    def characters(self, screen):
        from .watch import load
        r = self.need_run(screen)
        while r:
            data = tui.loading(screen, f'Reading {r["name"]}', lambda progress: (progress('loading everyone', .5), load(Path(r['path'])))[1])
            people = [p for p in data['people'] if 'card' in p]
            items = [{'key': p['id'], 'search': f'{p["name"]} {p["id"]} {p["card"].get("handle") or ""}',
                      'label': (f'{p["name"][:14]:<14} {p["card"]["age"]:>4.0f}  {p["place"][:18]:<18} mood {p["card"]["valence"]:+.2f}'
                                + (f'  stress {p["card"]["hormones"]["stress"]:.2f}' if 'hormones' in p['card'] else '')
                                + ('  (yours)' if p['card']['role'] == 'yours' else ''))} for p in people]
            key = tui.search_list(screen, f'Characters in {r["name"]} ({len(items)})', items)
            if key is None:
                self.tab = 0
                return
            self.person(screen, r, data, next(p for p in people if p['id'] == key))

    def person(self, screen, r, data, person):
        import curses
        from .watch import person_card
        actions = ['Send a notification', 'Change personality (Big Five)', 'Fine-tune facets', 'Change clinical dials', 'Change hormones',
                   'Change needs', 'Nudge mood', 'Goals', 'Relationships', 'Skills', 'Back']
        while True:
            h, w = self.frame(screen, f'{person["name"]} · {r["name"]}' + (' · live' if r['status'] == 'running' else ' · changes wait for resume'))
            card_w = min(48, w // 2)
            for i, (tag, text) in enumerate(person_card(data, person, card_w - 2)[:h - 4]):
                screen.addnstr(2 + i, 1, text, card_w - 2, self.style.get(tag, 0))
            waiting = self.pending.get(r['path'], [])
            if waiting:
                screen.addnstr(h - 3, card_w + 2, f'{len(waiting)} change(s) waiting for resume', w - card_w - 3, self.style['quiet'])
            screen.refresh()
            i = choose(screen, 'What would you like to do?', actions)
            if i is None or actions[i] == 'Back':
                return
            changes = self.changes_for(screen, person, actions[i])
            if changes is None:
                continue
            if changes == {}:
                self.notice = ' Nothing changed.'
                continue
            self.deliver(r, person, changes)

    def deliver(self, r, person, changes):
        from . import visit
        if 'notify' in changes:
            if r['status'] != 'running':
                self.notice = ' Notifications reach only a running simulation.'
                return
            visit.notify(r['path'], person['id'], changes['notify'], self.name)
            self.notice = f' Notification queued for {person["name"]}.'
            return
        if r['status'] == 'running':
            visit.edit(r['path'], person['id'], changes, self.name)
            self.notice = f' {len(changes)} change(s) sent; they apply at the next event and are logged as interventions.'
        else:
            self.pending.setdefault(r['path'], []).append({'to': person['id'], 'changes': changes, 'name': self.name})
            self.notice = f' Saved; applied to a copy when you resume {r["name"]}.'

    def changes_for(self, screen, person, action):
        c = person['card']
        slide = lambda title, items: tui.slider(screen, title, items)
        if action == 'Send a notification':
            text = ask(screen, f' Notification for {person["name"]}: ')
            return {'notify': text} if text else None
        if action == 'Change personality (Big Five)':
            means = {d: sum(c['facets'][f'{d}{k}'] for k in range(1, 7)) / 6 for d, _ in DOMAINS}
            got = slide('Big Five (moves all six facets of each)', [{'key': d, 'label': label, 'value': round(means[d]), 'low': 0,
                                                                   'high': 100, 'step': 1} for d, label in DOMAINS])
            if got is None:
                return None
            return {f'facet:{d}{k}': max(0.0, min(100.0, c['facets'][f'{d}{k}'] + got[d] - means[d]))
                    for d in got if abs(got[d] - means[d]) > 1e-9 for k in range(1, 7)}
        if action == 'Fine-tune facets':
            from .engine import FACET_NAMES
            got = slide('Facets', [{'key': f, 'label': f, 'value': c['facets'][f], 'low': 0, 'high': 100, 'step': 1} for f in FACET_NAMES])
            return None if got is None else {f'facet:{k}': v for k, v in got.items() if v != c['facets'][k]}
        if action == 'Change clinical dials':
            from .sleep import DIALS
            got = slide('Dials', [{'key': k, 'label': k.replace('_', ' '), 'value': c['dials'][k], 'low': lo, 'high': hi, 'step': .05}
                                  for k, (lo, hi, _) in DIALS.items()])
            return None if got is None else {f'dial:{k}': v for k, v in got.items() if v != c['dials'][k]}
        if action == 'Change hormones':
            if 'hormones' not in c:
                self.notice = ' This world has no hormone module.'
                return None
            ranges = {'stress': (0, .99), 'sleep pressure': (0, 1), 'dopamine': (-.99, .99)}
            got = slide('Hormones', [{'key': k, 'label': k, 'value': round(v, 2), 'low': ranges[k][0], 'high': ranges[k][1], 'step': .05}
                                     for k, v in c['hormones'].items()])
            return None if got is None else {f'hormone:{k.replace(" ", "_")}': v for k, v in got.items() if abs(v - c['hormones'][k]) > 1e-9}
        if action == 'Change needs':
            if 'needs' not in c:
                self.notice = ' This world has no living-world needs.'
                return None
            got = slide('Needs (1 = fully met)', [{'key': k, 'label': k, 'value': round(v, 2), 'low': 0, 'high': 1, 'step': .05}
                                                 for k, v in c['needs'].items()])
            return None if got is None else {f'need:{k}': v for k, v in got.items() if abs(v - c['needs'][k]) > 1e-9}
        if action == 'Nudge mood':
            got = slide('Mood', [{'key': 'mood', 'label': 'mood', 'value': round(c['valence'], 2), 'low': -1, 'high': 1, 'step': .05}])
            return None if got is None or abs(got['mood'] - c['valence']) < 1e-9 else {'mood': got['mood']}
        if action == 'Goals':
            names = [f'{g["text"][:50]} · {g["status"]}' for g in c['goals']] + ['Add a goal']
            i = choose(screen, 'Goals', names)
            if i is None:
                return None
            if i == len(c['goals']):
                text = ask(screen, ' New goal: ')
                return {'goal:add': {'id': builder.slug(text)[:24], 'description': text, 'priority': .6}} if text else None
            s = choose(screen, 'Set this goal to', ['active', 'completed', 'abandoned'])
            return None if s is None else {f'goal:{c["goal_ids"][i]}': ['active', 'completed', 'abandoned'][s]}
        if action == 'Skills':
            if 'skills' not in c:
                self.notice = ' This world has no skills module.'
                return None
            names = [f'{s["label"]} · {s["level"]:.2f} {s["tier"]}' for s in c['skills']] + ['Set a skill by name']
            i = choose(screen, 'Skills', names)
            if i is None:
                return None
            label = c['skills'][i]['label'] if i < len(c['skills']) else ask(screen, ' Skill (e.g. singing, chess, DSA): ')
            if not label:
                return None
            current = c['skills'][i]['level'] if i < len(c['skills']) else 0.0
            got = slide(f'{person["name"]}: {label}', [{'key': 'level', 'label': 'stored level', 'value': round(current, 2),
                                                        'low': 0, 'high': .99, 'step': .05}])
            return None if got is None or abs(got['level'] - current) < 1e-9 else {f'skill:{label}': got['level']}
        if action == 'Relationships':
            if not c['ties']:
                self.notice = ' No relationships recorded yet.'
                return None
            i = choose(screen, 'Whose relationship?', [f'{t["name"]} · {t["role"]}' for t in c['ties']])
            if i is None:
                return None
            tie = c['ties'][i]
            got = slide(f'{person["name"]} → {tie["name"]}', [{'key': k, 'label': k, 'value': round(tie[k], 2), 'low': 0, 'high': 1,
                                                                'step': .05} for k in ('trust', 'closeness')])
            return None if got is None else {f'tie:{tie["id"]}:{k}': v for k, v in got.items() if abs(v - tie[k]) > 1e-9}
        return None

    # New: the builder

    def new(self, screen):
        saved = builder.saved_designs()
        options = ['Start a new design', *[f'Open: {p.parent.name}' for p in saved[:8]]]
        i = choose(screen, 'New simulation', options, 'Pip will help: the model fills in each person one by one.')
        if i is None:
            self.tab = 0
            return
        if i == 0:
            title = ask(screen, ' Title for this world: ')
            if not title:
                self.tab = 0
                return
            design = builder.new_design(title)
        else:
            design = builder.load(saved[i - 1].parent)
        self.edit_design(screen, design)
        self.tab = 0

    def edit_design(self, screen, design):
        while True:
            builder.save(design)
            mains = [p for p in design['people'] if p['role'] == 'main']
            sides = [p for p in design['people'] if p['role'] == 'side']
            begin = design['begin']
            sections = [f'Basics · {design["title"]}, {design["duration_days"]:g} days',
                        f'Places · {len(design["places"])}', f'Main characters · {len(mains)}', f'Side characters · {len(sides)}',
                        f'Relationships · {len(design["relationships"])}', f'Background crowd · {design["crowd"]}',
                        'Modules · ' + ', '.join(k for k, v in design['modules'].items() if v),
                        'How to begin · ' + {'fill': 'model fills the past', 'fast_forward': f'fast-forward {begin["years"]:g} years',
                                             'none': 'no filled past'}[begin['mode']],
                        'Check and build', 'Save and leave']
            problems = builder.check_design(design)
            i = choose(screen, f'Design: {design["title"]}', sections, problems[0] if problems else 'Ready to build.')
            if i is None or i == 9:
                return
            [self.basics, self.places, lambda s, d: self.people(s, d, 'main'), lambda s, d: self.people(s, d, 'side'),
             self.relationships, self.crowd, self.modules, self.begin, self.build][i](screen, design)

    def basics(self, screen, design):
        got = tui.form(screen, 'Basics', [{'key': 'title', 'label': 'Title', 'value': design['title']},
                                          {'key': 'summary', 'label': 'One-line summary', 'value': design['summary']},
                                          {'key': 'duration_days', 'label': 'Duration in days', 'value': str(design['duration_days'])},
                                          {'key': 'seed', 'label': 'Seed', 'value': str(design['seed'])}])
        if got:
            try:
                design.update(title=got['title'], summary=got['summary'], duration_days=float(got['duration_days']), seed=int(got['seed']))
            except ValueError:
                self.notice = ' Duration and seed must be numbers.'

    def places(self, screen, design):
        while True:
            names = [f'{p["label"]} ({p["template"]})' for p in design['places']] + ['Add a place', 'Travel times', 'Back']
            i = choose(screen, 'Places', names)
            if i is None or names[i] == 'Back':
                return
            if names[i] == 'Add a place':
                kinds = list(builder.TEMPLATES)
                k = choose(screen, 'What kind of place?', [f'{k:<9} {builder.PLACE_ART[k][1]}' for k in kinds])
                if k is None:
                    continue
                label = ask(screen, f' Name for this {kinds[k]} (e.g. The Sharma home, Hillside School): ')
                if label:
                    pid = builder.slug(label)
                    design['places'].append({'id': pid, 'template': kinds[k], 'label': label})
            elif names[i] == 'Travel times':
                homes = [p for p in design['places'] if p['template'] == 'home']
                others = [p for p in design['places'] if p['template'] != 'home']
                items = [{'key': f'{h["id"]}|{o["id"]}', 'label': f'{h["label"][:12]}→{o["label"][:12]}',
                          'value': design['routes'].get(f'{h["id"]}|{o["id"]}', 20), 'low': 1, 'high': 120, 'step': 1}
                         for h in homes for o in others]
                got = items and tui.slider(screen, 'Minutes between places', items)
                if got:
                    design['routes'].update(got)
            elif choose(screen, design['places'][i]['label'], ['Remove it', 'Keep it']) == 0:
                design['places'].pop(i)

    def people(self, screen, design, role):
        while True:
            group = [p for p in design['people'] if p['role'] == role]
            names = [f'{p["name"]}, {p["age"]:g} · {p.get("description", "")[:40]}' for p in group] + [f'Add a {role} character', 'Back']
            i = choose(screen, 'Main characters' if role == 'main' else 'Side characters', names)
            if i is None or names[i] == 'Back':
                return
            person = group[i] if i < len(group) else None
            if person is None:
                person = {'id': '', 'name': '', 'age': 20, 'role': role, 'home': None, 'hours': 'at home', 'description': ''}
                if not self.person_form(screen, design, person):
                    continue
                design['people'].append(person)
            else:
                k = choose(screen, person['name'], ['Edit', *(['Personality sliders'] if role == 'main' else []), 'Remove', 'Back'])
                label = None if k is None else ['Edit', *(['Personality sliders'] if role == 'main' else []), 'Remove', 'Back'][k]
                if label == 'Edit':
                    self.person_form(screen, design, person)
                elif label == 'Personality sliders':
                    current = person.get('sliders') or {}
                    got = tui.slider(screen, f'{person["name"]}: personality (50 = average)',
                                     [{'key': d, 'label': name, 'value': current.get(d) if current.get(d) is not None else 50,
                                       'low': 0, 'high': 100, 'step': 1} for d, name in DOMAINS],
                                     'Untouched sliders at 50 let the model read personality from the description.')
                    if got is not None:
                        person['sliders'] = {d: v for d, v in got.items() if v != 50}
                elif label == 'Remove':
                    design['people'].remove(person)
                    design['relationships'] = [r for r in design['relationships'] if person['id'] not in (r['a'], r['b'])]

    def person_form(self, screen, design, person):
        got = tui.form(screen, 'Character', [{'key': 'name', 'label': 'Name', 'value': person['name']},
                                             {'key': 'age', 'label': 'Age', 'value': str(person['age'])},
                                             {'key': 'description', 'label': 'Who they are' if person['role'] == 'main' else 'One line',
                                              'value': person.get('description', '')}] +
                       ([{'key': 'goals', 'label': 'Goals (separate with ;, empty = model decides)',
                          'value': '; '.join(g['description'] for g in person.get('goals', []))}] if person['role'] == 'main' else []))
        if not got or not got['name']:
            return False
        try:
            person['age'] = float(got['age'])
        except ValueError:
            self.notice = ' Age must be a number.'
            return False
        person['name'], person['description'] = got['name'], got['description']
        person['id'] = person['id'] or builder.slug(got['name'])
        if person['role'] == 'main':
            person['goals'] = [{'description': g.strip(), 'priority': .6} for g in (got.get('goals') or '').split(';') if g.strip()]
        homes = [p for p in design['places'] if p['template'] == 'home']
        if not homes:
            self.notice = ' Add a home in Places first; then edit this person to set it.'
        else:
            h = choose(screen, f'Where does {person["name"]} live?', [p['label'] for p in homes])
            if h is not None:
                person['home'] = homes[h]['id']
        hours = list(builder.HOURS)
        k = choose(screen, f'{person["name"]}\'s days', hours)
        if k is not None:
            person['hours'] = hours[k]
            if hours[k] != 'at home':
                places = [p for p in design['places'] if p['template'] != 'home']
                j = choose(screen, 'Where do they go?', [p['label'] for p in places]) if places else None
                if j is not None:
                    person['place'] = places[j]['id']
        return True

    def relationships(self, screen, design):
        from .visit import RELATIONSHIPS
        people = design['people']
        while True:
            label = lambda pid: next((p['name'] for p in people if p['id'] == pid), pid)
            names = [f'{label(r["a"])} → {label(r["b"])}: {r["type"]}' for r in design['relationships']] + ['Add a relationship', 'Back']
            i = choose(screen, 'Relationships', names)
            if i is None or names[i] == 'Back':
                return
            if names[i] != 'Add a relationship':
                if choose(screen, names[i], ['Remove it', 'Keep it']) == 0:
                    design['relationships'].pop(i)
                continue
            if len(people) < 2:
                self.notice = ' Add two people first.'
                return
            a = choose(screen, 'Who?', [p['name'] for p in people])
            b = None if a is None else choose(screen, f'{people[a]["name"]} is … of whom?', [p['name'] for p in people])
            if b is None or a == b:
                continue
            kinds = [*builder.FAMILY, *RELATIONSHIPS, 'something else']
            k = choose(screen, f'{people[a]["name"]} is {people[b]["name"]}\'s …', kinds)
            if k is None:
                continue
            kind = kinds[k] if kinds[k] != 'something else' else ask(screen, ' In a few words: ')
            if kind:
                design['relationships'].append({'a': people[a]['id'], 'b': people[b]['id'], 'type': kind})

    def crowd(self, screen, design):
        options = list(builder.CROWD)
        i = choose(screen, 'Background crowd (people who exist around them, reaching them as news and contacts)', options)
        if i is not None:
            design['crowd'] = options[i]

    def modules(self, screen, design):
        while True:
            names = [f'[{"x" if v else " "}] {k}' for k, v in design['modules'].items()] + ['Done']
            i = choose(screen, 'Modules (Enter toggles)', names)
            if i is None or i == len(names) - 1:
                return
            key = list(design['modules'])[i]
            design['modules'][key] = not design['modules'][key]

    def begin(self, screen, design):
        i = choose(screen, 'How should the simulation begin?',
                   ['At their ages; the model writes each adult\'s past first', 'Fast-forward some years, scripted (cheap, sparse)',
                    'At their ages, with no written past'])
        if i == 0:
            design['begin'] = {'mode': 'fill', 'years': 0}
        elif i == 1:
            try:
                years = float(ask(screen, ' How many years to fast-forward? '))
                design['begin'] = {'mode': 'fast_forward', 'years': years}
            except ValueError:
                self.notice = ' Years must be a number.'
        elif i == 2:
            design['begin'] = {'mode': 'none', 'years': 0}

    def build(self, screen, design):
        problems = builder.check_design(design)
        if problems:
            tui.message(screen, 'Not ready yet', problems)
            return
        i = choose(screen, f'Build {design["title"]}', ['Build with the model (recommended)', 'Build without the model (sampled personalities)', 'Back'])
        if i not in (0, 1):
            return
        model = None
        if i == 0:
            try:
                model = runs.check_model(self.api)
            except Exception as exc:
                tui.message(screen, 'The model is not reachable', [str(exc)[:160]])
                return
        try:
            folder = tui.loading(screen, f'Building {design["title"]}', lambda progress: builder.build(
                design, api=self.api if model else None, model=model, progress=progress))
        except Exception as exc:
            tui.message(screen, 'The build stopped', [str(exc)[:200]])
            return
        if choose(screen, 'Built!', ['Start a run now', 'Later'], str(folder)) == 0:
            self.start_new(screen)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--api', default=runs.DEFAULT_API)
    args = parser.parse_args()
    from .visit import your_name
    import curses
    curses.wrapper(App(args.api, your_name()).run)


if __name__ == '__main__':
    main()
