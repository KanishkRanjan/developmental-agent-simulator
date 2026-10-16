"""Numerical checks of the supplied mood report's stated power-law equations.

This reproduces the relevant formulas, not the report's whole simulator.
Times use the same unit as tau; the report does not fix that unit.
"""

import json
from math import tanh


def paper_mood(impulses, now, cull=False):
    values = [intensity * valence * (1 + (now - timestamp) / tau) ** -0.5
              for intensity, valence, tau, timestamp in impulses]
    if cull:
        values = [value for value in values if abs(value) > 0.01]
    return tanh(sum(values))


def audit():
    micro_events = [(0.009, 1.0, 1.0, 0.0)] * 100
    full_sum = paper_mood(micro_events, 0.0)
    culled_sum = paper_mood(micro_events, 0.0, cull=True)

    # From the report's process_event pseudocode: negative reactivity 1+1.5*N,
    # inertia 1+2*N, tau=max(1, adjusted_intensity*100*inertia).
    neuroticism = 0.5
    adjusted = 0.8 * (1 + 1.5 * neuroticism)
    tau = adjusted * 100 * (1 + 2 * neuroticism)
    one_event = [(adjusted, -1.0, tau, 0.0)]
    forty_years_if_days = paper_mood(one_event, 40 * 365)
    forty_years_if_hours = paper_mood(one_event, 40 * 365 * 24)

    # Report's retrieve_and_ruminate adds a fresh event on each qualifying
    # retrieval. Ten same-time retrievals of one negative memory, arousal=.8,
    # rumination_mult=.5, produce ten new impulses before any refractory gate.
    rumination = 0.8 * neuroticism * 0.5
    adjusted_rumination = rumination * (1 + 1.5 * neuroticism)
    rumination_tau = adjusted_rumination * 100 * (1 + 2 * neuroticism)
    ten_retrievals = paper_mood([(adjusted_rumination, -1.0, rumination_tau, 0.0)] * 10, 0.0)

    assert full_sum > 0.7 and culled_sum == 0
    assert forty_years_if_days < -0.1
    assert ten_retrievals < -0.99
    return {
        '100_micro_events_true_mood': full_sum,
        '100_micro_events_with_paper_culling': culled_sum,
        'single_negative_event_after_40_years_if_units_days': forty_years_if_days,
        'single_negative_event_after_40_years_if_units_hours': forty_years_if_hours,
        'mood_after_10_same_time_ruminations': ten_retrievals,
        'assumed_event_tau_in_report_time_units': tau,
    }


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
