# Full Implementation & Reproducibility for Memory-System Baselines

## 0. Environment


| Item                   | Value                                                                                                                                           |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| OS                     | Ubuntu 22.04.5 LTS                                                                                                                              |
| glibc                  | 2.35 (cannot upgrade; no root/sudo)                                                                                                             |
| Containers             | No Docker, no Postgres/MySQL server, no sudo                                                                                                    |
| `$HOME`                | NFS-mounted — flaky for SQLite/Postgres data dirs ("Stale file handle"); use `/tmp` (local disk) for any DB/model cache |
| Primary Python env     | conda `agent_mem`, **Python 3.10.19**                                                                                                           |
| GPU                    | CUDA 12.1 available (torch 2.5.1+cu121); embeddings run CPU-fine                                                                                |
| Isolated venvs created | `/tmp/hs_venv` (Python 3.12.8, for Hindsight), `/tmp/memori_venv` (Python 3.10.19, for Memori)                                                  |


## 1. Common evaluation protocol 

The protocol isolates memory quality from reader quality so all systems are directly comparable.

1. **Per episode**: create a fresh, isolated memory store.
2. **Incremental ingestion**: feed the episode's sessions one at a time, in order, exactly as the memory system's API expects (note / fact / turn-pair /
   knowledge-graph episode).
3. **Probe-time retrieval**: for each probe question, ask the memory system to retrieve its relevant memory (NOT to answer). Where a system only offers a "generate an answer" call, we use its lowest-level *context-only* retrieval (e.g. cognee `only_context=True`, MemoryOS `retriever.retrieve_context`).
4. **Unified reader**: format the retrieved memory as context and answer the probe with `gemini-3-flash-preview` using the shared structured-JSON prompt (`READER_SYSTEM` + `_PROBE_SCHEMAS` from `src/eval/protocol.py`).
5. **Scoring**: `score_answer()` (typed field comparison) → `compute_metrics.py`.

**Model consistency (critical)**: every memory system's internal LLM = `gemini-2.5-flash`; every *reader* = `gemini-3-flash-preview`. Embeddings vary
by system (noted per system) because embedding choice is part of the system.

**Episodes / specs:** `data/suite56/episodes.jsonl`, `data/suite56/latent_specs.json`. Split episodes (12 of 56) carry `perturbation_p1` / `perturbation_p2` session types; the rest are non-split.


---


## 2. Systems (6 memory systems + 2 RAG diagnostics)


### 2.1 Mem0  — `mem0ai==2.0.2`  

- **Install:** `pip install mem0ai chromadb`
- **Backend:** Chroma (embedded, fresh collection per episode under `<work-dir>/chroma/<eid>` (work dir defaults to `/tmp/memprobe_run`, set with `--work-dir`)).
- **LLM/embedder:** `Memory.from_config({"llm":{"provider":"gemini","config":{"model":"gemini-2.5-flash"}}, "embedder":{"provider":"gemini","config":{"model":"models/gemini-embedding-001","embedding_dims":768}}, "vector_store":{"provider":"chroma",...}})`. Uses Mem0 library default temp/top_p (we only override the model).
- **Ingestion:** `m.add(messages, user_id=eid)` once per session (messages = that session's user/assistant turns).
- **Retrieval:** `m.get_all(filters={"user_id": eid})` → all extracted facts → reader.
- **Isolation:** fresh Chroma dir per episode.
- **Gotchas / patches:**
  - Embedding model must be `models/gemini-embedding-001` (NOT `text-embedding-004` → 404 on v1beta).
  - `search`/`get_all` need `filters={"user_id":...}`, not top-level `user_id=`.
  - **Must call** `m.close()` **+** `gc.collect()` **between episodes** or Chroma SQLite connections accumulate → "unable to open database file" after ~47 episodes.



### 2.2 LangMem — `langmem==0.0.30` + `langchain-google-genai==4.2.2` 

- **Install:** `pip install langmem langchain-google-genai`
- **Backend:** none (stateless `create_memory_manager`; consolidation carried in-process).
- **LLM/embedder:** `create_memory_manager(ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0), enable_inserts=True, enable_updates=True, enable_deletes=True)`. No embedder (memories carried as a list).
- **Ingestion:** per session `extracted = manager.invoke({"messages": msgs, "existing": existing})`; carry `existing=[(m.id, m.content) for m in extracted]` forward across sessions for consolidation.
- **Retrieval:** pass ALL final memories as context to reader (analogous to Mem0 get_all).
- **Isolation:** fresh `existing=[]` per episode (stateless → perfect isolation).
- **Gotchas / patches:**
  - **Python 3.10 shim:** langmem 0.0.30 uses `typing.NotRequired`/`typing.Required` (3.11+). Before importing langmem: `import typing, typing_extensions; typing.NotRequired = typing_extensions.NotRequired; typing.Required = typing_extensions.Required`.



### 2.3 Graphiti / Zep — `graphiti-core==0.29.0` + `kuzu==0.11.3` 

- **Install:** `pip install "graphiti-core[google-genai,kuzu]"`
- **Backend:** Kuzu embedded graph DB, fresh `.kuzu` file per episode under `<work-dir>/kuzu/<eid>.kuzu` (dropped after each episode).
- **LLM/embedder/reranker:** `GeminiClient(LLMConfig(model="gemini-2.5-flash", temperature=0.0))`, `GeminiEmbedder(GeminiEmbedderConfig(embedding_model="models/gemini-embedding-001", embedding_dim=768))`, `GeminiRerankerClient(LLMConfig(model="gemini-2.5-flash"))`.
- **Ingestion:** async `await g.add_episode(name=..., episode_body=<session text>, source=EpisodeType.message, reference_time=base+timedelta(hours=i), group_id=eid)` per session.
- **Retrieval:** `await g.search(query, group_ids=[eid], num_results=15)` → `edge.fact` strings → reader.
- **Isolation:** fresh Kuzu DB + group_id per episode.
- **Two REQUIRED patches for graphiti-core 0.29.0 + Kuzu** (both are upstream bugs):
  1. `KuzuDriver` lacks `_database`, which `add_episode` reads. After constructing the driver: `driver._database = ""` (Kuzu `clone()` is a no-op; group_id is still stored on nodes/edges).
  2. `KuzuDriver.build_indices_and_constraints` is a no-op, so FTS indices (`edge_name_and_fact`, etc.) are never created → first search inside `add_episode` raises "Table RelatesToNode_ doesn't have an index". Call the real implementation directly: `await g.driver._graph_ops.build_indices_and_constraints(g.driver, delete_existing=False)`.
- **Quirks:** internal gemini-2.5 extraction produced malformed JSON on ~178/≈1100 session-adds across 56 ep; these were skipped gracefully (graph still built from the rest).



### 2.4 cognee — `cognee==1.1.0` 

- **Install:** `pip install cognee` (needs `langdetect`; if its wheel build fails with NFS "Stale file handle", retry `pip install --no-cache-dir langdetect` from `/tmp`).
- **Backend:** fully embedded — Kuzu (graph) + LanceDB (vector) + SQLite (relational); all default, no server.
- **LLM/embedder (config-setter API, NOT env vars — env names from blogs are wrong):**
  ```python
  os.environ["COGNEE_SKIP_CONNECTION_TEST"] = "true"  # else 30s startup probe can hang
  cognee.config.set_llm_provider("gemini")
  cognee.config.set_llm_model("gemini/gemini-2.5-flash")   # litellm-style prefix
  cognee.config.set_llm_api_key(KEY)
  cognee.config.set_embedding_provider("gemini")
  cognee.config.set_embedding_model("gemini/gemini-embedding-001")
  cognee.config.set_embedding_api_key(KEY)
  ```
- **Ingestion (async):** per session `await cognee.add(text, dataset_name=ds)` then `await cognee.cognify(datasets=[ds])`.
- **Retrieval (key trick for reader consistency):**
`await cognee.search(query, query_type=SearchType.GRAPH_COMPLETION, datasets=[ds], only_context=True, top_k=15)`.
`only_context=True` returns the retrieved **graph subgraph/nodes as text** WITHOUT cognee's internal LLM synthesizing the answer → the unified gemini-3 reader does the answering (keeps reader consistent). (Plain GRAPH_COMPLETION would answer with cognee's internal gemini-2.5.)
- **Isolation:** `await cognee.prune.prune_data()` + `await cognee.prune.prune_system(metadata=True)` before each episode (cognee uses global embedded DBs; full reset per episode).



### 2.5 A-MEM — `WujiangXu/A-mem` (git clone, research scripts)

- **Install:** `git clone https://github.com/WujiangXu/A-mem` to `/tmp/A-mem`; deps already present in env (`sentence-transformers, chromadb, litellm, rank-bm25, nltk, transformers, torch`). `nltk.download('punkt'); nltk.download('punkt_tab')`. Import `memory_layer.py` directly (no pip package).
- **Backend:** in-process `SimpleEmbeddingRetriever` (sentence-transformers `all-MiniLM-L6-v2`) — local embeddings, no server.
- **LLM:** bootstrap `AgenticMemorySystem(llm_backend="openai", llm_model="gpt-4o-mini", api_key="dummy")`, then **swap the controller**: `amem.llm_controller.llm = GeminiLiteLLMController(model="gemini/gemini-2.5-flash", api_key=KEY)` (A-MEM's factory has no gemini option; LiteLLMController handles Gemini).
- **Ingestion:** per session `amem.add_note(content=<session text>, time="2026..", tags=[session_type], category=session_type)`. Each note → 1 LLM metadata-extraction call + neighborhood evolution.
- **Retrieval:** `ctx, idx = amem.find_related_memories(probe_question, k=15)` → reader.
- **Isolation:** fresh `AgenticMemorySystem` per episode.
- **REQUIRED patch (Gemini):** A-MEM's `analyze_content` sends OpenAI **strict** json_schema (`{"strict":True, "additionalProperties":False}`) which litellm+Gemini rejects → A-MEM's empty-metadata fallback (keywords/tags all empty) → degraded to content-only. Subclass `LiteLLMController.get_completion` to downgrade response_format to `{"type":"json_object"}` (Gemini supports it):
  ```python
  class GeminiLiteLLMController(LiteLLMController):
      def get_completion(self, prompt, response_format=None, temperature=0.7):
          resp = litellm.completion(model=self.model, api_key=self.api_key,
              messages=[{"role":"system","content":"You must respond with a JSON object."},
                        {"role":"user","content":prompt}],
              response_format={"type":"json_object"}, temperature=temperature)
          return resp.choices[0].message.content
  ```
- **Cache note:** set `HF_HOME`/`SENTENCE_TRANSFORMERS_HOME` to `/tmp/hf_cache` (NFS `$HOME` cache throws "Stale file handle" loading the model).



### 2.6 MemoryOS — `BAI-LAB/MemoryOS` (git clone, `memoryos-pypi`) 

- **Install:** `git clone https://github.com/BAI-LAB/MemoryOS`; add `MemoryOS/memoryos-pypi` to `sys.path`. Deps: `sentence-transformers`, `faiss-cpu`, `openai` (all present). `FlagEmbedding` is only needed for BGE-M3 (lazy import) — not required when using `all-MiniLM-L6-v2`.
- **Backend:** file-based JSON (short/mid/long-term) + FAISS in-memory; fully local, no server.
- **LLM (via OpenAI-compatible Gemini endpoint — avoids google-genai/protobuf entirely):**
  ```python
  Memoryos(user_id=..., assistant_id=..., openai_api_key=KEY,
           openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
           llm_model="gemini-2.5-flash",
           embedding_model_name="all-MiniLM-L6-v2",   # local
           data_storage_path="<work-dir>/memoryos/<eid>", short_term_capacity=7)
  ```
- **Ingestion:** split each session into (user, assistant) turn-pairs; `memo.add_memory(user_input=u, agent_response=a)` per pair. Mid-term promotion + profile/knowledge extraction fire as short-term fills (LLM calls).
- **Retrieval:** `memo.retriever.retrieve_context(user_query=probe, user_id=memo.user_id)` → `retrieved_pages` + `retrieved_user_knowledge` + `retrieved_assistant_knowledge` → reader. (We deliberately use this instead of `get_response()`, which would answer with the internal gemini-2.5.)
- **Isolation:** fresh `data_storage_path` + user_id/assistant_id per episode (dir deleted after).
- **REQUIRED patch (Gemini thinking model):** MemoryOS's `OpenAIClient.chat_completion` does `response.choices[0].message.content.strip()` with `max_tokens=2000`. `gemini-2.5-flash` via the OpenAI-compat endpoint returns `content=None` when the whole budget is consumed by thinking → crash + zero memory promotion. Monkey-patch to pass `reasoning_effort="none"` (disables thinking on the OpenAI-compat endpoint) and guard `None`:
  ```python
  import utils as memoryos_utils
  def _patched_chat(self, model, messages, temperature=0.7, max_tokens=2000):
      resp = self.client.chat.completions.create(model=model, messages=messages,
          temperature=temperature, max_tokens=max_tokens, reasoning_effort="none")
      raw = resp.choices[0].message.content
      return memoryos_utils.clean_reasoning_model_output(raw.strip()) if raw else ""
  memoryos_utils.OpenAIClient.chat_completion = _patched_chat
  ```
- **Cache note:** same `HF_HOME=/tmp/hf_cache` for the sentence-transformer.


### 2.7 Diagnostic RAG ablations — `run_eval.py --system time_aware_rag oracle_rag` 

- Reuse the Naive-RAG keyword retriever; reader = gemini-3-flash-preview.
- **time_aware_rag:** same top-5 keyword retrieval, but each retrieved session is labelled with its TRUE timeline position ("Session 19 of 21 (perturbation)") so the reader sees chronological position (Naive RAG re-numbers them 1–5).
- **oracle_rag:** skip retrieval; pass ONLY non-filler sessions (`encoding` + `perturbation` + `perturbation_p1/p2`), labelled with true indices → reader. Isolates retrieval failure from reader failure.

