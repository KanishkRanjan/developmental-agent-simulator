# environment-v5: overnight live run (started 2026-10-17T21:12Z)

Same scenario as environment-v4 (Priya's world, 7 characters, 62.09 days), recompiled with code at commit c99ff42.
Policy = compiled policy + sleep {} + society_layer {} + attention {} (all defaults). Mood kernel: power_law (standing user decision).

Changes since v4 to look for:
- attention allocation on (FULL/GIST/NONE per listener); calibration unverified
- consolidation no longer stalls after day 3; lessons about people/events, not own habits; near-duplicate beliefs merge; at most 4 inferred lessons per prompt
- previous-session view shows the person's own words; six-word phrase repeats are flagged
- sleep resolves at the end of each routine's night (not mid-afternoon)
- parents have a 'child' relationship to Priya
- shown-but-not-memory citations no longer cost repair calls; transient model errors retried twice

Watch: python3 -m devsim.watch runs/live/environment-v5/run
