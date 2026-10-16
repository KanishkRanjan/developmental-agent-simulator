"""Deterministic bounded model view; original state and records are untouched."""
import json


def compact(context, max_bytes=16000):
    """Trim optional history before essential current instructions and actions.

    A byte bound is a view-size policy, not a token estimate. The local
    transport separately checks the server's actual rendered prompt tokens.
    """
    context.setdefault('context_view', {'policy':'bounded_view_v1', 'omitted':{}, 'original_records_preserved':True})
    omitted = context['context_view']['omitted']
    def too_large():
        return len(json.dumps(context, allow_nan=False).encode()) > max_bytes
    for field, minimum in [('memories',2), ('beliefs',0), ('heard_about',0), ('unresolved_references',0), ('relationships',0), ('pending_questions',0), ('goals',1), ('memories',0)]:
        values = context.get(field, [])
        while too_large() and len(values) > minimum:
            if isinstance(values,list):
                values.pop()  # Retrieval already ordered by relevance.
            else:
                if field == 'goals':
                    key = min(values,key=lambda k:(values[k].get('status')=='active', values[k].get('priority',0), k))
                elif field == 'relationships':
                    key = min(values,key=lambda k:(k.lower() in context.get('situation','').lower(),
                                                   values[k].get('role') in ('parent','mother','father','caregiver'),k))
                else:
                    key = next(iter(values))  # Keep the newest committed entries.
                del values[key]
            omitted[field] = omitted.get(field,0) + 1
    if too_large():
        raise ValueError('Essential current context exceeds the model-view byte budget; shorten the current input')
    return context
