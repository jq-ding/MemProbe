# MemProbe new 40-episode extension suite

**Purpose.** Demonstrate that MemProbe's five-stage design pipeline is **rule-extensible** 

## 1. What was built

- **40 new episodes**, 10 per paradigm (interference / misinformation / consolidation / reconsolidation), 4 probes each = 160 probes total.
- **12 brand-new fact types** across the same 3 domains (Personal / Work / Agentic), no overlap with the original 21 fact types.
- `work` **domain adds a project-state family** (current_sprint_focus, active_feature_branch, release_train_target, oncall_rotation_role).
- `agentic` **domain adds a new config family** (active_kubernetes_context, rate_limit_threshold, log_shipping_destination + retained cache_ttl_seconds).
- `personal` **domain adds subscription/route/media types** (streaming service, delivery app, commute route, podcast).


| Dimension                         | Value                              |
| --------------------------------- | ---------------------------------- |
| Paradigm                          | 10 × 4 = 40                      |
| Update / Preserve                 | 21 / 19 = 52.5% / 47.5%            |
| always-update heuristic ceiling   | 52.5%                              |
| always-preserve heuristic ceiling | 47.5%                              |
| Domain                            | agentic 15 / personal 13 / work 12 |
| Fact-type usage                   | 1–6 uses each (mean 3.3)           |




## 2. Five-stage pipeline


| Stage                   | Artifact             | Method                                                                                                                                                                                      |
| ----------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Fact-type design     | `domain_config.json` | Hand-curated per-fact-type: readable name + 4 encoding contexts + 5–7 distractor pool                                                                                                       |
| 2. Value-pair design    | (same file)          | 4-5 (initial, new) pairs per fact type, category-plausible, non-overlapping tokens                                                                                                          |
| 3. Latent spec          | `latent_specs.json`  | Author writes a 7-field mini-spec per episode → `src/authoring/expand_specs.py` fills 40+ fields (perturbation defaults, filler plan, probe mix, gold, paradigm metadata) from `presets.py` |
| 4. Dialogue realization | `episodes.jsonl`     | `realize_episodes.py --filler-mode pool --backend gemini --model gemini-3.1-pro-preview --temperature 0.3`                                                                                  |
| 5. Validation           | (audit report)       | Schema check (`src/authoring/validate_suite.py`) + per-episode verbatim/leak/probe audits (`src/suite_construction/validate_episodes.py`)                                                   |


**LLM**: gemini-3.1-pro-preview for realization.
**Reader** (for downstream evaluation): **GPT-5.6** (paper Table 16, App. F). Memory systems were run once with the Qwen3-32B reader (prompt caches in `results/suite40/prompt_caches/`); the GPT-5.6 answers were produced from those caches with `src/eval/reader_swap.py`. 