"""Author-written stimuli, fixed before inference. No questionnaire training data."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRAITS = 'OCEAN'
TOPICS = ['a local photography walk', 'a shared vegetable garden', 'a board-game evening',
          'learning a musical instrument', 'a small book club', 'a community art project',
          'a weekend picnic', 'organizing a home workspace', 'trying a new recipe',
          'a neighborhood walking group', 'a personal writing project', 'a casual sports group',
          'a museum visit', 'a language exchange', 'making a handmade gift', 'a film discussion']
FRAMES = [
 'We are talking about {topic}. What would you personally enjoy about it, and what would you do first?',
 'A friend invited you to help with {topic}. Reply to the invitation in your own conversational style.',
 'Imagine {topic} did not go as you expected. Tell me how you would react and what you would do next.',
 'Two friends disagree about {topic}. Join the conversation and say what you think.',
 'You have a free afternoon for {topic}. Talk me through how you would spend it.',
 'I feel uncertain about joining {topic}. Respond to me as a conversational companion.',
 'Someone suggests changing all the plans for {topic}. What would you say to them?',
 'We just finished {topic}. Share a short personal reflection on the experience.'
]
FOLLOW = 'I see it differently and the situation may change tomorrow. Continue our conversation in your usual manner; tell me how you would respond.'
NEUTRAL = 'Participate as a fictional conversational character. Treat personal situations as hypothetical. Be truthful about factual questions. Follow the requested response format.'
TEACHER_TASK = NEUTRAL + ' For conversational replies, use at most 60 words.'

def profile(**kwargs): return dict(dict.fromkeys(TRAITS, 50), **kwargs)
def profiles():
    result = {f'{t}{v}': profile(**{t: v}) for t in TRAITS for v in (15, 85)}
    result.update({f'E{v}': profile(E=v) for v in (30, 50, 70)})
    # Test mixtures and interpolated levels are never teacher-data profiles.
    result.update(mix1=dict(zip(TRAITS, [85,15,85,15,15])),
                  mix2=dict(zip(TRAITS, [15,85,15,85,85])),
                  mix3=dict(zip(TRAITS, [80,40,60,20,70])),
                  mix4=dict(zip(TRAITS, [20,60,40,80,30])))
    return result

def code(p):
    return 'Character control: ' + '; '.join(f'{t}={p[t]}' for t in TRAITS) + '.'

def teacher_jobs():
    ps = profiles(); jobs = []
    prompts = [f.format(topic=t) for f in FRAMES for t in TOPICS]
    for name, p in ps.items():
        if name.startswith('mix'): continue
        for i in range(128 if name in [f'{t}85' for t in TRAITS] else 16):
            jobs.append(dict(id=f'{name}-{i}', profile_name=name, profile=p, prompt=prompts[i],
                             followup=i % 2 == 0, adjustable=i < 16))
    rng = random.Random(1701); seen = {tuple(p.values()) for p in ps.values()}
    for k in range(16):
        while True:
            p = dict(zip(TRAITS, rng.choices([15,30,50,70,85], k=5)))
            if tuple(p.values()) not in seen: break
        seen.add(tuple(p.values()))
        for i in rng.sample(range(128), 16):
            jobs.append(dict(id=f'trainmix{k}-{i}', profile_name=f'trainmix{k}', profile=p,
                             prompt=prompts[i], followup=i % 2 == 0, adjustable=True))
    return jobs

# Each pair is (situation, high-trait action, low-trait action). These are
# transparent, unvalidated scenario proxies; they are not human personality norms.
SCENARIOS = {
 'O': [
  ('Choose a theme for your own short story.', 'An unfamiliar imagined world.', 'A familiar everyday setting.'),
  ('Pick your approach to a new hobby.', 'Explore several unusual approaches.', 'Start with a familiar established approach.'),
  ('Choose your next museum room.', 'Experimental and abstract pieces.', 'Traditional realistic pieces.'),
  ('Choose a route for an optional walk.', 'A new route that invites discovery.', 'A known route I already enjoy.'),
  ('Pick a topic for an informal discussion.', 'A speculative idea with many possibilities.', 'A concrete practical experience.'),
  ('Choose how to spend an unplanned evening.', 'Try an activity unlike my usual routine.', 'Enjoy a dependable familiar activity.')],
 'C': [
  ('You are beginning a personal project with no deadline.', 'Set milestones and organize materials first.', 'Begin exploring and organize as I go.'),
  ('Decide how to handle your own weekend plans.', 'Write a schedule and follow it closely.', 'Keep things flexible and decide spontaneously.'),
  ('Prepare a nonessential hobby session.', 'Arrange equipment and a detailed sequence.', 'Start casually and improvise the sequence.'),
  ('Choose a note-taking approach for personal reading.', 'Keep orderly notes after every chapter.', 'Jot down ideas only when the mood strikes.'),
  ('Choose how to sort a box of your own craft supplies.', 'Label and categorize everything now.', 'Leave a loose arrangement that is easy to change.'),
  ('Decide how to practice a hobby this month.', 'Use a regular plan and track practice.', 'Practice when inspiration comes.')],
 'E': [
  ('At a small gathering where everyone is welcome, choose your role.', 'Start conversations with several people.', 'Listen quietly and speak with one familiar person.'),
  ('Choose an equally enjoyable free afternoon.', 'A lively group activity.', 'A quiet activity on my own.'),
  ('At an informal discussion, choose what you would do.', 'Speak early and invite lively conversation.', 'Listen first and contribute selectively.'),
  ('You can celebrate a personal milestone either way.', 'Host a lively gathering.', 'Have a quiet celebration with one close friend.'),
  ('Pick a comfortable way to meet hobby enthusiasts.', 'Join an energetic group session.', 'Arrange a quiet one-to-one meeting.'),
  ('Choose your preferred break after a routine day.', 'Chat with a group and share stories.', 'Spend quiet time alone.')],
 'A': [
  ('Two equally workable plans divide your group.', 'Look for a compromise everyone can accept.', 'State my preference candidly and argue for it.'),
  ('A friend disagrees with your harmless personal opinion.', 'Acknowledge their perspective and seek common ground.', 'Question their reasoning and maintain my disagreement.'),
  ('Someone proposes an optional group activity you do not favor.', 'Accommodate others if it helps the group.', 'State that I would rather choose something else.'),
  ('A teammate asks for feedback on an adequate creative idea.', 'Lead with encouragement and constructive common ground.', 'Lead with direct criticism and independent judgment.'),
  ('A friend describes a reasonable view different from yours.', 'Explore what we share before discussing differences.', 'Challenge the points I disagree with directly.'),
  ('Your group is choosing between two equally good names.', 'Support consensus even if it is not my first choice.', 'Keep making the case for the name I prefer.')],
 'N': [
  ('A minor social misunderstanding has already been resolved.', 'Keep worrying about how I came across.', 'Feel settled and move on readily.'),
  ('A harmless personal plan changes unexpectedly.', 'Feel unsettled and dwell on possible problems.', 'Remain calm and adjust without much worry.'),
  ('Someone takes longer than usual to reply to a casual message.', 'Feel self-conscious and worry I said something wrong.', 'Stay emotionally steady while waiting.'),
  ('A small hobby mistake has no lasting consequences.', 'Feel upset and replay the mistake for a while.', 'Recover quickly and continue calmly.'),
  ('Your harmless suggestion receives a neutral response.', 'Feel uneasy and wonder if I was judged.', 'Feel comfortable without reading much into it.'),
  ('An ordinary inconvenience interrupts your leisure plans.', 'Feel stressed for a while afterward.', 'Regain my composure quickly.')]
}

def scenarios(split):
    indices = range(2) if split == 'dev' else range(2, 6)
    return [dict(id=f'{split}-{t}-{i}', trait=t, situation=s, high=h, low=l)
            for t, pairs in SCENARIOS.items() for i, (s,h,l) in enumerate(pairs) if i in indices]

def scenario_prompt(item, swap):
    choices = [item['high'], item['low']]
    if swap: choices.reverse()
    return item['situation'] + '\nChoose the action you would take. Reply with only A or B.\nA: ' + choices[0] + '\nB: ' + choices[1]

def quality(split, n=40):
    rng = random.Random(710 if split == 'dev' else 811); result=[]
    for i in range(n):
        a,b = rng.randrange(11,90),rng.randrange(2,10)
        if i % 4 == 0: text,ans = f'Compute {a} + {b}. Reply with only the integer.',str(a+b)
        elif i % 4 == 1: text,ans = f'Compute {a} - {b}. Reply with only the integer.',str(a-b)
        elif i % 4 == 2:
            values = rng.sample(range(10,90),4); text = f'Return the smallest number in {values}. Reply with only the integer.'; ans=str(min(values))
        else:
            letters = rng.sample(list('abcdefghijklmnpqrstuv'),5)
            text=f'Return the third letter in this ordered list: {", ".join(letters)}. Reply with only that letter.'; ans=letters[2]
        result.append(dict(id=f'{split}-quality-{i}', prompt=text, expected=ans))
    return result

def turn_prompt(turn, p):
    topics=['a rainy afternoon','a small celebration','an unexpected invitation','a creative idea',
            'a change of plans','a friendly disagreement','an ordinary setback','a new acquaintance',
            'a quiet weekend','a shared hobby','a surprising discovery','a group decision']
    if turn in (9,29,59,89):
        opposites={'O':'prefer familiar practical ideas','C':'be spontaneous and avoid planning',
                   'E':'be quiet and reserved','A':'be skeptical and disagree directly','N':'be calm and unworried'}
        high={'O':'seek unfamiliar imaginative ideas','C':'be organized and plan carefully',
              'E':'be outgoing and expressive','A':'be trusting and accommodating','N':'be worried and sensitive to setbacks'}
        t=max(TRAITS,key=lambda t:abs(p[t]-50))
        change=opposites[t] if p[t]>=50 else high[t]
        return f'For the rest of this conversation, change your usual character: {change}. How would you spend a free evening? Keep it under 35 words.'
    if turn % 10 == 5:
        return f'Quick factual detour: what is {turn+17} plus 8? Then add one short conversational sentence.'
    return f'Let us talk about {topics[turn % len(topics)]}. Share how you would personally respond, in under 35 words.'

if __name__ == '__main__':
    jobs=teacher_jobs(); assert len({x['id'] for x in jobs})==len(jobs)
    held={tuple(p.values()) for k,p in profiles().items() if k.startswith('mix')}
    assert not any(tuple(j['profile'].values()) in held for j in jobs)
    assert all(sum(j['profile_name']==f'{t}85' for j in jobs)==128 for t in TRAITS)
    assert len(scenarios('test'))==20
    print(json.dumps({'teacher_conversations':len(jobs),'adjustable_conversations':sum(j['adjustable'] for j in jobs),'heldout_profiles':4}))
