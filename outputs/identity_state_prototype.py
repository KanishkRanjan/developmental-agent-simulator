"""Minimal event/observation/mood prototype for a social-simulation experiment.

The numerical parameters are illustrative engineering choices, not fitted
human-memory or mood parameters. All time values are simulated days.
"""

from dataclasses import dataclass
from math import exp, isclose, log
import re


@dataclass(frozen=True)
class Observation:
    event_id: str
    day: float
    text: str
    source: str
    valence: float = 0.0
    arousal: float = 0.0
    stability_days: float = 3.0


def recall_availability(age_days: float, stability_days: float) -> float:
    if age_days < 0 or stability_days <= 0:
        raise ValueError('Age must be nonnegative and stability positive')
    return 1 / (1 + age_days / (9 * stability_days))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+', text.lower()))


class AgentWorld:
    def __init__(self, mood_half_life_days: float = 1.0):
        if mood_half_life_days <= 0:
            raise ValueError('Mood half-life must be positive')
        self.mood_half_life_days = mood_half_life_days
        self.events: dict[str, tuple[float, str]] = {}
        self.observations: dict[str, list[Observation]] = {}
        self._last_day = -1.0

    def add_event(self, event_id: str, day: float, world_description: str,
                  recipients: dict[str, Observation]) -> None:
        if event_id in self.events:
            raise ValueError(f'Duplicate event: {event_id}')
        if day < self._last_day or day < 0:
            raise ValueError('Events must arrive in simulated-time order')
        if any(o.event_id != event_id or o.day != day or not -1 <= o.valence <= 1
               or not 0 <= o.arousal <= 1 or o.stability_days <= 0
               for o in recipients.values()):
            raise ValueError('Invalid observation')
        self.events[event_id] = (day, world_description)
        self._last_day = day
        for agent, observation in recipients.items():
            self.observations.setdefault(agent, []).append(observation)

    def mood(self, agent: str, day: float) -> tuple[float, float]:
        if day < 0:
            raise ValueError('Day must be nonnegative')
        valence = arousal = previous = 0.0
        for item in self.observations.get(agent, []):
            if item.day > day:
                break
            decay = exp(-log(2) * (item.day - previous) / self.mood_half_life_days)
            valence = max(-1.0, min(1.0, valence * decay + item.valence))
            arousal = max(0.0, min(1.0, arousal * decay + item.arousal))
            previous = item.day
        decay = exp(-log(2) * (day - previous) / self.mood_half_life_days)
        return round(valence * decay, 4), round(arousal * decay, 4)

    def retrieve(self, agent: str, query: str, day: float, k: int = 4,
                 method: str = 'typed') -> list[Observation]:
        if day < 0 or k < 0:
            raise ValueError('Invalid retrieval time or count')
        items = [o for o in self.observations.get(agent, []) if o.day <= day]
        if method == 'full':
            return items
        if method == 'recent':
            return sorted(items, key=lambda o: o.day, reverse=True)[:k]
        if method not in ('lexical', 'typed'):
            raise ValueError('Unknown retrieval method')
        query_tokens = _tokens(query)
        def score(o: Observation) -> tuple[float, float]:
            overlap = len(query_tokens & _tokens(o.text + ' ' + o.source))
            if method == 'lexical':
                return overlap, o.day
            age = day - o.day
            r = recall_availability(age, o.stability_days)
            # ponytail: fixed weights; fit on held-out recall data before realism claims.
            return 3 * overlap + 0.35 * r + 0.15 * o.arousal, o.day
        return sorted(items, key=score, reverse=True)[:k]


def self_check() -> None:
    assert isclose(recall_availability(3, 3), 0.9)
    world = AgentWorld()
    world.add_event('private', 0, 'A tells B the key is blue', {
        'B': Observation('private', 0, 'A said the key is blue', 'A')})
    assert not world.retrieve('C', 'key color', 0)
    assert len(world.retrieve('B', 'key color', 0)) == 1
    try:
        world.add_event('private', 0, 'retry', {})
    except ValueError:
        pass
    else:
        raise AssertionError('Duplicate event accepted')
    before = list(world.observations['B'])
    world.retrieve('B', 'key', 10)
    assert world.observations['B'] == before
    for i in range(100):
        world.add_event(f'negative{i}', i + 1, 'setback', {
            'B': Observation(f'negative{i}', i + 1, 'setback', 'direct', -0.8, 0.8)})
    low, alert = world.mood('B', 100)
    assert -1 <= low <= 1 and 0 <= alert <= 1
    recovered, settled = world.mood('B', 110)
    assert abs(recovered) < 0.01 and settled < 0.01


if __name__ == '__main__':
    self_check()
    print('Internal checks passed')
