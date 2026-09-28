#!/usr/bin/env python3
"""
python src/eval/run_eval.py --system mem0      --output results/mine/mem0.json
python src/eval/run_eval.py --system full_context naive_rag latest_value --output results/mine/refs.json
python src/eval/run_eval.py --adapter my_adapter.py:MyAdapter --name mysys --output results/mine/mysys.json
python src/eval/run_eval.py --system recency --dry-run --limit 2 --output /tmp/t.json     # no API key
"""
from __future__ import annotations
import argparse, asyncio, gc, importlib, importlib.util, json, logging, os, re, shutil, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  
P.add_src_to_path()
from llm import call_llm, set_llm_backend  
import protocol as PR 

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_eval")
for n in ("httpx", "google", "openai", "chromadb", "mem0", "langchain", "langmem", "graphiti_core", "kuzu", "neo4j",
          "cognee", "litellm", "LiteLLM", "sentence_transformers", "transformers", "torch", "faiss", "sqlalchemy", "lancedb"):
    logging.getLogger(n).setLevel(logging.ERROR)

READER_MODEL = "gemini-3-flash-preview"
INTERNAL_LLM = "gemini-2.5-flash"
GEMINI_EMBED = "models/gemini-embedding-001"
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
REFERENCE = {"judge", "full_context", "naive_rag", "time_aware_rag", "oracle_rag", "latest_value", "always_update", "always_preserve"}


def need_gemini_key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        raise SystemExit("Set the GEMINI_API_KEY environment variable")
    os.environ.setdefault("GOOGLE_API_KEY", k)
    return k


def fmt_session(session: Dict) -> str:
    return "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
                     for m in session.get("dialogue", []) if m.get("role") in ("user", "assistant"))


def messages(session: Dict) -> List[Dict]:
    return [{"role": m["role"], "content": m["content"]} for m in session.get("dialogue", []) if m.get("role") in ("user", "assistant")]


class MemorySystemAdapter:
    context_header = "Memory retrieved from the conversation history:"
    answer = None  # type: ignore[assignment]  # define answer(self, probe) -> str for end-to-end systems

    def __init__(self, work_dir: str = "/tmp/memprobe_run", **kw): self.work_dir = work_dir
    def reset(self, episode_id: str, episode: Optional[Dict] = None, spec: Optional[Dict] = None) -> None: raise NotImplementedError
    def ingest(self, session: Dict) -> None: raise NotImplementedError
    def retrieve(self, question: str) -> str: raise NotImplementedError
    def stored_memories(self) -> List: return []
    def close(self) -> None: pass


class RecencyBufferAdapter(MemorySystemAdapter):
    def __init__(self, k: int = 5, **kw): super().__init__(**kw); self.k = k; self.buf: List[str] = []
    def reset(self, eid, episode=None, spec=None): self.buf = []
    def ingest(self, s): self.buf = (self.buf + [fmt_session(s)])[-self.k:]
    def retrieve(self, q): return "\n\n---\n\n".join(f"[Session {i+1} of {len(self.buf)} (most recent last)]\n{s}" for i, s in enumerate(self.buf))
    def stored_memories(self): return list(self.buf)


class Mem0Adapter(MemorySystemAdapter):
    context_header = "Memory facts extracted from conversation history:"
    def __init__(self, **kw):
        super().__init__(**kw); need_gemini_key()
        from mem0 import Memory; self._Memory = Memory
    def reset(self, eid, episode=None, spec=None):
        self.eid = eid; d = os.path.join(self.work_dir, "chroma", eid); shutil.rmtree(d, ignore_errors=True)
        self.m = self._Memory.from_config({
            "llm": {"provider": "gemini", "config": {"model": INTERNAL_LLM}},
            "embedder": {"provider": "gemini", "config": {"model": GEMINI_EMBED, "embedding_dims": 768}},
            "vector_store": {"provider": "chroma", "config": {"collection_name": f"mp_{eid.replace('-', '_').lower()}", "path": d}}})
        self.mems: List = []
    def ingest(self, s):
        msgs = messages(s)
        if msgs: self.m.add(msgs, user_id=self.eid)
    def _all(self):
        r = self.m.get_all(filters={"user_id": self.eid}); return r.get("results", []) if isinstance(r, dict) else r
    def retrieve(self, q):
        self.mems = self._all(); return "\n".join(f"- {x.get('memory', '')}" for x in self.mems)
    def stored_memories(self): return [x.get("memory", "") for x in self.mems]
    def close(self):
        try: self.m.close()
        except Exception: pass
        del self.m; gc.collect()


class LangMemAdapter(MemorySystemAdapter):
    context_header = "Memory facts extracted from conversation history:"
    def __init__(self, **kw):
        super().__init__(**kw); need_gemini_key()
        import typing, typing_extensions
        for n in ("NotRequired", "Required"):
            if not hasattr(typing, n): setattr(typing, n, getattr(typing_extensions, n))
        from langchain_google_genai import ChatGoogleGenerativeAI; from langmem import create_memory_manager
        llm = ChatGoogleGenerativeAI(model=INTERNAL_LLM, temperature=0.0, google_api_key=os.environ["GEMINI_API_KEY"])
        self.manager = create_memory_manager(llm, enable_inserts=True, enable_updates=True, enable_deletes=True)
    def reset(self, eid, episode=None, spec=None): self.existing = []
    def ingest(self, s):
        msgs = messages(s)
        if msgs:
            ex = self.manager.invoke({"messages": msgs, "existing": self.existing}); self.existing = [(m.id, m.content) for m in ex]
    def _texts(self): return [str(c.content) if hasattr(c, "content") else str(c) for _, c in self.existing]
    def retrieve(self, q): return "\n".join(f"- {t}" for t in self._texts() if t)
    def stored_memories(self): return self._texts()


class GraphitiAdapter(MemorySystemAdapter):
    context_header = "Memory facts retrieved from the knowledge graph:"
    def __init__(self, **kw):
        super().__init__(**kw); need_gemini_key()
        from graphiti_core import Graphiti; from graphiti_core.driver.kuzu_driver import KuzuDriver
        from graphiti_core.llm_client.gemini_client import GeminiClient
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
        from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
        from graphiti_core.llm_client.config import LLMConfig; from graphiti_core.nodes import EpisodeType
        self._g = (Graphiti, KuzuDriver, GeminiClient, GeminiEmbedder, GeminiEmbedderConfig, GeminiRerankerClient, LLMConfig, EpisodeType)
        self.loop = asyncio.new_event_loop()
    def _run(self, coro): return self.loop.run_until_complete(coro)
    def reset(self, eid, episode=None, spec=None):
        Graphiti, KuzuDriver, GeminiClient, GeminiEmbedder, GeminiEmbedderConfig, GeminiRerankerClient, LLMConfig, _ = self._g
        self.eid = eid; self.i = 0; self.base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        os.makedirs(os.path.join(self.work_dir, "kuzu"), exist_ok=True); self.db = os.path.join(self.work_dir, "kuzu", f"{eid}.kuzu")
        self._rm_db()
        K = os.environ["GEMINI_API_KEY"]
        driver = KuzuDriver(db=self.db); driver._database = ""
        self.g = Graphiti(graph_driver=driver, llm_client=GeminiClient(config=LLMConfig(api_key=K, model=INTERNAL_LLM, temperature=0.0)),
                          embedder=GeminiEmbedder(config=GeminiEmbedderConfig(api_key=K, embedding_model=GEMINI_EMBED, embedding_dim=768)),
                          cross_encoder=GeminiRerankerClient(config=LLMConfig(api_key=K, model=INTERNAL_LLM)))
        async def _init():
            try:
                await driver.client.execute("INSTALL FTS;"); await driver.client.execute("LOAD EXTENSION FTS;")
            except Exception as e: log.warning(f"FTS extension: {e}")
            await self.g.driver._graph_ops.build_indices_and_constraints(self.g.driver, delete_existing=False)
        self._run(_init())
    def _rm_db(self):
        for p in [self.db] + [self.db + e for e in (".wal", ".tmp", ".lock")]:
            if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p): os.remove(p)
    def ingest(self, s):
        body = fmt_session(s)
        if not body.strip(): return
        EpisodeType = self._g[-1]
        self._run(self.g.add_episode(name=f"{self.eid}_s{self.i}", episode_body=body, source=EpisodeType.message,
                                     source_description=s.get("session_type", "session"),
                                     reference_time=self.base + timedelta(hours=self.i), group_id=self.eid))
        self.i += 1
    def retrieve(self, q):
        edges = self._run(self.g.search(query=q, group_ids=[self.eid], num_results=15)); return "\n".join(f"- {e.fact}" for e in edges)
    def close(self):
        try: self._run(self.g.close())
        except Exception: pass
        self._rm_db()


class CogneeAdapter(MemorySystemAdapter):
    context_header = "Memory facts retrieved from the knowledge graph:"
    def __init__(self, **kw):
        super().__init__(**kw); K = need_gemini_key(); os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"
        import cognee; from cognee import SearchType
        cognee.config.set_llm_provider("gemini"); cognee.config.set_llm_model(f"gemini/{INTERNAL_LLM}"); cognee.config.set_llm_api_key(K)
        cognee.config.set_embedding_provider("gemini"); cognee.config.set_embedding_model("gemini/gemini-embedding-001"); cognee.config.set_embedding_api_key(K)
        self.cognee, self.SearchType = cognee, SearchType; self.loop = asyncio.new_event_loop()
    def _run(self, coro): return self.loop.run_until_complete(coro)
    def reset(self, eid, episode=None, spec=None):
        self.ds = f"mp_{eid.replace('-', '_').lower()}"
        async def _prune():
            await self.cognee.prune.prune_data(); await self.cognee.prune.prune_system(metadata=True)
        try: self._run(_prune())
        except Exception as e: log.warning(f"prune: {e}")
    def ingest(self, s):
        body = fmt_session(s)
        if not body.strip(): return
        async def _add():
            await self.cognee.add(body, dataset_name=self.ds); await self.cognee.cognify(datasets=[self.ds])
        self._run(_add())
    def retrieve(self, q):
        res = self._run(self.cognee.search(query_text=q, query_type=self.SearchType.GRAPH_COMPLETION, datasets=[self.ds], only_context=True, top_k=15))
        if isinstance(res, str): return res
        if isinstance(res, list) and res:
            r0 = res[0]
            if isinstance(r0, dict) and "search_result" in r0:
                sr = r0["search_result"]; return sr if isinstance(sr, str) else "\n".join(str(x) for x in sr)
            return "\n".join(str(x) for x in res)
        return str(res) if res else ""


class AMemAdapter(MemorySystemAdapter):
    context_header = "Memory notes retrieved from A-MEM (with evolved links / tags):"
    def __init__(self, amem_repo: str = "/tmp/A-mem", **kw):
        super().__init__(**kw); need_gemini_key()
        for k, v in (("HF_HOME", "/tmp/hf_cache"), ("SENTENCE_TRANSFORMERS_HOME", "/tmp/hf_cache/st"), ("TRANSFORMERS_CACHE", "/tmp/hf_cache/transformers")):
            os.environ.setdefault(k, v)
        sys.path.insert(0, amem_repo)
        from memory_layer import AgenticMemorySystem, LiteLLMController; from litellm import completion
        class GeminiLiteLLMController(LiteLLMController):
            def get_completion(self, prompt, response_format=None, temperature=0.7):
                try:
                    r = completion(model=self.model, api_key=self.api_key, temperature=temperature, response_format={"type": "json_object"},
                                   messages=[{"role": "system", "content": "You must respond with a JSON object."}, {"role": "user", "content": prompt}])
                    return r.choices[0].message.content
                except Exception as e:
                    log.warning(f"gemini completion error: {e}"); return self._generate_empty_response(response_format or {})
        self._AMS, self._Ctl = AgenticMemorySystem, GeminiLiteLLMController
    def reset(self, eid, episode=None, spec=None):
        self.amem = self._AMS(model_name="all-MiniLM-L6-v2", llm_backend="openai", llm_model="gpt-4o-mini", api_key="dummy-not-used", evo_threshold=100)
        self.amem.llm_controller.llm = self._Ctl(model=f"gemini/{INTERNAL_LLM}", api_key=os.environ["GEMINI_API_KEY"]); self.i = 0
    def ingest(self, s):
        body = fmt_session(s)
        if body.strip():
            self.amem.add_note(content=body, time=f"202601{1+self.i:02d}0001"[:12], tags=[s.get("session_type", "session")], category=s.get("session_type", "session"))
        self.i += 1
    def retrieve(self, q): ctx, _ = self.amem.find_related_memories(q, k=15); return ctx
    def stored_memories(self):
        return [{"content": m.content, "context": m.context, "keywords": list(m.keywords), "tags": list(m.tags), "links": list(m.links)} for m in self.amem.memories.values()]
    def close(self): del self.amem; gc.collect()


class MemoryOSAdapter(MemorySystemAdapter):
    context_header = "Memory retrieved from MemoryOS (mid-term pages + long-term knowledge):"
    def __init__(self, memoryos_repo: str = "/tmp/MemoryOS/memoryos-pypi", **kw):
        super().__init__(**kw); need_gemini_key()
        for k, v in (("HF_HOME", "/tmp/hf_cache"), ("SENTENCE_TRANSFORMERS_HOME", "/tmp/hf_cache/st"), ("TRANSFORMERS_CACHE", "/tmp/hf_cache/transformers")):
            os.environ.setdefault(k, v)
        sys.path.insert(0, memoryos_repo)
        from memoryos import Memoryos; import utils as mu
        def _patched_chat(self_, model, msgs, temperature=0.7, max_tokens=2000):
            try:
                r = self_.client.chat.completions.create(model=model, messages=msgs, temperature=temperature, max_tokens=max_tokens, reasoning_effort="none")
                raw = r.choices[0].message.content
                if raw is None: return ""
                try: return mu.clean_reasoning_model_output(raw.strip())
                except Exception: return raw.strip()
            except Exception as e:
                log.warning(f"memoryos chat err: {e}"); return ""
        mu.OpenAIClient.chat_completion = _patched_chat; self._Memoryos = Memoryos
    def reset(self, eid, episode=None, spec=None):
        self.ds = os.path.join(self.work_dir, "memoryos", eid); shutil.rmtree(self.ds, ignore_errors=True); os.makedirs(self.ds, exist_ok=True)
        u = eid.replace("-", "_").lower()
        self.memo = self._Memoryos(user_id=f"u_{u}", assistant_id=f"a_{u}", openai_api_key=os.environ["GEMINI_API_KEY"], openai_base_url=GEMINI_OPENAI_BASE,
                                   llm_model=INTERNAL_LLM, embedding_model_name="all-MiniLM-L6-v2", data_storage_path=self.ds,
                                   short_term_capacity=7, mid_term_heat_threshold=5.0)
    @staticmethod
    def turn_pairs(session):
        pairs, cu, ca, state = [], [], [], None
        for m in session.get("dialogue", []):
            r = m.get("role")
            if r == "user":
                if state == "assistant": pairs.append(("\n".join(cu).strip(), "\n".join(ca).strip())); cu, ca = [], []
                cu.append(m.get("content", "")); state = "user"
            elif r == "assistant": ca.append(m.get("content", "")); state = "assistant"
            elif r == "tool_output": ca.append(f"[tool] {m.get('content', '')}")
        if cu or ca: pairs.append(("\n".join(cu).strip(), "\n".join(ca).strip()))
        return [(u, a) for u, a in pairs if u or a]
    def ingest(self, s):
        for u, a in self.turn_pairs(s): self.memo.add_memory(user_input=u or "(no user text)", agent_response=a or "(no assistant text)")
    def retrieve(self, q):
        rc = self.memo.retriever.retrieve_context(user_query=q, user_id=self.memo.user_id); parts = []
        for p in rc.get("retrieved_pages", []):
            parts.append(f"- [mid-term] {(p.get('page_content') or p.get('content') or json.dumps(p, ensure_ascii=False)) if isinstance(p, dict) else p}")
        for k in rc.get("retrieved_user_knowledge", []): parts.append(f"- [user-knowledge] {k.get('knowledge') if isinstance(k, dict) else k}")
        for k in rc.get("retrieved_assistant_knowledge", []): parts.append(f"- [assistant-knowledge] {k.get('knowledge') if isinstance(k, dict) else k}")
        return "\n".join(parts)
    def close(self): del self.memo; gc.collect(); shutil.rmtree(self.ds, ignore_errors=True)


class _ReferenceAdapter(MemorySystemAdapter):
    def __init__(self, model: str = READER_MODEL, **kw): super().__init__(**kw); self.model = model
    def reset(self, eid, episode=None, spec=None): self.ep, self.spec = episode, spec or {}
    def ingest(self, s): pass
    def retrieve(self, q): raise RuntimeError("reference baselines answer directly")


class FullContextAdapter(_ReferenceAdapter):
    def answer(self, probe): return PR.run_full_context(self.ep, probe, self.model)


class NaiveRAGAdapter(_ReferenceAdapter):
    def answer(self, probe):
        pred, idx = PR.run_naive_rag(self.ep, probe, self.spec, self.model); self.last_indices = idx; return pred


class JudgeAdapter(_ReferenceAdapter):
    def reset(self, eid, episode=None, spec=None):
        super().reset(eid, episode, spec); self.k = 0
        try: self.j = PR.run_llm_judge(episode, self.model).get("answers", [])
        except Exception as e: log.warning(f"judge call failed: {e}"); self.j = []
    def answer(self, probe):
        a = self.j[self.k] if self.k < len(self.j) else {}; self.k += 1; return a.get("answer", "")


class _HeuristicAdapter(_ReferenceAdapter):
    fn = None
    def reset(self, eid, episode=None, spec=None): super().reset(eid, episode, spec); self.h = type(self).fn(episode, spec or {})
    def answer(self, probe): return str(self.h.get(probe["probe_type"], ""))


class LatestValueAdapter(_HeuristicAdapter): fn = staticmethod(PR.run_latest_value)
class AlwaysUpdateAdapter(_HeuristicAdapter): fn = staticmethod(PR.run_always_update)
class AlwaysPreserveAdapter(_HeuristicAdapter): fn = staticmethod(PR.run_always_preserve)


_STOP = {"the", "a", "an", "is", "was", "did", "does", "do", "at", "to", "of", "in", "for", "and", "or", "it", "its", "any", "what", "who",
         "how", "their", "they", "this", "that", "has", "have", "been", "ever", "point"}
ORACLE_TYPES = {"encoding", "perturbation", "perturbation_p1", "perturbation_p2"}


def _with_true_idx(sessions_with_idx, total):
    parts = []
    for i, s in sessions_with_idx:
        parts.append(f"--- Session {i+1} of {total} ({s.get('session_type', 'session')}) ---")
        parts += [f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}" for m in s.get("dialogue", [])]; parts.append("")
    return "\n".join(parts)


class TimeAwareRAGAdapter(_ReferenceAdapter):
    def answer(self, probe, top_k=5):
        kws = []
        for v in [self.spec.get("canonical_initial", ""), self.spec.get("canonical_new", "")] + self.spec.get("distractor_values", []): kws += v.split()
        kws += self.spec.get("fact_type", "").replace("_", " ").split()
        kws += [w for w in (re.sub(r"[^\w]", "", x.lower()) for x in probe["question"].split()) if w and w not in _STOP and len(w) > 2]
        kws = list(set(kws)); S = self.ep["sessions"]
        scored = sorted(((PR.keyword_relevance(" ".join(m.get("content", "") for m in s.get("dialogue", [])), kws), i, s) for i, s in enumerate(S)), key=lambda x: -x[0])[:top_k]
        top = sorted(scored, key=lambda x: x[1]); self.last_indices = [i for _, i, _ in top]
        prompt = (f"Retrieved conversation sessions (subset of {len(S)} total, labelled with their original position in the timeline):\n\n"
                  f"{_with_true_idx([(i, s) for _, i, s in top], len(S))}\n\nQuestion: {probe['question']}\n\n{PR._PROBE_SCHEMAS.get(probe['probe_type'], '')}")
        return call_llm(PR.RAG_SYSTEM, prompt, model=self.model, temperature=0.0, max_tokens=4096)


class OracleRAGAdapter(_ReferenceAdapter):
    def answer(self, probe):
        S = self.ep["sessions"]; sel = [(i, s) for i, s in enumerate(S) if s.get("session_type") in ORACLE_TYPES]; self.last_indices = [i for i, _ in sel]
        prompt = (f"Oracle-selected evidence sessions (all non-filler sessions, labelled with their original position in the {len(S)}-session timeline):\n\n"
                  f"{_with_true_idx(sel, len(S))}\n\nQuestion: {probe['question']}\n\n{PR._PROBE_SCHEMAS.get(probe['probe_type'], '')}")
        return call_llm(PR.RAG_SYSTEM, prompt, model=self.model, temperature=0.0, max_tokens=4096)


SYSTEMS = {"mem0": Mem0Adapter, "langmem": LangMemAdapter, "graphiti": GraphitiAdapter, "cognee": CogneeAdapter, "amem": AMemAdapter,
           "memoryos": MemoryOSAdapter, "recency": RecencyBufferAdapter, "judge": JudgeAdapter, "full_context": FullContextAdapter,
           "naive_rag": NaiveRAGAdapter, "time_aware_rag": TimeAwareRAGAdapter, "oracle_rag": OracleRAGAdapter,
           "latest_value": LatestValueAdapter, "always_update": AlwaysUpdateAdapter, "always_preserve": AlwaysPreserveAdapter}


def load_user_adapter(spec: str, **kw) -> MemorySystemAdapter:
    mod_part, _, cls = spec.rpartition(":")
    if not cls: raise SystemExit("--adapter must be module_or_file:ClassName")
    if mod_part.endswith(".py") or os.sep in mod_part:
        sp = importlib.util.spec_from_file_location("user_adapter", mod_part); mod = importlib.util.module_from_spec(sp); sp.loader.exec_module(mod)  # type: ignore[union-attr]
    else:
        sys.path.insert(0, os.getcwd()); mod = importlib.import_module(mod_part)
    try: return getattr(mod, cls)(**kw)
    except TypeError: return getattr(mod, cls)()


def evaluate(name: str, adapter: MemorySystemAdapter, key: str, episodes: List[Dict], spec_map: Dict, args, results: Dict, out: Path):
    end_to_end = callable(getattr(adapter, "answer", None))
    cache_path = str(out.with_name(f"{out.stem}_{key}_prompts.json"))
    results.setdefault(key, {}); results.setdefault("stored_memories", {})
    results.setdefault("meta", {})[key] = {"system": name, "adapter": type(adapter).__name__, "mode": "end_to_end" if end_to_end else "retrieval+unified_reader",
                                           "reader": None if end_to_end and name in ("latest_value", "always_update", "always_preserve") else (args.reader_model or READER_MODEL),
                                           "internal_llm": INTERNAL_LLM if name in ("mem0", "langmem", "graphiti", "cognee", "amem", "memoryos") else None,
                                           "episodes": args.episodes}
    done = set(results[key])
    print(f"\n=== {name} -> key '{key}'  ({len(episodes)} episodes, {len(done)} done, {'end-to-end' if end_to_end else 'retrieval + reader'}) ===", flush=True)
    for idx, ep in enumerate(episodes):
        eid = ep["episode_id"]
        if eid in done: continue
        spec = spec_map.get(eid, ep.get("latent_spec", {})); t0 = time.time()
        print(f"[{idx+1}/{len(episodes)}] {eid} ({ep.get('paradigm')}/{ep.get('condition')}) sessions={len(ep['sessions'])} probes={len(ep['probes'])}", flush=True)
        try:
            adapter.reset(eid, ep, spec)
        except Exception as e:
            log.error(f"  reset failed: {e}"); results[key][eid] = {"error": f"reset: {e}", "answers": []}; json.dump(results, open(out, "w"), indent=2); continue
        ingest_errors = 0
        for s in ep["sessions"]:
            try: adapter.ingest(s)
            except Exception as e: ingest_errors += 1; log.warning(f"  ingest error at session {s.get('session_idx')}: {e}")
        ingest_time = time.time() - t0
        answers = []
        for probe in ep["probes"]:
            pt = probe["probe_type"]; rec = {"probe_type": pt, "gold": probe.get("gold_answer", "")}
            try:
                if end_to_end:
                    pred = "[DRY-RUN]" if args.dry_run and name not in ("latest_value", "always_update", "always_preserve") else adapter.answer(probe)  # type: ignore[misc]
                    if getattr(adapter, "last_indices", None) is not None: rec["retrieved_indices"] = adapter.last_indices
                else:
                    ctx = adapter.retrieve(probe["question"])
                    prompt = f"{adapter.context_header}\n\n{ctx}\n\nQuestion: {probe['question']}\n\n{PR._PROBE_SCHEMAS.get(pt, '')}"
                    pc = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
                    pc.setdefault(eid, []).append({"probe_type": pt, "question": probe["question"], "gold_answer": probe.get("gold_answer", ""), "prompt": prompt})
                    json.dump(pc, open(cache_path, "w"), indent=2)
                    pred = "[DRY-RUN]" if args.dry_run else call_llm(PR.READER_SYSTEM, prompt, model=(args.reader_model or READER_MODEL), temperature=0.0, max_tokens=4096)
            except Exception as e:
                pred = f"[ERROR: {e.__class__.__name__}: {e}]"
            sc = PR.score_answer(pred, probe.get("gold_answer", ""), pt, spec=spec)
            if pred == "[DRY-RUN]": sc = {"match": "execution_error", "reason": "dry run"}
            rec.update(predicted=pred, match=sc["match"], reason=sc.get("reason", "")); answers.append(rec)
        try: results["stored_memories"].setdefault(key, {})[eid] = adapter.stored_memories()
        except Exception: pass
        try: adapter.close()
        except Exception: pass
        results[key][eid] = {"answers": answers, "n_memories": len(results["stored_memories"].get(key, {}).get(eid) or []),
                             "ingest_time_sec": round(ingest_time, 1), "ingest_errors": ingest_errors, "sessions_fed": len(ep["sessions"]),
                             "total_time_sec": round(time.time() - t0, 1)}
        json.dump(results, open(out, "w"), indent=2)
        print(f"  {sum(a['match'] == 'correct' for a in answers)}/{len(answers)} correct  ingest={ingest_time:.0f}s total={time.time()-t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system", nargs="*", default=[], choices=sorted(SYSTEMS), help="built-in systems / baselines to run")
    ap.add_argument("--adapter", default=None, help="your adapter: module_or_file:ClassName")
    ap.add_argument("--name", default="custom", help="name for --adapter (report key <name>_full)")
    ap.add_argument("--key", default=None, help="override the report key")
    ap.add_argument("--episodes", default=str(P.EPISODES56)); ap.add_argument("--specs", default=str(P.SPECS56))
    ap.add_argument("--output", required=True, help="report JSON (resumes if it exists; several systems may share one file)")
    ap.add_argument("--limit", type=int, default=None); ap.add_argument("--only", nargs="*", default=None, help="episode ids")
    ap.add_argument("--reader-backend", default="gemini"); ap.add_argument("--reader-model", default=None, help=f"default {READER_MODEL}")
    ap.add_argument("--work-dir", default="/tmp/memprobe_run", help="scratch dir for Chroma / Kuzu / MemoryOS stores (local disk, not NFS)")
    ap.add_argument("--amem-repo", default="/tmp/A-mem"); ap.add_argument("--memoryos-repo", default="/tmp/MemoryOS/memoryos-pypi")
    ap.add_argument("--buffer-k", type=int, default=5, help="k for the recency example adapter")
    ap.add_argument("--dry-run", action="store_true", help="ingest + retrieve + cache prompts, skip every LLM reader call")
    args = ap.parse_args()
    if not args.system and not args.adapter: ap.error("give --system ... and/or --adapter")

    spec_map = {s["episode_id"]: s for s in json.load(open(args.specs))["specs"]}
    episodes = [json.loads(l) for l in open(args.episodes) if l.strip()]
    if args.only: episodes = [e for e in episodes if e["episode_id"] in set(args.only)]
    if args.limit: episodes = episodes[: args.limit]
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    results = json.load(open(out)) if out.exists() else {}

    jobs = []
    for s in args.system:
        kw = {"work_dir": args.work_dir}
        if s == "amem": kw["amem_repo"] = args.amem_repo
        if s == "memoryos": kw["memoryos_repo"] = args.memoryos_repo
        if s == "recency": kw["k"] = args.buffer_k
        if s in REFERENCE: kw["model"] = args.reader_model or READER_MODEL
        jobs.append((s, SYSTEMS[s](**kw), args.key or (s if s in REFERENCE else f"{s}_full")))
    if args.adapter:
        jobs.append((args.name, load_user_adapter(args.adapter, work_dir=args.work_dir), args.key or f"{args.name}_full"))

    LLM_REFERENCES = {"judge", "full_context", "naive_rag", "time_aware_rag", "oracle_rag"}
    reader_needed = any((not callable(getattr(a, "answer", None))) or n in LLM_REFERENCES for n, a, _ in jobs)
    if reader_needed and not args.dry_run:
        if args.reader_backend == "gemini": need_gemini_key()
        set_llm_backend(args.reader_backend)

    for name, adapter, key in jobs:
        evaluate(name, adapter, key, episodes, spec_map, args, results, out)
    print(f"\nDone. Report: {out}\nNext: python src/analysis/compute_metrics.py {out}", flush=True)


if __name__ == "__main__":
    main()
