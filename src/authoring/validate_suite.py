#!/usr/bin/env python3
"""Schema + consistency checker for MemProbe authoring artifacts.
USAGE
-----
    python validate_suite.py path/to/mini_specs.jsonl
    python validate_suite.py path/to/latent_specs.json
    python validate_suite.py path/to/episodes.jsonl
Exit code 0 = clean; 1 = errors found; 2 = warnings only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from presets import (  # noqa: E402
    CONDITIONS_BY_PARADIGM, EXPECTED_BEHAVIOR, LENGTH_TIERS, PARADIGMS,
)

LEGAL_PROBE_TYPES = {
    "current_value", "previous_value", "change_detection",
    "source", "conflict_value", "temporal",
}

LEGAL_SESSION_TYPES = {
    "encoding", "perturbation", "perturbation_p1", "perturbation_p2",
    "filler_weakly_related", "filler_near_miss", "filler_confusable",
    "filler_decoy_nonupdate", "filler_generic",
}

LEGAL_LENGTH_TIERS = set(LENGTH_TIERS.keys())


class Report:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def err(self, where: str, msg: str): self.errors.append(f"  [ERR] {where}: {msg}")
    def warn(self, where: str, msg: str): self.warnings.append(f"  [WARN] {where}: {msg}")

    def exit_code(self) -> int:
        if self.errors: return 1
        if self.warnings: return 2
        return 0

    def print(self, source: str):
        for e in self.errors:    print(e)
        for w in self.warnings:  print(w)
        n_err, n_warn = len(self.errors), len(self.warnings)
        verdict = "CLEAN" if (n_err + n_warn == 0) else f"{n_err} errors, {n_warn} warnings"
        print(f"[validate] {source}: {verdict}")


MINI_REQUIRED = (
    "episode_id", "paradigm", "condition", "domain",
    "fact_type", "initial_value", "new_value",
)


def validate_mini(rows: List[Dict], rep: Report) -> None:
    seen_ids = set()
    for i, r in enumerate(rows, 1):
        where = f"row {i} ({r.get('episode_id','?')})"
        for f in MINI_REQUIRED:
            if not r.get(f):
                rep.err(where, f"missing required field '{f}'")
        eid = r.get("episode_id", "")
        if eid in seen_ids:
            rep.err(where, f"duplicate episode_id '{eid}'")
        seen_ids.add(eid)
        p, c = r.get("paradigm"), r.get("condition")
        if p and p not in PARADIGMS:
            rep.err(where, f"unknown paradigm '{p}' (allowed: {PARADIGMS})")
        elif p and c and c not in CONDITIONS_BY_PARADIGM[p]:
            rep.err(where, f"condition '{c}' not legal for paradigm '{p}'. "
                           f"Allowed: {CONDITIONS_BY_PARADIGM[p]}")
        lt = r.get("length_tier", "core")
        if lt not in LEGAL_LENGTH_TIERS:
            rep.err(where, f"unknown length_tier '{lt}' (allowed: {sorted(LEGAL_LENGTH_TIERS)})")
        if r.get("initial_value") and r.get("initial_value") == r.get("new_value"):
            rep.warn(where, "initial_value == new_value — the perturbation has nothing to change")


def validate_full_specs(specs: List[Dict], rep: Report) -> None:
    seen_ids = set()
    required = ["episode_id", "paradigm", "condition", "domain", "fact_type",
                "initial_value", "new_value", "expected_behavior",
                "encoding", "perturbation", "filler_plan",
                "num_encoding_sessions", "num_pre_perturbation_fillers",
                "num_perturbation_sessions", "num_post_perturbation_fillers",
                "probes", "gold", "paradigm_metadata"]
    for s in specs:
        eid = s.get("episode_id", "?")
        where = eid
        for f in required:
            if f not in s:
                rep.err(where, f"missing field '{f}'")
        if eid in seen_ids:
            rep.err(where, f"duplicate episode_id")
        seen_ids.add(eid)

        p, c = s.get("paradigm"), s.get("condition")
        if p in PARADIGMS and c in CONDITIONS_BY_PARADIGM.get(p, []):
            exp = EXPECTED_BEHAVIOR[(p, c)]
            if s.get("expected_behavior") != exp:
                rep.err(where, f"expected_behavior should be '{exp}' for "
                               f"({p}, {c}), got '{s.get('expected_behavior')}'")

        probes = s.get("probes", [])
        if not probes:
            rep.err(where, "no probes")
        for j, pb in enumerate(probes):
            pt = pb.get("type") if isinstance(pb, dict) else None
            if pt not in LEGAL_PROBE_TYPES:
                rep.err(where, f"probes[{j}].type '{pt}' is not a legal probe type")

        gold = s.get("gold", {})
        if s.get("expected_behavior") == "should_update":
            for f in ("current_value", "previous_value", "has_changed"):
                if f not in gold:
                    rep.err(where, f"gold missing '{f}' for should_update")
            if gold.get("has_changed") is not True:
                rep.warn(where, "should_update spec but gold.has_changed is not True")
            if gold.get("current_value") != s.get("new_value"):
                rep.warn(where, f"gold.current_value '{gold.get('current_value')}' "
                                f"!= spec.new_value '{s.get('new_value')}'")
        elif s.get("expected_behavior") == "should_preserve":
            if gold.get("has_changed") is not False:
                rep.warn(where, "should_preserve spec but gold.has_changed is not False")
            if "conflict_gold" not in gold:
                rep.warn(where, "should_preserve spec missing gold.conflict_gold "
                                "(needed for conflict_value probe scoring)")

        dv = s.get("distractor_values", [])
        if len(dv) < 3:
            rep.warn(where, f"only {len(dv)} distractor_values "
                            f"(near-miss fillers may be repetitive)")

        fp = s.get("filler_plan", {})
        if fp:
            pre = fp.get("pre_perturbation", {})
            tot = pre.get("total", 0)
            comp = sum(v for k, v in pre.items() if k != "total" and isinstance(v, int))
            if tot and comp != tot:
                rep.warn(where, f"filler_plan.pre_perturbation.total={tot} "
                                f"but components sum to {comp}")


def validate_episodes(eps: List[Dict], rep: Report) -> None:
    for ep in eps:
        eid = ep.get("episode_id", "?")
        where = eid
        sessions = ep.get("sessions", [])
        probes = ep.get("probes", [])
        if not sessions:
            rep.err(where, "no sessions")
        if not probes:
            rep.err(where, "no probes")
        for j, s in enumerate(sessions):
            st = s.get("session_type")
            if st not in LEGAL_SESSION_TYPES:
                rep.warn(where, f"sessions[{j}].session_type '{st}' is unusual "
                                f"(legal: {sorted(LEGAL_SESSION_TYPES)})")
            dlg = s.get("dialogue", [])
            if not dlg:
                rep.err(where, f"sessions[{j}] has empty dialogue")
            for k, m in enumerate(dlg):
                if m.get("role") not in ("user", "assistant", "tool_output"):
                    rep.warn(where, f"sessions[{j}].dialogue[{k}].role "
                                    f"'{m.get('role')}' is unusual")
                if not str(m.get("content", "")).strip():
                    rep.warn(where, f"sessions[{j}].dialogue[{k}] empty content")
        kinds = [s.get("session_type") for s in sessions]
        if not any(k == "encoding" for k in kinds):
            rep.err(where, "no encoding sessions")
        if not any(k in ("perturbation", "perturbation_p1", "perturbation_p2") for k in kinds):
            rep.err(where, "no perturbation session(s)")
        for j, pb in enumerate(probes):
            if "probe_type" not in pb:
                rep.err(where, f"probes[{j}] missing 'probe_type'")
            if pb.get("probe_type") not in LEGAL_PROBE_TYPES:
                rep.err(where, f"probes[{j}].probe_type '{pb.get('probe_type')}' invalid")
            if not pb.get("question"):
                rep.warn(where, f"probes[{j}] missing 'question' text")
            if "gold_answer" not in pb:
                rep.err(where, f"probes[{j}] missing 'gold_answer'")


def detect_type(path: Path) -> str:
    text = path.read_text()
    if path.suffix == ".jsonl":
        line = next((l for l in text.splitlines()
                     if l.strip() and not l.lstrip().startswith("#")), "")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return "unknown"
        if "sessions" in obj and "probes" in obj:
            return "episodes"
        if {"episode_id", "paradigm", "condition", "fact_type"} <= set(obj):
            if "encoding" in obj and "perturbation" in obj and isinstance(obj.get("perturbation"), dict):
                return "latent_specs"
            return "mini_specs"
        return "unknown"
    obj = json.loads(text)
    if isinstance(obj, dict) and isinstance(obj.get("specs"), list):
        return "latent_specs"
    return "unknown"


def load_rows(path: Path, kind: str) -> List[Dict]:
    if kind == "latent_specs":
        return json.loads(path.read_text())["specs"]
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--kind", choices=["mini_specs", "latent_specs", "episodes", "auto"],
                    default="auto", help="Force input type instead of auto-detecting.")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[validate] file not found: {path}", file=sys.stderr)
        sys.exit(2)

    kind = args.kind if args.kind != "auto" else detect_type(path)
    print(f"[validate] {path} detected as: {kind}")
    rows = load_rows(path, kind)
    print(f"[validate] {len(rows)} rows")

    rep = Report()
    if kind == "mini_specs":
        validate_mini(rows, rep)
    elif kind == "latent_specs":
        validate_full_specs(rows, rep)
    elif kind == "episodes":
        validate_episodes(rows, rep)
    else:
        print(f"[validate] cannot validate unknown file type", file=sys.stderr)
        sys.exit(2)
    rep.print(str(path))
    sys.exit(rep.exit_code())


if __name__ == "__main__":
    main()
