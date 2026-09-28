"""Single source of truth for repository paths. Import from any script:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # -> src/
    import paths as P; P.add_src_to_path()
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EVAL, ANALYSIS, SUITE_CONSTRUCTION, AUTHORING = (SRC / d for d in ("eval", "analysis", "suite_construction", "authoring"))

DATA56 = ROOT / "data" / "suite56"
DATA40 = ROOT / "data" / "suite40"
EPISODES56 = DATA56 / "episodes.jsonl"
SPECS56 = DATA56 / "latent_specs.json"
EPISODES40 = DATA40 / "episodes.jsonl"
SPECS40 = DATA40 / "latent_specs.json"

RES56 = ROOT / "results" / "suite56"
REPORTS56, CACHES56, ANALYSIS56, CASES56 = RES56 / "reports", RES56 / "prompt_caches", RES56 / "analysis", RES56 / "source_error_cases"
RES40 = ROOT / "results" / "suite40"
REPORTS40, CACHES40 = RES40 / "reports", RES40 / "prompt_caches"

SEED_SKELETONS = ROOT / "data" / "seed_skeletons.md"


def add_src_to_path() -> None:
    for d in (SRC, EVAL, ANALYSIS, SUITE_CONSTRUCTION):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
