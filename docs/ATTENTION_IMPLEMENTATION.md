# Attention allocation (opt-in)

The module decides, for each (listener, event) pair, how much of the event the listener attends to. That weight `a` (0 to 1) and a tier (FULL, GIST, NONE) then decide how much is encoded, felt and shown back to the model.

This is psychological attention (Kahneman 1973), not transformer attention. Every number is a design default; see [attention_evidence.md](attention_evidence.md) for the evidence tag on each.

- Code: `devsim/attention.py`
- Parameters: `devsim/policies/attention.json`
- Checks: `checks/check_attention.py` (19 named checks)

## Turning it on

Add an `attention` block to a `Lifetime` policy: `{}` uses the defaults, and overrides use the parameter names from the JSON file, for example `{"felt_ignored": true}`. Bad config fails at load.

- **No block:** the engine is unchanged.
- **`{"enabled": false}`:** the world is byte-identical to running without the block. A golden check confirms this on a scripted 10-day household world.

No archived policy has the block, so archived runs replay unchanged.

## Where it is integrated

| Point | File | What changes |
|---|---|---|
| Event delivery | `Engine.advance` (`engine.py`), the per-recipient loop | One `attention.allocate` call per (listener, event), after the LLM appraisal and before encoding. This is the only call site. |
| Encoding | same loop | Without sleep, stability is multiplied by `a^gamma_enc`. With sleep, `a^gamma_enc` goes into the buffer entry's `attention_weight`, which `sleep.trace_weight` multiplies in, so inattentive events are more often dropped at the next sleep. GIST traces also get `gist_stability_factor`. |
| GIST / NONE content | `attention.encoded` | GIST encodes a coarse line: who, main topic and rough valence ("Half-noticed: Rohan, something about work or duties; it seemed unpleasant."). NONE keeps a hidden receipt with tier `unattended`, which is in `sleep.HIDDEN`. The original observation always stays in `state['events']`. NONE also records no reminders or mentions; GIST still records mentions. The physical encounter is recorded either way. |
| Mood and arousal | `Engine.mood` | Each event's impulse is scaled by `a`, in full when captured, and by 0 when NONE. |
| LLM context | `cognition.views`, `Engine.memories` (via `HIDDEN`), `household.conversation_memory`, `Engine.consolidate` | NONE is left out. GIST appears as its one-line summary. FULL is shown as before. |
| Response gating hook | `AttentionResult.may_skip_response` | True for GIST or NONE events that are not addressed. No gate uses it yet. |
| Relationships (phase 4, flag `felt_ignored`, off) | `attention.felt_ignored` → `Engine.relate` | A face-to-face speaker may notice low attention and lose `ignored_penalty` closeness. Each change is logged in `attention_stats.felt_ignored`. |
| Addressing | `visit.py` | The researcher's addressed lines and phone-call lines now carry `addressed: [person]`. `addressed` is validated as a list of ids. |
| Policy | `lifetime.py` | The `attention` block is configured next to `sleep`. |

Per-agent state lives in `agent['attention_state']`: open streams with their `u`, `T`, last-seen day, last event and drift end, plus a `drift_periods` count. It is updated only when an event arrives, and streams older than `stream_expiry_minutes` are dropped when it is next read. The result of each event is stored on its receipt as `memory_meta[event]['attention']`. Counters are in `state['attention_stats']`: allocations, events with no derivable topic tags (`neutral_tags`), and felt-ignored records.

## Event fields

The engine has no native actor, stream, address or topic fields, so they are derived:

- **actor:** the observation's `source`, when it is an entity other than the listener.
- **stream:** `@conversation:<key>`, `@call:<n>`, or the event itself.
- **addressed:** the observation's `addressed` list. A resolved mention of the listener (their own name) also counts.
- **mentioned:** `references`, plus resolved `mentions`.
- **topic tags:** authored `topic_tags`, else the event-prefix and keyword rule tables in the config. If nothing matches, every tag gets 0.2 and the miss is counted.
- **threat salience:** authored `threat_salience`, else `max(0, -valence) x arousal` from the listener's own appraisal.

An agent's own actions and thoughts are always FULL.

## Providers still on defaults

Override any of these with `engine.attention_providers[name]`.

| Provider | Default | Real signal when available |
|---|---|---|
| closeness | Recorded relationship closeness (faded by the `society` policy). With nothing above 0 recorded: a caregiver, child or biological parent (from identity facts) gets 0.6, any other known person 0.3, and a stranger 0.05. | Society-layer tie strength for bound characters |
| surprise | 0 | A prediction-error module. The habituation novelty `1/(1+exposures)` is a candidate. |
| fatigue | 0 | Hours awake since `sleep.wake_day` and the last sleep quality |
| asleep | False | Agents are never delivered events outside their waking hours, so nothing sets this yet. |
| goal match | 0 | Goal and plan overlap with the event |

## Limits

- Attention runs after the LLM appraisal, so it saves no model calls. Moving it before appraisal would save calls on NONE events but lose threat salience.
- The keyword table is English, whole-word and small.
- Not live-verified with the 27B model, and no parameter is calibrated.

## Most sensitive parameters for calibration

1. **`arousal_shape`, `kappa` [U].** Mood arousal 0 means "calm", but the inverted U treats it as under-aroused, so a calm agent has only half its capacity (`1 - 2 x 0.25`). In checks, interested listeners in a calm conversation reached FULL on only 14% of turns. This is the biggest single lever, and `monotone` removes it.
2. **`a_full`, `a_gist`.** These set how much of everyday talk becomes GIST: for a typical stranger or acquaintance, most of it does.
3. **`closeness_known`, `closeness_stranger`, `w_rel`.** Most relationships in the authored worlds sit at closeness 0, so the "known" default decides speaker closeness for nearly everyone.
4. **`lam0_per_minute`, `drift_mean_minutes`, `d_drift`.** Over 120 turns, bored listeners drifted on about 25% of turns.
5. **`s_0`, `s_dys`, `lam_dys`, `u0_dys`.** Together these set how strongly dysregulation lowers attention and makes it more variable (mean `a` 0.31 vs 0.19 for the lowest and highest quartiles).
6. **`ignored_penalty`, `notice_gain`.** In checks, 80 turns with a highly dysregulated listener cost a close speaker 0.25 closeness.
