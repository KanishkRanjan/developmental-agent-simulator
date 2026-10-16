# MiroFish prompt review for our 27B personality prototype

Reviewed upstream [MiroFish commit `7657031`](https://github.com/666ghj/MiroFish/tree/7657031ac01184afe2cb220f5ee3545573b5e843) and its pinned OASIS dependency, [version 0.2.5](https://github.com/camel-ai/oasis/tree/e97a1d83761605a24a7dc91fa4d4e9defffa7e23). This review concerns the code paths for persona generation and agent prompting. It is not a replication of MiroFish's full social-media simulation.

## What the model actually receives

MiroFish first asks an LLM to turn an entity's name, type, summary, attributes, and up to 3,000 characters of context into a bio and a roughly 2,000-character narrative persona. The requested persona includes age, career, education, relationships, MBTI, posting habits, views, distinctive experiences, and “personal memories.” [Persona-generation prompt](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/oasis_profile_generator.py#L716-L768)

For Twitter, MiroFish concatenates the bio and persona into OASIS's private `user_char` field. For Reddit, it passes `persona` separately. [Twitter export](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/oasis_profile_generator.py#L1114-L1158), [Reddit export](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/oasis_profile_generator.py#L1190-L1222)

OASIS then wraps that text in a short system prompt with `OBJECTIVE`, `SELF-DESCRIPTION`, and `RESPONSE METHOD` sections. It asks the agent to keep actions consistent with its self-description, observe the platform environment, and use tools to act. The detailed behavioral constraints are mostly in the generated prose, not in a formal personality model. [OASIS system prompts](https://github.com/camel-ai/oasis/blob/e97a1d83761605a24a7dc91fa4d4e9defffa7e23/oasis/social_platform/config/user.py#L44-L110), [environment/action call](https://github.com/camel-ai/oasis/blob/e97a1d83761605a24a7dc91fa4d4e9defffa7e23/oasis/social_agent/agent.py#L125-L150)

For interviews, MiroFish prefixes the question with an instruction to consider the agent's persona, past memories, and actions. OASIS supplies the memory context available at that moment. The prefix itself does not verify that a relevant event was retrieved or distinguish a witnessed event from a rumor. [MiroFish interview prefix](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/api/simulation.py#L53-L73), [OASIS interview context](https://github.com/camel-ai/oasis/blob/e97a1d83761605a24a7dc91fa4d4e9defffa7e23/oasis/social_agent/agent.py#L197-L219)

MiroFish also generates per-agent activity settings such as active hours, posting rate, stance, and influence. The prompt seeds these with entity-type ranges and China-time examples. That is a separate behavior control channel beyond the persona. [Activity-config prompt](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/simulation_config_generator.py#L835-L875)

## What is useful for us

The clear separation between the agent's objective, self-description, and response method is a sensible organizational pattern, although the direct test below did not improve action control. Separating a public bio from the internal profile is useful once we simulate social interactions: other agents should not automatically see an individual's full internal state. The platform environment is passed as the current observation rather than baked into the permanent persona.

## What I would change for our research aim

1. **Do not promote generated biography to observed fact.** A 3,000-character source may omit age, career, relationships, or memories, yet MiroFish's prompt asks the LLM to supply them. Its export also defaults missing age to 30 and MBTI to `ISTJ`. Those choices may be acceptable for explicitly fictional agents, but they would contaminate a test of a real person's behavior. Keep `observed_fact`, `reported_claim`, `agent_belief`, and `synthetic_assumption` distinct. Unknown fields stay unknown. [Prompt](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/oasis_profile_generator.py#L731-L760), [fallbacks](https://github.com/666ghj/MiroFish/blob/7657031ac01184afe2cb220f5ee3545573b5e843/backend/app/services/oasis_profile_generator.py#L1219-L1222)
2. **Keep traits as explicit, inspectable data.** Our 30-facet profile should remain separate from a writing-style description. MiroFish's narrative persona and generated MBTI give the model character cues, but they do not let us tell which trait caused a behavioral difference. At this stage, do not replace the facet profile with a long story.
3. **Separate stable traits from the present situation.** Once we add mood, memory, and relationships, the prompt should label each layer and its source. An agent may act differently because of a witnessed event, a rumor, current mood, or a stable tendency; these should not be collapsed into one paragraph. This is a proposed architecture, not a validated improvement yet.
4. **Do not copy activity defaults as human behavior estimates.** MiroFish's rate and schedule ranges are explicit assumptions by account type. We can use such settings for a social-media demo, but must calibrate them before interpreting output as research evidence.

## Direct prompt-style test on the same local 27B model

The test script is [personality_prompt_style_pilot.py](personality_prompt_style_pilot.py). It gives both prompts the identical 30 facet scores and meanings, compares the existing paragraph prompt with an OASIS-inspired sectioned prompt, and asks 12 new situations of paired high/low profiles at temperature zero. The outcome is **behavioral controllability in synthetic situations**, not accuracy about humans.

| Prompt | Concordant actions | Pairs with opposite expected actions |
|---|---:|---:|
| Existing 30-facet prompt | 17/24 | 5/12 |
| OASIS-inspired sectioned prompt | 17/24 | 5/12 |

The sectioned wording did **not** improve this small test. It helped some cases and hurt others: it made one low-assertiveness profile state a preference and one low-imagination profile invent a dragon. The unchanged aggregate is a reason to keep the existing prompt for now, rather than add sections solely because MiroFish uses them.

The 12 situations and scoring rubric were written before generation. Responses were shuffled for action coding, but the same analyst designed and scored the test. The situations are synthetic, and 48 answers are too few for a general model claim. Both prompts used the same facet values and meaning glosses; the [scored responses](prompt-style-scored.jsonl) and [test script](personality_prompt_style_pilot.py) show the exact comparison.

**Recommendation:** keep the current 27B API and explicit 30-facet prompt as the personality baseline. Borrow MiroFish's public-versus-private profile distinction when we reach social interactions. Build provenance and knowledge boundaries before generating life histories, rather than copying a long narrative persona. Validate each addition against held-out behavior; this source review and prompt-style test do not establish real-person replication.
