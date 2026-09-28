# Custom-Domain Authoring Guide

This guide is for anyone who wants to **build their own MemProbe-style evaluation suite in a new domain** while reusing the original benchmark structure: paradigms, conditions, probe types, scoring, and evaluation.

## 0. Quickstart

```bash
cd src/authoring
export GEMINI_API_KEY=...

# Create a starter project
python scaffold_suite.py --name my_domain --out ~/my_suites/

# Optional: generate a starter fact-type registry
python propose_facts_with_llm.py \
  --domain my_domain \
  --description "1-2 sentences describing the domain" \
  --out ~/my_suites/my_domain/domain_config.json

# Hand-edit:
#   ~/my_suites/my_domain/domain_config.json
#   ~/my_suites/my_domain/mini_specs.jsonl

# Expand
python expand_specs.py \
  --mini-specs ~/my_suites/my_domain/mini_specs.jsonl \
  --domain-config ~/my_suites/my_domain/domain_config.json \
  --out ~/my_suites/my_domain/latent_specs.json

# Validate before spending LLM calls
python validate_suite.py ~/my_suites/my_domain/latent_specs.json

# Realize dialogue + probes (generic fillers come from filler_pool.json; build it once, ~90 MB)
python ../suite_construction/build_filler_pool.py --output ../../filler_pool.json
python ../suite_construction/realize_episodes.py \
  --filler-mode pool \
  --specs ~/my_suites/my_domain/latent_specs.json \
  --filler-pool ../../filler_pool.json \
  --backend gemini --model gemini-3.1-pro-preview \
  --output ~/my_suites/my_domain/episodes.jsonl

# Validate realized episodes
python validate_suite.py ~/my_suites/my_domain/episodes.jsonl

# Evaluate
python ../eval/run_eval.py \
  --system full_context naive_rag \
  --episodes ~/my_suites/my_domain/episodes.jsonl \
  --specs ~/my_suites/my_domain/latent_specs.json \
  --output ~/my_suites/my_domain/report.json
python ../analysis/compute_metrics.py ~/my_suites/my_domain/report.json
```

For most users, this is the complete workflow.

## 1. How a MemProbe suite works

### 1.1 Episode structure

A MemProbe **episode** tests memory behavior around a **single fact about the user**, such as “what gym does the user go to?” A typical core episode is:

```
[encoding × 3] -> [filler × 15] -> [perturbation × 1] -> [filler × 2]
```

### 1.2 Probe types

Standard probes are:
- `current_value` — what is the fact now?
- `previous_value` — what was it before the change?
- `change_detection` — did it change?
- `source` — who introduced the new/conflicting value?
- `conflict_value` — what conflicting value appeared, and was it accepted?
- `temporal` — when or why did the change happen?

### 1.3 Paradigms and conditions

| Paradigm | What it tests | Conditions |
|---|---|---|
| `interference` | competing similar facts | `authoritative_update`, `decoy_no_update` |
| `misinformation` | false or non-authoritative evidence | `user_explicit`, `assistant_noise`, `third_party_noise`, `stale_tool` |
| `consolidation` | resistance after reinforcement | `high`, `low`, `high_weak_challenge`, `low_weak_challenge` |
| `reconsolidation` | updateability after recall | `reactivated`, `direct`, `reactivated_weak`, `direct_weak` |

Expected behavior is:

- `authoritative_update`, `user_explicit`, `high`, `low`, `reactivated`, `direct` -> `should_update`
- the corresponding noise / weak-challenge conditions -> `should_preserve`   

The canonical mapping lives in `presets.py: CONDITIONS_BY_PARADIGM`.

## 2. Authoring paths

### 2.1 Minimal-spec path — recommended

Write one **7-field JSON object per episode**:

```json
{
  "episode_id": "MYDOM-INT-01",
  "paradigm": "interference",
  "condition": "authoritative_update",
  "domain": "my_domain",
  "fact_type": "favorite_dish",
  "initial_value": "kung pao chicken at Sichuan Garden",
  "new_value": "Tom Yum soup at Thai Spice"
}
```
`expand_specs.py` fills in the remaining fields using `presets.py` and `domain_config.json`.

Optional overrides include:

| Field | Default |
|---|---|
| `canonical_initial`, `canonical_new` | heuristic canonicalization |
| `distractor_values` | fact-type distractor pool |
| `encoding_contexts` | `domain_config.json` |
| `length_tier` | `"core"` |
| `group_id`, `group_role`, `base_fact_type`, `difficulty_target`, `group_design` | singleton defaults |
| `perturbation_wording` | paradigm/condition template |
| `probe_overrides` | paradigm/condition template |

Use overrides only when the defaults are clearly unsuitable.

### 2.2 Full-control path

If you need custom perturbation flags, `paradigm_metadata`, gold structures, filler plans, or probe definitions, write or edit a full `latent_specs.json` in the same shape as: `data/suite56/latent_specs.json`
Recommended workflow:
1. start with minimal specs;
2. expand them;
3. inspect `latent_specs.json`;
4. edit only the fields that need custom behavior;
5. realize episodes from the edited file.

The expander is additive: fields already present are not overwritten.

## 3. Files you actually author

### 3.1 `mini_specs.jsonl`

One JSON object per line. Required fields:

```
episode_id
paradigm
condition
domain
fact_type
initial_value
new_value
```

`#`-prefixed lines are ignored as comments. A useful pilot pattern is to create episodes in groups of four—one per paradigm, so failures are easier to localize.

### 3.2 `domain_config.json`

Defines domain-level defaults and fact types:

```json
{
  "domain": "restaurant_reviews",
  "description": "Casual chat about restaurants, dishes, and dining preferences.",
  "style": "friendly, casual, like texting a foodie friend",
  "fact_types": {
    "favorite_dish": {
      "readable": "favorite dish",
      "encoding_contexts": [
        "user asks for recipes that recreate their favorite dish",
        "user plans a restaurant visit and mentions the dish they always order",
        "user compares similar dishes across restaurants"
      ],
      "distractor_values_pool": ["pho", "ramen", "biryani", "carbonara", "gnocchi"]
    }
  }
}
```

For each fact type, the key fields are:

- `readable`
- `encoding_contexts`
- `distractor_values_pool`

`propose_facts_with_llm.py` can create a starter config, but it should be reviewed manually.

### 3.3 Generated artifacts

| File | Produced by | Purpose |
|---|---|---|
| `latent_specs.json` | `expand_specs.py` | full structured episode specs |
| `episodes.jsonl` | `realize_episodes.py` | realized dialogue + probes |

Treat these as generated artifacts unless you intentionally use the full-control path.

## 4. Authoring tools

| Tool | Purpose |
|---|---|
| `scaffold_suite.py` | creates a starter domain directory |
| `propose_facts_with_llm.py` | proposes fact types and example values |
| `expand_specs.py` | expands minimal specs into full latent specs |
| `validate_suite.py` | checks mini specs, latent specs, or realized episodes |
| `presets.py` | single source of truth for paradigms, conditions, templates, and gold defaults |

### `scaffold_suite.py`

```bash
python scaffold_suite.py --name my_domain --out ./my_suites/
```

Creates `README.md`, `domain_config.json`, and `mini_specs.jsonl`, including four starter episodes.

### `propose_facts_with_llm.py`

```bash
python propose_facts_with_llm.py \
  --domain my_domain \
  --description "1-2 sentences describing the domain" \
  --n-fact-types 8 \
  --out ./my_suites/my_domain/domain_config.json
```

It also writes `starter_minis.jsonl` with example `(initial_value, new_value)` pairs.

### `expand_specs.py`

```bash
python expand_specs.py \
  --mini-specs mini_specs.jsonl \
  --domain-config domain_config.json \
  --out latent_specs.json
```

The expander is deterministic: the same inputs produce the same output.

### `validate_suite.py`

| Input | Main checks |
|---|---|
| `mini_specs.jsonl` | required fields, legal paradigm-condition pairs, duplicate IDs, `initial == new` |
| `latent_specs.json` | expected behavior, gold structure, probes, filler totals, distractors |
| `episodes.jsonl` | encoding/perturbation presence, legal session types, non-empty dialogue, probe gold answers |

Exit codes:

```text
0 = clean
1 = errors
2 = warnings only
```

Run it before realization and again after realization.

## 5. Designing good fact types

Fact-type design is the most important authoring decision.

### One current value at a time

Good: `favorite_dish = "Tom Yum"`

Bad:`favorite_dishes = ["Tom Yum", "pho"]`

### Use concrete values

Good: `"Sichuan Garden"`

Bad: `"the place near my office that has good lighting"`

Named entities, short noun phrases, IDs, categories, and similar concrete values are easier to generate and score reliably.

### Make the update meaningful

Good: `"Sichuan Garden" -> "Thai Spice"`

Bad: `"Sichuan Garden" -> "Sichuan Garden Restaurant"`

The new value should represent a real change, not a paraphrase.

### Use same-category distractors

For `favorite_dish`, use other dishes such as `pho`, `ramen`, or `biryani`, not restaurant names or unrelated entities.

### Require several natural contexts

You should be able to think of at least three realistic ways the user could mention the fact. If the fact only fits one narrow context, it is probably too artificial.

### Keep enough domain breadth

A domain with only one or two usable fact types tends to produce repetitive distractors. As a practical starting point, aim for roughly **6–10 fact types** if the domain supports them.

### Agentic facts are supported

Facts can also be config values, port numbers, branch names, tool outputs, or environment settings. These are especially useful for `stale_tool`-style conditions. See `data/suite56/latent_specs.json` for existing agentic examples.

## 6. Filler sessions

Filler sessions make the target fact less isolated and create interference. Common types include:

- `weakly_related_background`
- `near_miss`
- `confusable`
- `decoy_nonupdate`

The default workflow uses: `<repo-root>/filler_pool.json`

The pool is not shipped; rebuild it with `../suite_construction/build_filler_pool.py`. It contains roughly 18k sessions extracted from LongMemEval and LoCoMo.

If generic conversational fillers are a poor fit for your domain, either build a domain-specific pool or set:

```json
{
  "filler_pool_override": "path/to/my_pool.json"
}
```

## 7. Common pitfalls

1. **Invalid paradigm-condition pair.** Run `validate_suite.py mini_specs.jsonl` before expansion.

2. **Initial/new values overlap.** Avoid pairs such as `"Sichuan"` -> `"Sichuan Garden"` because substring overlap can create spurious score matches.

3. **Distractors overlap with target values.** Expand the pool in `domain_config.json` if filtering leaves too few alternatives.

4. **Domain is too narrow.** Prefer several distinct fact types over many episodes of one fact type.

5. **Realizing before validating.** Always run:
   ```bash
   python validate_suite.py latent_specs.json
   ```
   before paying for LLM realization.

6. **Missing `conflict_gold` in hand-written full specs.** The expander creates it automatically; full-control specs must provide it explicitly when required.

7. **Confusing `expected_behavior` with a probe answer.** `should_update` / `should_preserve` describe the perturbation. A `previous_value` probe in a `should_update` episode still expects the original value.

## 8. Advanced customization

Most custom domains do **not** need this section.

### 8.1 Add a new condition

Edit `presets.py`:

1. add the condition to `CONDITIONS_BY_PARADIGM`;
2. define `EXPECTED_BEHAVIOR`;
3. add the perturbation template;
4. add any required paradigm metadata;
5. add probe templates;
6. update conflict-status logic if needed.

`expand_specs.py` and `validate_suite.py` will then pick it up.

### 8.2 Add a new paradigm

Also:

1. append it to `PARADIGMS`;
2. define its conditions;
3. document its cognitive rationale;
4. inspect `../analysis/compute_metrics.py` to determine whether a custom metric is needed.

### 8.3 Add a probe type

A new probe type requires:

1. `LEGAL_PROBE_TYPES` in `validate_suite.py`;
2. a schema in `protocol._PROBE_SCHEMAS`;
3. matching logic in `protocol.score_answer`;
4. probe templates for any condition that uses it.

### 8.4 Custom scoring

The scoring entry point is:

```python
protocol.score_answer(predicted, gold, probe_type, spec)
```

It returns a structure containing:

```json
{
  "match": "correct | incorrect | partial | execution_error",
  "reason": "..."
}
```

Custom scoring is compatible with downstream analysis as long as the `match` field is preserved.

## 9. Reproducibility and sharing

For a released custom suite, share:

```text
mini_specs.jsonl
domain_config.json
latent_specs.json
episodes.jsonl
```

Also record the realization configuration:

```text
backend
model
temperature
other non-default generation settings
```

The first two files are the human-authored source; the latter two freeze the exact expanded specs and realized episodes used in evaluation.

Recommended layout:

```text
my_suite/
├── mini_specs.jsonl
├── domain_config.json
├── latent_specs.json
├── episodes.jsonl
└── README.md
```