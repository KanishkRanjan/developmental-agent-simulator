"""Shared terminal widgets for the watcher and the control panel (curses, standard library only).

Pure helpers (slider_text, filter_items, tabs_line, mascot frames) have no terminal dependency and are checked
without one; the interactive widgets draw boxed overlays and return the user's choice, or None on Esc.
"""
import queue
import textwrap
import threading
import time

LOGO = [
    r" ____  _______     _______ ___ __  __ ",
    r"|  _ \| ____\ \   / / ___|_ _|  \/  |",
    r"| | | |  _|  \ \ / /\___ \| || |\/| |",
    r"| |_| | |___  \ V /  ___) | || |  | |",
    r"|____/|_____|  \_/  |____/___|_|  |_|",
]
TAGLINE = 'developmental agent simulator · control panel'
MASCOT = [  # Pip, the panel's little robot: idle, blink, wave, thinking
    ["  .---.  ", " [ o o ] ", " |  -  | ", " '-----' ", "  /| |\\  "],
    ["  .---.  ", " [ - - ] ", " |  -  | ", " '-----' ", "  /| |\\  "],
    ["  .---. /", " [ o o ]/", " |  v  | ", " '-----' ", "  /| |   "],
    ["  .---. ?", " [ o O ] ", " |  ~  | ", " '-----' ", "  /| |\\  "],
]
SPINNER = '|/-\\'


def read_key(screen):
    """getch that also understands arrow keys sent as ESC [ A or ESC O A, whatever the terminal's keypad mode."""
    import curses
    key = screen.getch()
    if key != 27:
        return key
    screen.nodelay(True)
    try:
        follow = screen.getch()
        if follow in (ord('['), ord('O')):
            return {ord('A'): curses.KEY_UP, ord('B'): curses.KEY_DOWN, ord('C'): curses.KEY_RIGHT,
                    ord('D'): curses.KEY_LEFT}.get(screen.getch(), 27)
        if follow != -1:
            curses.ungetch(follow)
        return 27
    finally:
        screen.nodelay(False)


def read_wide(screen):
    """get_wch with the same arrow handling (for text entry that needs non-ASCII letters)."""
    import curses
    key = screen.get_wch()
    if key != '\x1b':
        return key
    screen.nodelay(True)
    try:
        try:
            follow = screen.get_wch()
        except curses.error:
            return '\x1b'
        if follow in ('[', 'O'):
            try:
                last = screen.get_wch()
            except curses.error:
                return '\x1b'
            return {'A': curses.KEY_UP, 'B': curses.KEY_DOWN, 'C': curses.KEY_RIGHT, 'D': curses.KEY_LEFT}.get(last, '\x1b')
        curses.unget_wch(follow)
        return '\x1b'
    finally:
        screen.nodelay(False)


def mascot(frame):
    """One mascot frame (a list of lines); frames cycle idle, blink, idle, wave."""
    return MASCOT[[0, 1, 0, 2][frame % 4]]


def init_colors():
    """Colour styles for every screen: head, speech, quiet, accent, good, bad."""
    import curses
    curses.use_default_colors()
    for pair, color in ((1, curses.COLOR_CYAN), (2, -1), (3, curses.COLOR_YELLOW), (4, curses.COLOR_MAGENTA),
                        (5, curses.COLOR_GREEN), (6, curses.COLOR_RED)):
        curses.init_pair(pair, color, -1)
    return {'head': curses.color_pair(1) | curses.A_BOLD, 'speech': curses.color_pair(2), 'quiet': curses.color_pair(3),
            'accent': curses.color_pair(4) | curses.A_BOLD, 'good': curses.color_pair(5), 'bad': curses.color_pair(6)}


def tabs_line(names, active, width):
    """The tab bar: ' 1 Runs │ 2 Watch │ …' with the active tab marked."""
    parts = [(f'[{i + 1} {n}]' if i == active else f' {i + 1} {n} ') for i, n in enumerate(names)]
    return ' │'.join(parts)[:width]


def slider_text(label, value, low, high, cells=20, label_width=16):
    """'label   ████░░░░  value' for a value in [low, high]."""
    full = max(0, min(cells, round((value - low) / (high - low) * cells))) if high > low else 0
    shown = f'{value:+.2f}' if low < 0 else f'{value:.0f}' if high > 1 else f'{value:.2f}'
    return f'{label[:label_width]:<{label_width}} {"█" * full}{"░" * (cells - full)} {shown}'


def filter_items(items, query):
    """Items whose 'search' text contains every word of the query (case-insensitive), in their original order."""
    words = query.lower().split()
    return [item for item in items if all(w in item['search'].lower() for w in words)]


def choose(screen, title, options, note=''):
    """A boxed pick list: arrows or a number, Enter to pick, Esc to go back. Returns the index or None."""
    import curses
    current, top = 0, 0
    screen.timeout(-1)
    screen.touchwin()  # repaint the main screen, so an earlier box does not linger behind this one
    screen.refresh()
    try:
        while True:
            height, width = screen.getmaxyx()
            box_w = min(width - 2, max(34, len(title) + 6, len(note) + 4, *(len(o) + 8 for o in options)))
            rows = max(1, min(len(options), height - 7))
            top = min(max(top, current - rows + 1), current)
            box_h = rows + 4 + bool(note)
            win = curses.newwin(box_h, box_w, max(0, (height - box_h) // 2), max(0, (width - box_w) // 2))
            win.erase()
            win.box()
            win.addnstr(0, 2, f' {title} ', box_w - 4, curses.A_BOLD)
            for i in range(top, min(len(options), top + rows)):
                label = (f'{i + 1}. ' if i < 9 else '   ') + options[i]
                win.addnstr(1 + i - top, 2, label.ljust(box_w - 4), box_w - 4, curses.A_REVERSE if i == current else 0)
            if note:
                win.addnstr(box_h - 3, 2, note, box_w - 4, curses.A_DIM)
            win.addnstr(box_h - 2, 2, '↑↓ or number · Enter choose · Esc back', box_w - 4, curses.A_DIM)
            win.refresh()
            key = read_key(screen)
            if key in (curses.KEY_UP, ord('k')):
                current = (current - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord('j')):
                current = (current + 1) % len(options)
            elif ord('1') <= key <= ord('9') and key - ord('1') < len(options):
                return key - ord('1')
            elif key in (10, 13, curses.KEY_ENTER):
                return current
            elif key in (27, ord('q')):
                return None
    finally:
        screen.timeout(250)


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


def slider(screen, title, items, note=''):
    """Edit several values: ↑↓ pick, ←→ step, [ ] ten steps, Enter keep, Esc cancel.
    items: [{'key', 'label', 'value', 'low', 'high', 'step'}]. Returns {key: value} or None."""
    import curses
    values = [dict(i) for i in items]
    current = 0
    screen.timeout(-1)
    screen.touchwin()
    screen.refresh()
    try:
        while True:
            height, width = screen.getmaxyx()
            box_w = min(width - 2, 64)
            rows = max(1, min(len(values), height - 7))
            top = max(0, min(current - rows + 1, len(values) - rows))
            box_h = rows + 4 + bool(note)
            win = curses.newwin(box_h, box_w, max(0, (height - box_h) // 2), max(0, (width - box_w) // 2))
            win.erase()
            win.box()
            win.addnstr(0, 2, f' {title} ', box_w - 4, curses.A_BOLD)
            cells = max(6, box_w - 30)
            for i in range(top, min(len(values), top + rows)):
                v = values[i]
                win.addnstr(1 + i - top, 2, slider_text(v['label'], v['value'], v['low'], v['high'], cells).ljust(box_w - 4),
                            box_w - 4, curses.A_REVERSE if i == current else 0)
            if note:
                win.addnstr(box_h - 3, 2, note, box_w - 4, curses.A_DIM)
            win.addnstr(box_h - 2, 2, '↑↓ pick · ←→ adjust · [ ] faster · Enter keep · Esc cancel', box_w - 4, curses.A_DIM)
            win.refresh()
            key = read_key(screen)
            v = values[current]
            if key in (curses.KEY_UP, ord('k')):
                current = (current - 1) % len(values)
            elif key in (curses.KEY_DOWN, ord('j')):
                current = (current + 1) % len(values)
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord('['), ord(']'), ord('h'), ord('l')):
                sign = -1 if key in (curses.KEY_LEFT, ord('['), ord('h')) else 1
                step = v['step'] * (10 if key in (ord('['), ord(']')) else 1)
                v['value'] = round(min(v['high'], max(v['low'], v['value'] + sign * step)), 6)
            elif key in (10, 13, curses.KEY_ENTER):
                return {v['key']: v['value'] for v in values}
            elif key == 27:
                return None
    finally:
        screen.timeout(250)


def search_list(screen, title, items, note=''):
    """Type to filter (name, id, handle), ↑↓ to move, Enter to open, Esc to go back.
    items: [{'key', 'label', 'search'}]. Returns the chosen key or None."""
    import curses
    query, current = '', 0
    screen.timeout(-1)
    screen.touchwin()
    screen.refresh()
    try:
        while True:
            height, width = screen.getmaxyx()
            shown = filter_items(items, query)
            current = max(0, min(current, len(shown) - 1))
            box_w = min(width - 2, max(40, *(len(i['label']) + 6 for i in items or [{'label': ''}])))
            rows = max(1, height - 8)
            top = max(0, min(current - rows + 1, max(0, len(shown) - rows)))
            box_h = min(height - 1, min(rows, max(1, len(shown))) + 5)
            win = curses.newwin(box_h, box_w, max(0, (height - box_h) // 2), max(0, (width - box_w) // 2))
            win.erase()
            win.box()
            win.addnstr(0, 2, f' {title} ', box_w - 4, curses.A_BOLD)
            win.addnstr(1, 2, f'search: {query}_'.ljust(box_w - 4), box_w - 4, curses.A_UNDERLINE)
            for i in range(top, min(len(shown), top + box_h - 5)):
                win.addnstr(2 + i - top, 2, shown[i]['label'].ljust(box_w - 4), box_w - 4, curses.A_REVERSE if i == current else 0)
            if not shown:
                win.addnstr(2, 2, 'nothing matches', box_w - 4, curses.A_DIM)
            win.addnstr(box_h - 2, 2, (note or 'type to search · ↑↓ move · Enter open · Esc back'), box_w - 4, curses.A_DIM)
            win.refresh()
            key = read_wide(screen)
            if key in (curses.KEY_UP,):
                current = max(0, current - 1)
            elif key in (curses.KEY_DOWN,):
                current = min(len(shown) - 1, current + 1)
            elif key in ('\n', '\r', curses.KEY_ENTER):
                if shown:
                    return shown[current]['key']
            elif key == '\x1b':
                return None
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                query, current = query[:-1], 0
            elif isinstance(key, str) and key.isprintable():
                query, current = query + key, 0
    finally:
        screen.timeout(250)


def form(screen, title, fields, note=''):
    """Fill several text fields: ↑↓ pick, Enter edit, 'Done' to finish, Esc cancel.
    fields: [{'key', 'label', 'value'}]. Returns {key: value} or None."""
    values = [dict(f) for f in fields]
    while True:
        labels = [f'{f["label"]}: {f["value"] if f["value"] not in (None, "") else "—"}' for f in values] + ['Done']
        i = choose(screen, title, labels, note)
        if i is None:
            return None
        if i == len(values):
            return {f['key']: f['value'] for f in values}
        text = ask(screen, f' {values[i]["label"]}: ')
        if text:
            values[i]['value'] = text


def loading(screen, title, job, style=None):
    """Run job(progress) in a thread while the mascot animates; progress(text, fraction) updates the line.
    Returns the job's result, or raises its exception."""
    import curses
    updates, box = queue.Queue(), {}
    def worker():
        try:
            box['result'] = job(lambda text, fraction=None: updates.put((text, fraction)))
        except BaseException as exc:  # handed to the screen thread
            box['error'] = exc
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    text, fraction, frame, log = 'starting', 0.0, 0, []
    screen.timeout(120)
    try:
        while thread.is_alive() or not updates.empty():
            while not updates.empty():
                text, f = updates.get()
                fraction = fraction if f is None else f
                log.append(text)
            height, width = screen.getmaxyx()
            screen.erase()
            art = mascot(3 if frame % 8 < 4 else 0)
            y = max(1, height // 2 - 7)
            screen.addnstr(y, 2, f' {title} ', width - 4, curses.A_BOLD)
            for i, line in enumerate(art):
                screen.addnstr(y + 2 + i, 4, line, width - 6)
            bar_w = max(10, min(50, width - 20))
            done = round(fraction * bar_w)
            screen.addnstr(y + 2, 16, f'{SPINNER[frame % 4]} {text}'[:width - 18], width - 18)
            screen.addnstr(y + 4, 16, f'[{"█" * done}{"░" * (bar_w - done)}] {fraction:.0%}', width - 18)
            for i, line in enumerate(log[-(height - y - 10):][-6:]):
                screen.addnstr(y + 8 + i, 16, ('· ' + line)[:width - 18], width - 18, curses.A_DIM)
            screen.refresh()
            screen.getch()
            frame += 1
        thread.join()
    finally:
        screen.timeout(250)
    if 'error' in box:
        raise box['error']
    return box.get('result')


def message(screen, title, lines):
    """A boxed message; any key closes it."""
    choose(screen, title, ['OK'], ' '.join(lines)[:200])
