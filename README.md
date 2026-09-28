# MemProbe

Code, data and evaluation tools for **"Probing Stability–Plasticity Tradeoffs in Agent Memory through Cognitive Experimental Paradigms"** (EMNLP 2026). Paper link: [https://arxiv.org/abs/2609.30558](https://arxiv.org/abs/2609.30558)

**MemProbe is a multi-dimensional evaluation framework for long-term memory systems.** It uses four cognitive-inspired paradigms: **interference, misinformation, consolidation, and reconsolidation**, to test how memory systems update, preserve, and distinguish information under different memory challenges.

Beyond overall accuracy, MemProbe evaluates complementary dimensions including **plasticity, stability, historical fidelity, source fidelity, and temporal/conflict understanding**.

## Contents

1. [Quickstart](#quickstart)
2. [Repository structure](#repository-structure)
3. [Reproducing paper results](#reproducing-paper-results)
4. [Evaluating your own system](#evaluating-your-own-system)
5. [Building your own suite](#building-your-own-suite)
6. [Model configuration](#model-configuration)
7. [Expected runtime and cost](#expected-runtime-and-cost)
8. [Citation](#citation)
9. [License and third-party data](#license-and-third-party-data)



## Quickstart



### Environment

```bash
conda create -n memprobe python=3.10 -y
conda activate memprobe
pip install -r requirements.txt
```



### Recompute the paper results without an API key

```bash
python src/analysis/compute_metrics.py \
    results/suite56/reports/baselines_report_ALL_gemini.json \
    --baseline-compare full_context

python src/analysis/paper_tables.py --out /tmp/paper_tables.md
```



### Run a memory system and reference baselines

```bash
export GEMINI_API_KEY=...

python src/eval/run_eval.py \
    --system mem0 full_context naive_rag \
    --limit 2 \
    --output /tmp/demo.json

python src/analysis/compute_metrics.py /tmp/demo.json
```

All built-in systems and baselines run through `src/eval/run_eval.py`. Reports are saved after every episode and resume automatically.

## Repository structure

```text
.
├── README.md
├── IMPLEMENTATION_DETAILS.md setup, patches, and exact versions for all the systems
├── LICENSE
├── DATA_LICENSE
├── requirements.txt
├── env/
│   └── pip_freeze_full.txt
├── src/
│   ├── eval/                 evaluation protocol + adapters
│   ├── analysis/             metrics, bootstrap, paper tables
│   ├── suite_construction/   benchmark generation + validation
│   └── authoring/            custom-suite toolkit
├── data/
│   ├── suite56/              main suite
│   └── suite40/              second suite
└── results/
    ├── suite56/
    └── suite40/
```



## Reproducing paper results

Regenerate the numeric tables from the shipped outputs:

```bash
python src/analysis/paper_tables.py --out /tmp/paper_tables.md
```

The main result sources are under:

```
results/suite56/
results/suite40/
```

The analysis scripts reproduce the paper's overall accuracy, confidence intervals, stability–plasticity metrics, paradigm-wise results, fidelity metrics, reader ablations, diagnostic RAG ablations, suite validation, cross-model validation, and second-suite results.

To regenerate raw outputs:

```bash
python src/eval/run_eval.py --system <name>
```

To re-answer a cached retrieved context with another reader without re-ingesting memory:

```bash
python src/eval/reader_swap.py ...
```

See `IMPLEMENTATION_DETAILS.md` and the shipped analysis outputs for exact reproduction details.

## Evaluating your own system

MemProbe provides a common adapter interface so a new memory system can use the same episode isolation, ingestion order, shared reader, scorer, caching, resume behavior, and report format as the paper's systems.

A minimal adapter implements:

```python
# my_adapter.py

from run_eval import MemorySystemAdapter


class MyAdapter(MemorySystemAdapter):
    def reset(self, episode_id, episode=None, spec=None):
        self.mem = MySystem(namespace=episode_id)

    def ingest(self, session):
        self.mem.add(session["dialogue"])

    def retrieve(self, question):
        memories = self.mem.search(question, k=15)
        return "\n".join(m.text for m in memories)
```

`retrieve()` should return **memory content for the shared reader**, not a final answer.

For systems that cannot expose retrieved context, implement:

```python
answer(self, probe) -> str
```



### Run and score your adapter

```bash
export GEMINI_API_KEY=...

python src/eval/run_eval.py \
    --adapter my_adapter.py:MyAdapter \
    --name mysys \
    --output results/mine/report.json

python src/analysis/compute_metrics.py results/mine/report.json

python src/analysis/bootstrap.py overall \
    --report results/mine/report.json \
    --out results/mine/ci.json
```



### Compare with reported systems

```bash
python src/eval/merge_reports.py \
    results/suite56/reports/baselines_report_ALL_gemini.json \
    results/mine/report.json \
    --out results/mine/merged.json

python src/analysis/bootstrap.py paired \
    --report results/mine/merged.json \
    --only-pairs mysys_full:amem_full,mysys_full:full_context
```

For directly comparable results, keep the shared reader fixed and report both the reader model and any internal LLM used by your memory system.

To evaluate the second suite, pass:

```text
--episodes data/suite40/episodes.jsonl
--specs data/suite40/latent_specs.json
```



## Building your own suite

See `src/authoring/AUTHORING_GUIDE.md`. The second suite in `data/suite40/` was built with this workflow.

## Citation

```bibtex
@misc{ding2026probingstabilityplasticitytradeoffsagent,
      title={Probing Stability-Plasticity Tradeoffs in Agent Memory through Cognitive Experimental Paradigms}, 
      author={Jiaqi Ding and Guorong Wu},
      year={2026},
      eprint={2609.30558},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2609.30558}, 
}
```



## License and third-party data


| Content                                                | License      |
| ------------------------------------------------------ | ------------ |
| Code                                                   | MIT          |
| `data/suite56/` and `results/suite56/`                 | MIT          |
| `data/suite40/` and derived `results/suite40/` content | CC BY-NC 4.0 |
| rebuilt `filler_pool.json`                             | CC BY-NC 4.0 |


The root `LICENSE` covers MIT-licensed material; `DATA_LICENSE` covers CC BY-NC 4.0 material.

If you use the second suite, please cite **LoCoMo** (CC BY-NC 4.0) and **LongMemEval** (MIT):

- LoCoMo: [https://github.com/snap-research/locomo](https://github.com/snap-research/locomo)
- LongMemEval: [https://github.com/xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval)

```bibtex
@inproceedings{maharana2024locomo,
  title     = {Evaluating Very Long-Term Conversational Memory of LLM Agents},
  author    = {Maharana, Adyasha and Lee, Dong-Ho and Tulyakov, Sergey and Bansal, Mohit and Barbieri, Francesco and Fang, Yuwei},
  booktitle = {Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (ACL)},
  year      = {2024}
}

@inproceedings{wu2025longmemeval,
  title     = {LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory},
  author    = {Wu, Di and Wang, Hongwei and Yu, Wenhao and Zhang, Yuwei and Chang, Kai-Wei and Yu, Dong},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2025}
}
```

