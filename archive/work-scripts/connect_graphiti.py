from pathlib import Path
p=Path('outputs/agent_engine/cognition.py');s=p.read_text().replace("'reference_resolution', 'autonomous_goals'}", "'reference_resolution', 'autonomous_goals', 'graphiti_retrieval'}").replace("'reference_resolution', 'autonomous_goals'):", "'reference_resolution', 'autonomous_goals', 'graphiti_retrieval'):")
s=s.replace("engine.state['config']['cognition'] = deepcopy(settings)", "engine.state['config']['cognition'] = deepcopy(settings)\n    if settings.get('graphiti_retrieval'):\n        from uuid import uuid4\n        engine.state['config'].setdefault('graphiti_namespace',uuid4().hex)")
s=s.replace("queries = []\n    if settings.get('indexed_retrieval',False):", """queries = []
    graph_info = None
    candidates = None
    if settings.get('graphiti_retrieval',False):
        try:
            from graphiti_bridge import candidates as graph_candidates
            candidates, graph_info = graph_candidates(engine,owner,situation,settings.get('semantic_candidates',24))
        except (OSError,ValueError,RuntimeError,TimeoutError) as exc:
            # A graph outage never grants access to broader data. The existing
            # private FTS path remains usable and the downgrade is recorded.
            graph_info={'backend':'graphiti','status':'fallback_private_fts','error':str(exc)[:400]}
    if candidates is None and settings.get('indexed_retrieval',False):""")
s=s.replace("    else:\n        candidates = views(engine, owner, '', settings.get('semantic_candidates',24))", "    elif candidates is None:\n        candidates = views(engine, owner, '', settings.get('semantic_candidates',24))")
s=s.replace("'indexed_corpus':bool(settings.get('indexed_retrieval',False))}", "'indexed_corpus':bool(settings.get('indexed_retrieval',False)),\n        **({'graph_retrieval':graph_info} if graph_info is not None else {})}")
p.write_text(s)
p=Path('outputs/agent_engine/engine.py');s=p.read_text()
s=s.replace("return save(path,self.state)", "result=save(path,self.state)\n            self._publish_graph_view()\n            return result")
s=s.replace("temporary.replace(path)\n\n    @classmethod", "temporary.replace(path)\n        self._publish_graph_view()\n\n    def _publish_graph_view(self):\n        if self.state['config'].get('cognition',{}).get('graphiti_retrieval'):\n            try:\n                from graphiti_bridge import publish\n                publish(self)\n            except (OSError,ValueError,RuntimeError) as exc:\n                import warnings\n                warnings.warn('Checkpoint saved; graph outbox publication deferred: '+str(exc),RuntimeWarning)\n\n    @classmethod")
p.write_text(s)
