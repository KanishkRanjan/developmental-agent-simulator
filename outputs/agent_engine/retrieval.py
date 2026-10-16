"""Private available-representation index; standard library, no new model.

LLM query expansion searches the entire private corpus before the bounded
rerank. This is an FTS5/BM25 index, not an embedding model or exhaustive recall.
"""
import re
import sqlite3


def candidates(engine, owner, situation, *, api, model, limit):
    from engine import validated_json
    from cognition import views
    available = views(engine,owner,'',len(engine.agent(owner)['memory_meta']))
    if not available: return [], []
    context=engine.context(owner,situation)
    context.update(task='expand_retrieval_query')
    def validate(result):
        terms=result.get('queries')
        if not isinstance(terms,list) or not 1<=len(terms)<=4 or not all(isinstance(t,str) and 0<len(t)<=150 for t in terms):
            raise ValueError('Return one to four short search paraphrases in queries')
    result=validated_json('Return JSON queries, one to four short paraphrases or related concepts for finding '
        'personally relevant past experiences for this situation. Include synonyms and analogous situations. '
        'Do not invent incidents or names; these are search terms, not memory claims.',context,validate,api,model,250)
    # ponytail: rebuild the private view index per cognitive event. This avoids
    # stale availability/privacy caches; persist incremental indices after profiling.
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE VIRTUAL TABLE episodes USING fts5(event UNINDEXED, content, tokenize="porter unicode61")')
        db.executemany('INSERT INTO episodes(event,content) VALUES (?,?)',[
            (m['event'],m['text']+' '+m['meaning']+' '+' '.join(m['topics'])) for m in available])
        ranked={}
        for query in [situation,*result['queries']]:
            tokens=list(dict.fromkeys(re.findall(r'\w+',query.lower())))[:30]
            if not tokens: continue
            expression=' OR '.join('"'+token+'"' for token in tokens)
            for rank,(event,) in enumerate(db.execute('SELECT event FROM episodes WHERE episodes MATCH ? ORDER BY bm25(episodes), event LIMIT ?', (expression,limit))):
                ranked[event]=ranked.get(event,0)+1/(rank+1)
    by_id={m['event']:m for m in available}
    matches=sorted(ranked,key=lambda mid:(-ranked[mid],-by_id[mid]['day'],mid))
    # Preserve a small salience/recency reserve without displacing distant matches.
    reserve=min(3,max(0,limit//4)); ids=matches[:limit-reserve]
    recent=sorted(available,key=lambda m:(m['day'],m['event']),reverse=True)
    for memory in [*recent[:reserve],*available]:
        if len(ids)>=limit: break
        if memory['event'] not in ids: ids.append(memory['event'])
    return [by_id[mid] for mid in ids], result['queries']
