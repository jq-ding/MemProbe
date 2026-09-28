"""
Usage
    python src/suite_construction/realize_episodes.py --specs data/suite56/latent_specs.json \
           --backend azure --model gpt-5.4 --output /tmp/episodes.jsonl            # templated (default)
    python src/suite_construction/realize_episodes.py --filler-mode pool --specs data/suite40/latent_specs.json \
           --backend gemini --model gemini-3.1-pro-preview --filler-pool filler_pool.json --output /tmp/ep40.jsonl
    python src/suite_construction/realize_episodes.py --dry-run --limit 2 --output /tmp/x.jsonl   # no API calls
    python src/suite_construction/realize_episodes.py --validate-only --input episodes.jsonl --specs specs.json
"""
from __future__ import annotations
import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P 
P.add_src_to_path()

from llm import call_llm, set_llm_backend, parse_dialogue  
from generation_prompts import (  
    encoding_session_prompt,
    perturbation_session_prompt,
    near_miss_filler_prompt,
    select_context_themes,
    FACT_TYPE_READABLE,
    DOMAIN_STYLE,
)
from validation_prompts import RuleValidator  

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


class SeedSkeletonIndex:
    def __init__(self, seed_path: Optional[str] = None):
        self.seeds: Dict[str, Dict] = {}
        if seed_path and Path(seed_path).exists():
            self._load(seed_path)

    def _load(self, path: str):
        text = Path(path).read_text()

        blocks = re.split(r"## Seed \d+", text)[1:]

        for block in blocks:
            meta_match = re.search(
                r"paradigm:\s*(\w+).*?domain:\s*(\w+).*?fact_type:\s*(\w+)",
                block, re.DOTALL,
            )
            if not meta_match:
                continue

            paradigm, domain, fact_type = meta_match.groups()

            encoding_match = re.search(
                r"### (?:Shared |HIGH )?Encoding Session 1.*?```\n(.*?)```",
                block, re.DOTALL,
            )
            encoding_example = encoding_match.group(1).strip() if encoding_match else ""

            filler_match = re.search(
                r"### Near-Miss Filler.*?```\n(.*?)```",
                block, re.DOTALL,
            )
            filler_example = filler_match.group(1).strip() if filler_match else ""


            conditions_and_perts = self._extract_perturbation_variants(block, paradigm)

            for condition, pert_example in conditions_and_perts:
                key = f"{paradigm}|{condition}|{domain}"
                entry = {
                    "encoding": encoding_example,
                    "perturbation": pert_example,
                    "filler": filler_example,
                }
                self.seeds[key] = entry

                key_pc = f"{paradigm}|{condition}"
                if key_pc not in self.seeds:
                    self.seeds[key_pc] = entry

    @staticmethod
    def _extract_perturbation_variants(
        block: str, paradigm: str
    ) -> List[Tuple[str, str]]:
        results = []

        pert_patterns = [
            (r"Perturbation.*?`user_explicit`.*?```\n(.*?)```", "user_explicit"),
            (r"Perturbation.*?`assistant_noise`.*?```\n(.*?)```", "assistant_noise"),
            (r"Perturbation.*?`third_party_noise`.*?```\n(.*?)```", "third_party_noise"),
            (r"Perturbation.*?REACTIVATED.*?```\n(.*?)```", "reactivated"),
            (r"Perturbation.*?DIRECT Condition.*?```\n(.*?)```", "direct"),
            (r"Perturbation.*?reactivation_then_weak.*?```\n(.*?)```", "reactivated_weak"),
            (r"Perturbation.*?near_miss_noise.*?```\n(.*?)```", "noise"),
            (r"Perturbation.*?scope_restricted.*?```\n(.*?)```", "scope_restricted"),
            (r"Perturbation.*?weak_challenge.*?```\n(.*?)```", "high_challenge"),
            (r"Perturbation.*?direct_update\).*?```\n(.*?)```", "standard"),
        ]

        for pattern, condition in pert_patterns:
            match = re.search(pattern, block, re.DOTALL | re.IGNORECASE)
            if match:
                results.append((condition, match.group(1).strip()))

        for condition, pert in list(results):
            if condition == "high_challenge":
                results.append(("low_challenge", pert))

        if paradigm == "consolidation" and not results:
            shared_match = re.search(
                r"### Shared Perturbation.*?```\n(.*?)```",
                block, re.DOTALL,
            )
            if shared_match:
                pert = shared_match.group(1).strip()
                results.append(("high", pert))
                results.append(("low", pert))

        if not results:
            cond_match = re.search(r"condition:\s*(\S+)", block)
            condition = cond_match.group(1).strip("\"'/ ") if cond_match else "unknown"
            pert_match = re.search(
                r"### (?:Shared )?Perturbation.*?```\n(.*?)```",
                block, re.DOTALL,
            )
            if pert_match:
                results.append((condition, pert_match.group(1).strip()))

        return results

    def get_example(
        self, paradigm: str, condition: str, domain: str, session_type: str
    ) -> Optional[str]:
        for key in [
            f"{paradigm}|{condition}|{domain}",
            f"{paradigm}|{condition}",
        ]:
            if key in self.seeds:
                return self.seeds[key].get(session_type, "")
        return None


class FillerPool:
    def __init__(self, pool_path: Optional[str] = None):
        self.pool: List[Dict] = []
        if pool_path and Path(pool_path).exists():
            self.pool = json.loads(Path(pool_path).read_text())
            log.info(f"Loaded {len(self.pool)} filler sessions from pool")

    def draw(
        self,
        n: int,
        exclude_topics: List[str],
        domain: str,
        rng: random.Random,
    ) -> List[Dict]:
        if self.pool:
            candidates = []
            for session in self.pool:
                text = json.dumps(session).lower()
                if not any(topic.lower() in text for topic in exclude_topics):
                    candidates.append(session)

            if len(candidates) >= n:
                return rng.sample(candidates, n)
            else:
                log.warning(
                    f"Only {len(candidates)} suitable fillers in pool, need {n}. "
                    f"Using all available + placeholders."
                )
                selected = list(candidates)
                for i in range(n - len(candidates)):
                    selected.append(self._placeholder(i))
                return selected
        else:
            return [self._placeholder(i) for i in range(n)]

    @staticmethod
    def _placeholder(idx: int) -> Dict:
        return {
            "session_type": "filler_generic",
            "dialogue": [
                {"role": "user", "content": f"[PLACEHOLDER — generic filler #{idx+1} from benchmark pool]"},
                {"role": "assistant", "content": "[PLACEHOLDER — to be replaced with real benchmark material]"},
            ],
            "metadata": {
                "source": "placeholder",
                "note": "Replace with real sessions from LoCoMo/LongMemEval/REALTALK/etc.",
            },
        }


class EpisodeGenerator:
    def __init__(
        self,
        seed_index: SeedSkeletonIndex,
        filler_pool: FillerPool,
        model: str | None = None,
        temperature: float = 0.7,
        seed: int = 42,
        dry_run: bool = False,
    ):
        self.seed_index = seed_index
        self.filler_pool = filler_pool
        self.model = model
        self.temperature = temperature
        self.rng = random.Random(seed)
        self.dry_run = dry_run
        self.validator = RuleValidator()

    def generate(self, spec: Dict) -> Dict:
        episode_id = spec["episode_id"]
        log.info(f"Generating {episode_id}: {spec['paradigm']}/{spec['condition']} "
                 f"({spec['domain']}/{spec['fact_type']})")

        sessions = []

        encoding_sessions = self._generate_encoding(spec)
        sessions.extend(encoding_sessions)

        n_total_fillers = spec["num_pre_perturbation_fillers"]
        n_near_miss = max(1, n_total_fillers // 4)
        n_generic = n_total_fillers - n_near_miss

        generic_fillers = self.filler_pool.draw(
            n=n_generic,
            exclude_topics=[spec["initial_value"], spec["new_value"],
                            spec["fact_type"].replace("_", " ")],
            domain=spec["domain"],
            rng=self.rng,
        )
        sessions.extend(generic_fillers)

        near_miss_fillers = self._generate_near_miss_fillers(spec, n_near_miss)
        sessions.extend(near_miss_fillers)

        perturbation = self._generate_perturbation(spec)
        sessions.append(perturbation)

        post_fillers = self.filler_pool.draw(
            n=spec["num_post_perturbation_fillers"],
            exclude_topics=[spec["initial_value"], spec["new_value"]],
            domain=spec["domain"],
            rng=self.rng,
        )
        sessions.extend(post_fillers)

        probes = self._generate_probes(spec)

        episode = {
            "episode_id": episode_id,
            "group_id": spec["group_id"],
            "latent_spec": spec,
            "sessions": sessions,
            "probes": probes,
        }

        validation_results = self.validator.validate_episode(episode, spec)
        episode["validation"] = {
            "rule_checks": [
                {"check": name, "passed": passed, "message": msg}
                for name, passed, msg in validation_results
            ],
            "all_passed": all(passed for _, passed, _ in validation_results),
        }

        passed_count = sum(1 for _, p, _ in validation_results if p)
        total_count = len(validation_results)
        log.info(f"  {episode_id}: validation {passed_count}/{total_count} passed")

        return episode

    def _generate_encoding(self, spec: Dict) -> List[Dict]:
        n = spec["num_encoding_sessions"]
        context_themes = select_context_themes(spec, self.rng)

        sessions = []
        for i in range(n):
            theme = context_themes[i] if i < len(context_themes) else "general"

            seed_ex = self.seed_index.get_example(
                spec["paradigm"], spec["condition"], spec["domain"], "encoding"
            )

            system, prompt = encoding_session_prompt(
                spec=spec,
                session_idx=i,
                context_theme=theme,
                seed_example=seed_ex,
            )

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] encoding session {i+1}, theme: {theme}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "encoding",
                "session_idx": i,
                "dialogue": dialogue,
                "metadata": {"context_theme": theme},
            })

        return sessions

    def _generate_perturbation(self, spec: Dict) -> Dict:
        seed_ex = self.seed_index.get_example(
            spec["paradigm"], spec["condition"], spec["domain"], "perturbation"
        )

        system, prompt = perturbation_session_prompt(
            spec=spec,
            seed_example=seed_ex,
        )

        if self.dry_run:
            dialogue = [{"role": "user", "content": f"[DRY RUN] perturbation: {spec['perturbation_type']}"}]
        else:
            raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
            dialogue = parse_dialogue(raw)

        return {
            "session_type": "perturbation",
            "dialogue": dialogue,
            "metadata": {
                "perturbation_type": spec["perturbation_type"],
                "condition": spec["condition"],
            },
        }

    def _generate_near_miss_fillers(self, spec: Dict, n: int) -> List[Dict]:
        sessions = []
        for i in range(n):
            seed_ex = self.seed_index.get_example(
                spec["paradigm"], spec["condition"], spec["domain"], "filler"
            )

            system, prompt = near_miss_filler_prompt(
                spec=spec,
                filler_idx=i,
                seed_example=seed_ex,
            )

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] near-miss filler {i+1}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "filler_near_miss",
                "dialogue": dialogue,
                "metadata": {"filler_idx": i},
            })

        return sessions

    def _generate_probes(self, spec: Dict) -> List[Dict]:
        readable_ft = FACT_TYPE_READABLE.get(
            spec["fact_type"], spec["fact_type"].replace("_", " ")
        )
        gold = spec["gold"]
        expected = spec["expected_behavior"]

        noise_val = (
            gold.get("noise_value")
            or gold.get("challenge_value")
            or gold.get("weak_evidence_value")
            or spec["new_value"]
        )

        def make_probe(pt: str) -> Dict:
            if pt == "current_value":
                return {
                    "probe_type": "current_value",
                    "question": f"What is the user's current {readable_ft}?",
                    "gold_answer": gold.get(
                        "current_value",
                        spec["new_value"] if expected == "should_update" else spec["initial_value"],
                    ),
                    "expected_behavior": expected,
                }
            if pt == "previous_value":
                q = (f"What was the user's {readable_ft} before the most recent change?"
                     if expected == "should_update"
                     else f"What {readable_ft} did the user originally state (before any challenge)?")
                return {
                    "probe_type": "previous_value",
                    "question": q,
                    "gold_answer": gold.get("previous_value", spec["initial_value"]),
                    "expected_behavior": expected,
                }
            if pt == "change_detection":
                gold_ans = (
                    f"Yes — changed from \"{spec['initial_value']}\" to \"{spec['new_value']}\""
                    if expected == "should_update"
                    else f"No — it remains \"{spec['initial_value']}\""
                )
                return {
                    "probe_type": "change_detection",
                    "question": (f"Has the user's {readable_ft} changed during our conversations?"
                                 if expected == "should_update"
                                 else f"Has the user's {readable_ft} changed?"),
                    "gold_answer": gold_ans,
                    "expected_behavior": expected,
                }
            if pt == "source":
                return {
                    "probe_type": "source",
                    "question": (f"How did we learn about the change in the user's {readable_ft}?"
                                 if expected == "should_update"
                                 else f"Who mentioned the alternative {readable_ft}, and does it apply?"),
                    "gold_answer": self._source_gold(spec) if expected == "should_update"
                                   else self._conflict_gold(spec, noise_val),
                    "expected_behavior": expected,
                }
            if pt == "conflict_value":
                return {
                    "probe_type": "conflict_value",
                    "question": f"Was any alternative {readable_ft} mentioned? If so, what was it and where did it come from?",
                    "gold_answer": self._conflict_gold(spec, noise_val),
                    "expected_behavior": expected,
                }
            if pt == "temporal":
                return {
                    "probe_type": "temporal",
                    "question": f"When or why did the user change their {readable_ft}?",
                    "gold_answer": gold.get("source_of_change") or
                                   (f"the user explicitly stated the switch from "
                                    f"\"{spec['initial_value']}\" to \"{spec['new_value']}\""),
                    "expected_behavior": expected,
                }
            raise ValueError(f"Unknown probe type '{pt}' in spec {spec.get('episode_id')}")

        spec_probes = spec.get("probes")
        if spec_probes:
            probe_types_to_generate = [p["type"] if isinstance(p, dict) else p
                                        for p in spec_probes]
        else:
            probe_types_to_generate = (["current_value", "previous_value", "source",
                                        "change_detection"] if expected == "should_update"
                                       else ["current_value", "previous_value",
                                             "conflict_value", "change_detection"])
        probes = [make_probe(pt) for pt in probe_types_to_generate]

        return probes

    @staticmethod
    def _source_gold(spec: Dict) -> str:
        condition = spec["condition"]

        if condition == "user_explicit" or condition == "standard":
            return "The user directly stated the change"
        elif condition == "reactivated":
            return "The user recalled the old value, then stated the change"
        elif condition == "direct":
            return "The user directly stated the new value without recalling the old"
        elif condition in ("high", "low"):
            return "The user directly stated the change"
        else:
            return "The user communicated the change"

    @staticmethod
    def _conflict_gold(spec: Dict, noise_val: str) -> str:
        condition = spec["condition"]

        source_desc = {
            "assistant_noise": "the assistant incorrectly stated",
            "third_party_noise": "a third party mentioned",
            "noise": "it was mentioned in passing about a different entity",
            "scope_restricted": "it was a real change but in a different scope",
            "high_challenge": "a non-authoritative source suggested",
            "low_challenge": "a non-authoritative source suggested",
            "reactivated_weak": "weak/unconfirmed evidence suggested",
        }

        desc = source_desc.get(condition, "conflicting information mentioned")
        return (
            f"Yes — \"{noise_val}\" was mentioned, but {desc}. "
            f"The user's {spec['fact_type'].replace('_', ' ')} remains \"{spec['initial_value']}\"."
        )


CONDITION_MAP = {
    "authoritative_update": "standard",
    "decoy_no_update": "noise",
}


def _compat_spec(spec: Dict) -> Dict:
    out = dict(spec)
    out["condition"] = CONDITION_MAP.get(spec["condition"], spec["condition"])
    return out


FILLER_TEMPLATES = {
    "current_gym": {
        "confusable": [
            "User's friend just joined {new_value} and describes their experience",
            "User reads an online review comparing {new_value} to other gyms in the area",
            "User helps a colleague pick a gym; {new_value} is one option they discuss",
        ],
        "decoy_nonupdate": [
            "User considered trying {new_value} after seeing a promotion, but decided to stick with {initial_value}",
            "User visited {new_value} for a guest pass day, but prefers {initial_value} for the group classes",
        ],
        "weakly_related_background": [
            "User asks about home workout routines for days they skip the gym",
            "User discusses workout nutrition and post-exercise protein intake",
            "User asks about recovery stretches after high-intensity sessions",
            "User asks about proper form for deadlifts or squats",
            "User asks about running shoes and whether to add cardio days",
            "User discusses fitness tracking apps and step goals",
        ],
        "near_miss_patterns": [
            "ask_for_recommendation",
            "compare_two_options",
            "check_schedule_conflict",
            "read_review",
        ],
    },
    "submission_deadline": {
        "confusable": [
            "A different conference's deadline is {new_value}; user helps a colleague plan for it",
            "User reads a call-for-papers where the deadline happens to be {new_value} — different venue",
            "User discusses an internal review milestone set for {new_value} — not the paper submission",
        ],
        "decoy_nonupdate": [
            "User mentions a rumor that the deadline might move to {new_value}, but confirms it is still {initial_value}",
            "User sees a stale tracker showing {new_value} but says the real deadline is {initial_value}",
        ],
        "weakly_related_background": [
            "User asks for help formatting references in the paper",
            "User coordinates with co-author on section assignments",
            "User asks about page limits and figure requirements",
            "User plans focused writing blocks for the week",
            "User discusses related work section organization",
            "User asks about submission portal account setup",
        ],
        "near_miss_patterns": [
            "check_tracker_confusion",
            "compare_two_project_dates",
            "summarize_meeting_notes",
            "draft_status_update",
        ],
    },
    "diet_preference": {
        "confusable": [
            "User's partner follows a {new_value} and user discusses their meal differences",
            "User reads an article about {new_value} health benefits — purely informational, not adopting",
            "User plans a dinner party with a friend who follows {new_value}",
        ],
        "decoy_nonupdate": [
            "User considered switching to {new_value} after reading a health article, but decided to stay {initial_value}",
            "User tried a {new_value} meal plan for one week but went back to {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about meal prep containers and batch cooking tips",
            "User discusses grocery shopping strategies on a budget",
            "User asks about hydration and daily water intake",
            "User discusses seasonal produce and farmers market finds",
            "User asks about cooking techniques for grains and legumes",
            "User discusses restaurant choices for an upcoming group dinner",
        ],
        "near_miss_patterns": [
            "ask_for_recommendation",
            "compare_two_options",
            "read_review",
            "check_schedule_conflict",
        ],
    },
    "project_owner": {
        "confusable": [
            "{new_value} is mentioned as owning a DIFFERENT module (payments), not authentication",
            "User discusses {new_value}'s recent tech talk — no ownership change implied",
            "{new_value} reviewed a PR on the auth module as a one-time favor, not as new owner",
        ],
        "decoy_nonupdate": [
            "Team considered having {new_value} take over auth, but decided to keep {initial_value} as owner",
            "There was a proposal to reassign auth to {new_value} during reorg, but it was rejected",
        ],
        "weakly_related_background": [
            "User discusses sprint planning and task assignment for the team",
            "User asks about code review turnaround time expectations",
            "User discusses CI/CD pipeline flakiness and how to fix it",
            "User asks about technical debt prioritization in the backlog",
            "User discusses onboarding a new team member",
            "User asks about documentation standards for internal APIs",
        ],
        "near_miss_patterns": [
            "ask_for_recommendation",
            "compare_two_options",
            "summarize_meeting_notes",
            "draft_status_update",
        ],
    },
    "config_value": {
        "confusable": [
            "A DIFFERENT service's timeout is set to {new_value} — user checks its config, not the target API",
            "User reads a best-practices article recommending {new_value} timeout for high-latency APIs — informational only",
            "User reviews a staging environment where timeout happens to be {new_value} — production is unchanged",
        ],
        "decoy_nonupdate": [
            "User considered bumping the timeout to {new_value} after seeing latency spikes, but kept it at {initial_value} after root-causing the issue",
            "A teammate proposed changing timeout to {new_value} in a PR, but user rejected the change and kept {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about retry strategy and exponential backoff configuration",
            "User discusses rate limiting and circuit breaker patterns",
            "User debugs a connection pool exhaustion issue",
            "User reviews error handling for upstream service failures",
            "User asks about health check endpoint configuration",
            "User discusses logging verbosity levels for API calls",
        ],
        "near_miss_patterns": [
            "compare_two_options",          
            "check_tracker_confusion",      
            "read_review",               
            "draft_status_update",        
        ],
    },
    "reported_port": {
        "confusable": [
            "A DIFFERENT service (e.g., the cache layer) runs on port {new_value} — not the user's API",
            "User reads documentation that references port {new_value} for a different microservice",
            "User checks a Docker compose file where an unrelated service maps to port {new_value}",
        ],
        "decoy_nonupdate": [
            "User considered moving the API to port {new_value} for consistency, but decided to keep it on {initial_value}",
            "A migration plan proposed moving to port {new_value}, but the team shelved it and kept {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about firewall rules and ingress configuration",
            "User discusses service discovery and DNS resolution",
            "User debugs a TLS certificate mismatch issue",
            "User reviews load balancer health check settings",
            "User asks about container networking and bridge mode",
            "User discusses monitoring and alerting for service uptime",
        ],
        "near_miss_patterns": [
            "check_schedule_conflict",    
            "compare_two_options",       
            "read_review",               
            "summarize_meeting_notes",    
        ],
    },
    "active_branch": {
        "confusable": [
            "A teammate is working on {new_value} — user discusses their teammate's PR, not their own branch",
            "User reviews a CI failure on the {new_value} branch — it belongs to a different team member",
            "User sees {new_value} in a branch listing and comments on it, but is not switching to it",
        ],
        "decoy_nonupdate": [
            "User thought about switching to {new_value} to help with a blocker, but decided to stay on {initial_value}",
            "User was asked to pick up work on {new_value}, but declined and stayed on {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about git rebase vs merge strategy for the team",
            "User discusses branch protection rules and required reviewers",
            "User debugs a CI pipeline failure unrelated to any specific branch",
            "User asks about cherry-picking a hotfix across release branches",
            "User discusses stale branch cleanup policy",
            "User asks about pre-commit hooks and linting configuration",
        ],
        "near_miss_patterns": [
            "ask_for_recommendation",    
            "compare_two_options",        
            "check_tracker_confusion",    
            "draft_status_update",        
        ],
    },
    "selected_database": {
        "confusable": [
            "A different microservice uses {new_value} — user discusses its setup, not the target project's DB",
            "User reads a benchmark comparing {new_value} performance — informational, not adopting it",
            "User helps a colleague troubleshoot their {new_value} instance — the user's own project is unaffected",
        ],
        "decoy_nonupdate": [
            "User evaluated {new_value} for the project but decided to stick with {initial_value} after benchmarking",
            "A team discussion proposed migrating to {new_value}, but the consensus was to keep {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about database indexing strategies and query optimization",
            "User discusses backup and disaster recovery procedures",
            "User debugs a slow query and reviews the execution plan",
            "User asks about connection pooling and max connections settings",
            "User discusses data migration tooling and schema versioning",
            "User asks about read replica setup and replication lag",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "summarize_meeting_notes",
            "check_tracker_confusion",
        ],
    },
    
   
    "current_gym_v2": {
        "confusable": [
            "User's friend just joined {new_value} and describes classes there",
            "User reads a review comparing {new_value} to other gyms",
            "User walks past {new_value} and comments on it",
        ],
        "decoy_nonupdate": [
            "User tried a guest pass at {new_value} but decided to stay with {initial_value}",
            "User saw a promo for {new_value} but is sticking with {initial_value}",
        ],
        "weakly_related_background": [
            "User discusses a new workout routine and asks for form tips",
            "User asks about protein intake and recovery timing",
            "User plans a weekend hike and asks about gear",
            "User asks about stretching routines for office workers",
            "User discusses tracking fitness progress with a smartwatch",
            "User asks about group fitness class etiquette",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "relay_friend_experience",
            "check_tracker_confusion",
        ],
    },
    "favorite_coffee": {
        "confusable": [
            "User's colleague recommends {new_value} and describes their roasts",
            "User reads an article ranking local coffee shops including {new_value}",
            "User passes by {new_value} and mentions it looks nice",
        ],
        "decoy_nonupdate": [
            "User tried {new_value} once but still prefers {initial_value}",
            "User considered switching to {new_value} but stayed with {initial_value} for the loyalty points",
        ],
        "weakly_related_background": [
            "User discusses the best coffee brewing methods at home",
            "User asks about caffeine content and its effects on sleep",
            "User plans a catch-up meeting with a friend at a cafe",
            "User asks about dairy-free milk alternatives for coffee",
            "User discusses remote work productivity tips",
            "User asks about local brunch spots for the weekend",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "relay_friend_experience",
            "summarize_meeting_notes",
        ],
    },
    "commute_method": {
        "confusable": [
            "User's roommate switched to {new_value} and describes the experience",
            "User reads an article about {new_value} commuting trends in their city",
            "User takes {new_value} for a one-off errand, not their regular commute",
        ],
        "decoy_nonupdate": [
            "User considered switching to {new_value} but decided {initial_value} is faster",
            "User tried {new_value} for a week but went back to {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about weather forecasts for the week",
            "User discusses time management and morning routines",
            "User asks about podcast recommendations for commute listening",
            "User plans a weekend trip and asks about transportation options",
            "User discusses workplace parking or bike storage policies",
            "User asks about noise-cancelling headphones for commuting",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "relay_friend_experience",
            "read_review",
            "check_tracker_confusion",
        ],
    },
    "diet_preference_v2": {
        "confusable": [
            "User's partner follows {new_value} and describes their meals",
            "User reads a nutrition article about {new_value} benefits",
            "User tries a {new_value} meal at a restaurant but hasn't switched",
        ],
        "decoy_nonupdate": [
            "User researched {new_value} but decided to stick with {initial_value}",
            "User's doctor mentioned {new_value} as an option but user chose to stay {initial_value}",
        ],
        "weakly_related_background": [
            "User asks for meal prep ideas for the upcoming week",
            "User discusses grocery shopping lists and budget tips",
            "User asks about vitamin supplements and nutrient tracking",
            "User discusses cooking techniques for meal variety",
            "User asks about food allergy management strategies",
            "User plans a dinner party and asks about menu ideas",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "relay_friend_experience",
            "summarize_meeting_notes",
        ],
    },
    "sleep_schedule": {
        "confusable": [
            "User's friend swears by a {new_value} bedtime and describes the benefits",
            "User reads a sleep study recommending {new_value} as optimal",
            "User mentions a podcast guest who advocates {new_value}",
        ],
        "decoy_nonupdate": [
            "User tried {new_value} for a few days but went back to {initial_value}",
            "User considered shifting to {new_value} but {initial_value} works better for their schedule",
        ],
        "weakly_related_background": [
            "User asks about morning routine optimization",
            "User discusses blue-light blocking glasses and screen time",
            "User asks about melatonin and natural sleep aids",
            "User discusses energy levels and afternoon fatigue",
            "User asks about bedroom temperature for better sleep",
            "User discusses weekend sleep schedule vs weekday routine",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "relay_friend_experience",
            "check_tracker_confusion",
        ],
    },
    "team_standup": {
        "confusable": [
            "Another team's standup is at {new_value} — user mentions it in passing",
            "User reads a blog about optimal standup times suggesting {new_value}",
            "A calendar glitch briefly showed the standup at {new_value} but was corrected",
        ],
        "decoy_nonupdate": [
            "Team discussed moving standup to {new_value} but decided to keep {initial_value}",
            "Manager proposed {new_value} but the team voted to stay with {initial_value}",
        ],
        "weakly_related_background": [
            "User asks about improving standup efficiency and format",
            "User discusses async standup tools vs synchronous meetings",
            "User plans their morning task priorities before standup",
            "User asks about meeting-free deep work blocks",
            "User discusses time zone challenges for distributed teams",
            "User asks about sprint retrospective formats",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "summarize_meeting_notes",
            "check_tracker_confusion",
            "relay_friend_experience",
        ],
    },
    "deploy_cadence": {
        "confusable": [
            "Another team deploys {new_value} — user discusses their process",
            "User reads a DevOps article recommending {new_value} deployments",
            "A conference talk advocated {new_value} cadence for smaller teams",
        ],
        "decoy_nonupdate": [
            "Team considered switching to {new_value} but decided {initial_value} is safer for now",
            "Platform team suggested {new_value} but user's team stayed with {initial_value}",
        ],
        "weakly_related_background": [
            "User discusses CI/CD pipeline optimization and build times",
            "User asks about feature flag strategies for gradual rollouts",
            "User discusses rollback procedures and incident response",
            "User asks about deployment monitoring and alerting setup",
            "User discusses canary deployments and traffic splitting",
            "User asks about release note automation",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "summarize_meeting_notes",
            "check_tracker_confusion",
        ],
    },
    "submission_deadline_v2": {
        "confusable": [
            "A colleague's report deadline is {new_value} — user mentions it",
            "User reads about a conference deadline of {new_value} for a different submission",
            "An old email references {new_value} as a deadline for a separate deliverable",
        ],
        "decoy_nonupdate": [
            "User heard a rumor the deadline moved to {new_value} but confirmed it's still {initial_value}",
            "Someone suggested extending to {new_value} but the manager confirmed {initial_value} stands",
        ],
        "weakly_related_background": [
            "User asks about report formatting and citation style",
            "User discusses section drafts and asks for feedback",
            "User plans a review session with co-authors",
            "User asks about document version control and collaboration tools",
            "User discusses data analysis approaches for the report",
            "User asks about presentation slides for the report findings",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "check_tracker_confusion",
            "summarize_meeting_notes",
            "relay_friend_experience",
        ],
    },
    "project_owner_v2": {
        "confusable": [
            "{new_value} reviewed some billing code — user discusses the review, not ownership",
            "User mentions {new_value} helped debug a billing issue as a one-off favor",
            "{new_value} presented billing metrics at a team meeting — doesn't mean they own the module",
        ],
        "decoy_nonupdate": [
            "There was a proposal to transfer billing to {new_value} but {initial_value} kept ownership",
            "During reorg discussions, {new_value} was considered but {initial_value} stayed as owner",
        ],
        "weakly_related_background": [
            "User discusses sprint planning and task assignments for the billing module",
            "User asks about code review best practices and turnaround times",
            "User discusses the billing module's API versioning strategy",
            "User asks about onboarding a new team member to the billing codebase",
            "User discusses billing module performance monitoring dashboards",
            "User asks about inter-team dependency management",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "summarize_meeting_notes",
            "check_tracker_confusion",
            "relay_friend_experience",
        ],
    },
    "ci_provider": {
        "confusable": [
            "Another team migrated to {new_value} — user discusses their experience",
            "User reads a comparison of {new_value} vs alternatives for CI",
            "A tech talk at the company demo'd {new_value} features — informational only",
        ],
        "decoy_nonupdate": [
            "Team evaluated {new_value} but decided to stick with {initial_value} for now",
            "A migration to {new_value} was planned but cancelled — still on {initial_value}",
        ],
        "weakly_related_background": [
            "User discusses build caching strategies and CI speed optimization",
            "User asks about automated testing in the CI pipeline",
            "User discusses secret management and CI credential rotation",
            "User asks about build artifact storage and versioning",
            "User discusses CI pipeline monitoring and failure alerting",
            "User asks about parallelizing test suites for faster feedback",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "summarize_meeting_notes",
            "check_tracker_confusion",
        ],
    },
    "log_level": {
        "confusable": [
            "A teammate runs {new_value} on their staging server — user discusses it",
            "User reads a blog about when to use {new_value} vs other log levels",
            "A runbook mentions {new_value} for incident debugging — not the default setting",
        ],
        "decoy_nonupdate": [
            "User considered switching to {new_value} for debugging but kept {initial_value} in production",
            "Team discussed enabling {new_value} temporarily but decided {initial_value} is sufficient",
        ],
        "weakly_related_background": [
            "User discusses structured logging formats and log aggregation",
            "User asks about log retention policies and storage costs",
            "User discusses distributed tracing and correlation IDs",
            "User asks about alerting thresholds based on error log patterns",
            "User discusses log sampling strategies for high-traffic services",
            "User asks about PII scrubbing in log output",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "check_tracker_confusion",
            "summarize_meeting_notes",
        ],
    },
    "config_value_v2": {
        "confusable": [
            "A blog recommends {new_value} as default — user reads it, doesn't adopt it",
            "Another service uses {new_value} — user discusses their setup",
            "User benchmarks {new_value} in a test environment but keeps {initial_value} in prod",
        ],
        "decoy_nonupdate": [
            "User tested {new_value} but saw no improvement — staying with {initial_value}",
            "SRE suggested {new_value} but user decided {initial_value} is appropriate for their SLA",
        ],
        "weakly_related_background": [
            "User discusses circuit breaker patterns and failure isolation",
            "User asks about backoff strategies for API retries",
            "User discusses timeout vs retry tradeoffs for upstream services",
            "User asks about rate limiting configuration and headers",
            "User discusses API error handling and response codes",
            "User asks about load testing and capacity planning",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "check_tracker_confusion",
            "summarize_meeting_notes",
        ],
    },
    "reported_port_v2": {
        "confusable": [
            "A different database service runs on {new_value} — user discusses its setup",
            "User reads a security guide mentioning port {new_value} for a different protocol",
            "User sees port {new_value} in an old config file for a deprecated service",
        ],
        "decoy_nonupdate": [
            "User considered migrating to port {new_value} but kept {initial_value} for compatibility",
            "A teammate suggested {new_value} but the team stuck with {initial_value}",
        ],
        "weakly_related_background": [
            "User discusses database connection pooling and connection limits",
            "User asks about firewall rules and network security groups",
            "User discusses database backup automation and restore testing",
            "User asks about TLS configuration for database connections",
            "User discusses monitoring database latency and query performance",
            "User asks about multi-region database replication setup",
        ],
        "near_miss_patterns": [
            "compare_two_options",
            "read_review",
            "check_tracker_confusion",
            "relay_friend_experience",
        ],
    },
}


def _substitute_template(template: str, initial_value: str, new_value: str) -> str:
    out = template
    for alias in ["{new_value}", "{new_value_date}", "{new_owner}"]:
        out = out.replace(alias, new_value)
    for alias in ["{initial_value}", "{initial_value_date}", "{old_owner}"]:
        out = out.replace(alias, initial_value)
    return out


def confusable_filler_prompt(
    spec: Dict, scenario_template: str, filler_idx: int
) -> Tuple[str, str]:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    new_value = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))
    scenario = _substitute_template(scenario_template, initial_value, new_value)

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating a CONFUSABLE FILLER session.\n\n"
        "A confusable filler MENTIONS the same value as the target fact's new value, "
        "BUT IN A WRONG RELATION OR CONTEXT — the value appears in the dialogue, "
        "but the user's actual fact has NOT changed.\n\n"
        "CRITICAL RULES:\n"
        f"1. The new_value MUST appear naturally in the conversation: '{new_value}'\n"
        "2. The new_value must appear in a context that is NOT an update to the user's "
        f"{readable_ft}\n"
        f"3. Do NOT update or imply that the user's own {readable_ft} has "
        f"changed from '{initial_value}' to '{new_value}'\n"
        "4. Natural conversational tone\n"
        "5. Keep it short: 3-5 turns total (1 turn = 1 user msg + 1 assistant msg)\n"
    )

    prompt = f"""Generate a confusable filler session.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Target fact type:** {readable_ft}
**User's actual fact:** "{initial_value}" (UNCHANGED)
**Value to MENTION in wrong context:** "{new_value}"
**Filler index:** {filler_idx + 1}

**Scenario:** {scenario}

**Requirements:**
- 3-5 turns total (1 turn = user + assistant). Do NOT exceed 5 turns.
- "{new_value}" MUST appear at least once, naturally
- The mention must be clearly about a different entity/context
- Do NOT reaffirm the user's actual fact explicitly (keep it implicit)

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 3-5 turns)
"""
    return system, prompt


def decoy_nonupdate_filler_prompt(
    spec: Dict, decoy_template: str, filler_idx: int
) -> Tuple[str, str]:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    new_value = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))
    decoy_text = _substitute_template(decoy_template, initial_value, new_value)

    rejection_examples = {
        "personal": (
            f"'Nah, I'm sticking with {initial_value}.' or "
            f"'I looked into it but {initial_value} suits me better.'"
        ),
        "work": (
            f"'We discussed it but decided not to change — {initial_value} stays.' or "
            f"'That was just a one-off; {initial_value} is still the owner.'"
        ),
        "agentic": (
            f"'We benchmarked it but {initial_value} performed better — keeping it.' or "
            f"'Rolled back the change; {initial_value} is what we're using.'"
        ),
    }
    example = rejection_examples.get(domain, rejection_examples["personal"])

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating a DECOY-NONUPDATE FILLER session.\n\n"
        "A decoy-nonupdate filler brings up a potential change, but the user "
        "REJECTS it in ONE concise sentence and moves on.\n\n"
        "CRITICAL RULES:\n"
        f"1. '{new_value}' MUST appear in the conversation\n"
        f"2. The user rejects the change in exactly ONE natural sentence — "
        f"e.g., {example}\n"
        "3. The rejection must sound natural for this domain. Do NOT use "
        "generic phrases like 'works fine for me' for work/ownership topics.\n"
        "4. Do NOT repeat the rejection. Do NOT have the user explain, "
        "justify, or re-clarify why they are not switching. One sentence, "
        "then the conversation moves to something else or ends.\n"
        "5. Keep it short: 2-4 turns total (1 turn = 1 user msg + 1 assistant msg)\n"
    )

    prompt = f"""Generate a decoy-nonupdate filler session.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Target fact type:** {readable_ft}
**User's actual fact (stays in force):** "{initial_value}"
**Value mentioned but REJECTED:** "{new_value}"
**Filler index:** {filler_idx + 1}

**Decoy framing:** {decoy_text}

**Requirements:**
- 2-4 turns total (1 turn = user + assistant). Do NOT exceed 4 turns.
- "{new_value}" MUST appear once, naturally
- The user rejects it in ONE short sentence and does not revisit the topic
- No triple-emphasis, no multi-turn justification — just one clear "no" and move on
- The assistant should acknowledge briefly and NOT probe further about the rejected option

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 2-4 turns)
"""
    return system, prompt


def weakly_related_filler_prompt(
    spec: Dict, topic: str, filler_idx: int
) -> Tuple[str, str]:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    new_value = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))
    domain_labels = {
        "personal": "fitness / health / lifestyle",
        "work": "work / team / engineering",
        "agentic": "dev tools / infrastructure / configs / git / databases",
    }
    domain_label = domain_labels.get(domain, "work / team / engineering")

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating a WEAKLY-RELATED BACKGROUND filler — a conversation "
        "that stays STRICTLY within the user's domain but discusses a DIFFERENT "
        "topic with LOW relevance to the target fact.\n\n"
        "CRITICAL RULES:\n"
        f"1. MUST NOT mention '{initial_value}' or '{new_value}'\n"
        f"2. MUST NOT reference the user's {readable_ft}\n"
        f"3. MUST stay within the domain: {domain_label}. "
        "Do NOT drift to unrelated domains (e.g., no climate policy, ESG, "
        "ecology, national parks, etc. for a fitness topic).\n"
        "4. Keep it short: 2-4 turns total (1 turn = 1 user msg + 1 assistant msg)\n"
        "5. Natural, self-contained conversation\n"
    )

    prompt = f"""Generate a weakly-related background filler session.

**Domain:** {domain} ({domain_label})
**Domain style:** {DOMAIN_STYLE[domain]}
**Topic to discuss:** {topic}
**Values to AVOID:** "{initial_value}", "{new_value}"
**Filler index:** {filler_idx + 1}

**Requirements:**
- 2-4 turns total (1 turn = user + assistant). Do NOT exceed 4 turns.
- The conversation MUST be about {domain_label} topics.
- Natural and self-contained — the user asks about "{topic}" and the assistant helps.
- MUST NOT mention the target fact values or anything that could be confused with them.

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 2-4 turns)
"""
    return system, prompt


def stale_reference_filler_prompt(
    spec: Dict, filler_idx: int
) -> Tuple[str, str]:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    new_value = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))
    expected = spec.get("expected_behavior", "")

   

    if expected == "should_update":
        stale_val = initial_value
        correct_val = new_value
        stale_context = (
            f"An outdated document, tracker, or wiki page still shows "
            f"'{stale_val}' as the {readable_ft}. The user notices it's "
            f"stale but does NOT correct it in this session — they just "
            f"note the discrepancy or move on."
        )
    else:
        stale_val = new_value
        correct_val = initial_value
        stale_context = (
            f"An old planning doc, proposal, or tracker entry shows "
            f"'{stale_val}' as a planned/proposed {readable_ft}. The user "
            f"encounters it but it was never actually adopted — the real "
            f"value is still '{correct_val}'."
        )

    domain_labels = {
        "personal": "fitness / health / lifestyle",
        "work": "work / team / engineering",
        "agentic": "dev tools / infrastructure / configs / git / databases",
    }
    domain_label = domain_labels.get(domain, domain)

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating a STALE-REFERENCE filler session.\n\n"
        "A stale-reference filler shows an OUTDATED document, tracker, wiki, "
        "spreadsheet, or cached entry that displays a value which is NOT "
        "the current ground truth. The user encounters this stale data "
        "but does NOT resolve it in this session.\n\n"
        "CRITICAL RULES:\n"
        f"1. The stale value '{stale_val}' MUST appear naturally\n"
        "2. The source must be clearly a document/tracker/system, not a person\n"
        "3. The user should notice or mention the entry but NOT update it\n"
        "4. Do NOT have the user explicitly state what the correct value is\n"
        "5. Keep it short: 2-4 turns total (1 turn = 1 user msg + 1 assistant msg)\n"
    )

    prompt = f"""Generate a stale-reference filler session.

**Domain:** {domain} ({domain_label})
**Domain style:** {DOMAIN_STYLE[domain]}
**Target fact type:** {readable_ft}
**Stale value shown in old doc/tracker:** "{stale_val}"
**Context:** {stale_context}
**Filler index:** {filler_idx + 1}

**Requirements:**
- 2-4 turns total. Do NOT exceed 4 turns.
- The stale entry must come from a document, wiki, tracker, spreadsheet, dashboard,
  or cached system — NOT from a person's statement.
- The user notices or references the entry without resolving the discrepancy.
- Do NOT have the user state the correct value explicitly.

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 2-4 turns)
"""
    return system, prompt


class PilotGenerator:
    def __init__(self, model: str = "gpt-5", temperature: float = 0.7,
                 seed: int = 42, dry_run: bool = False):
        self.model = model
        self.temperature = temperature
        self.rng = random.Random(seed)
        self.dry_run = dry_run

    def generate(self, spec: Dict) -> Dict:
        eid = spec["episode_id"]
        log.info(f"Generating {eid}: {spec['paradigm']}/{spec['condition']} "
                 f"({spec['domain']}/{spec['fact_type']})")

        sessions = []
        compat = _compat_spec(spec)

        encoding_sessions = self._generate_encoding(spec, compat)
        sessions.extend(encoding_sessions)

        fp = spec["filler_plan"]["pre_perturbation"]
        fact_type = spec["fact_type"]
        templates = FILLER_TEMPLATES.get(fact_type, {})

        bg_topics = templates.get("weakly_related_background", [])
        bg_fillers = self._generate_weakly_related(spec, fp.get("weakly_related_background", 0), bg_topics)

        nm_fillers = self._generate_near_miss(spec, compat, fp.get("near_miss", 0))

        conf_templates = templates.get("confusable", [])
        conf_fillers = self._generate_confusable(spec, fp.get("confusable", 0), conf_templates)

        decoy_templates = templates.get("decoy_nonupdate", [])
        decoy_fillers = self._generate_decoy(spec, fp.get("decoy_nonupdate", 0), decoy_templates)

    
        pre_block = bg_fillers + nm_fillers + conf_fillers + decoy_fillers
        self.rng.shuffle(pre_block)
        sessions.extend(pre_block)

        split_pert = spec.get("split_perturbation")
        if split_pert:
            p1 = self._generate_split_p1(spec, compat)
            sessions.append(p1)

            interleave_n = split_pert.get("interleave_fillers", 2)
            interleave_types = split_pert.get("interleave_types", ["confusable", "near_miss"])
            for it in interleave_types[:interleave_n]:
                if it == "confusable":
                    il_templates = conf_templates[len(conf_fillers):] or conf_templates[:1]
                    sessions.extend(self._generate_confusable(spec, 1, il_templates))
                elif it == "near_miss":
                    sessions.extend(self._generate_near_miss(spec, compat, 1))
                elif it == "decoy_nonupdate":
                    il_decoy = decoy_templates[len(decoy_fillers):] or decoy_templates[:1]
                    sessions.extend(self._generate_decoy(spec, 1, il_decoy))

            p2 = self._generate_split_p2(spec, compat)
            sessions.append(p2)
        else:
            perturbation = self._generate_perturbation(spec, compat)
            sessions.append(perturbation)

        post_plan = spec["filler_plan"]["post_perturbation"]
        post_n = post_plan["total"]
        post_types = post_plan.get("types", ["weakly_related_background", "near_miss"])

        post_fillers = []
        for pt in post_types:
            if len(post_fillers) >= post_n:
                break
            if pt == "weakly_related_background":
                remaining_topics = bg_topics[len(bg_fillers):] if len(bg_topics) > len(bg_fillers) else ["general follow-up"]
                post_fillers += self._generate_weakly_related(spec, 1, remaining_topics)
            elif pt == "near_miss":
                post_fillers += self._generate_near_miss(spec, compat, 1)
            elif pt == "confusable":
                post_conf_templates = conf_templates[len(conf_fillers):] if len(conf_templates) > len(conf_fillers) else conf_templates[:1]
                post_fillers += self._generate_confusable(spec, 1, post_conf_templates)
            elif pt == "decoy_nonupdate":
                post_decoy_templates = decoy_templates[len(decoy_fillers):] if len(decoy_templates) > len(decoy_fillers) else decoy_templates[:1]
                post_fillers += self._generate_decoy(spec, 1, post_decoy_templates)
            elif pt == "stale_reference":
                post_fillers += self._generate_stale_reference(spec, len(post_fillers))

        
        while len(post_fillers) < post_n:
            post_fillers += self._generate_near_miss(spec, compat, 1)

        sessions.extend(post_fillers[:post_n])

        probes = self._build_probes(spec)

        episode = {
            "episode_id": eid,
            "group_id": spec["group_id"],
            "paradigm": spec["paradigm"],
            "condition": spec["condition"],
            "expected_behavior": spec["expected_behavior"],
            "latent_spec": spec,
            "sessions": sessions,
            "probes": probes,
            "metadata": {
                "total_sessions": len(sessions),
                "length_tier": spec["length_tier"],
                "model": self.model,
            },
        }

        log.info(f"  {eid}: {len(sessions)} sessions, {len(probes)} probes")
        return episode

    def _generate_encoding(self, spec: Dict, compat: Dict) -> List[Dict]:
        n = spec["num_encoding_sessions"]
        mention_contexts = spec.get("encoding", {}).get("mention_contexts", [])
        context_themes = select_context_themes(compat, self.rng)

        sessions = []
        for i in range(n):
            
            if i < len(mention_contexts):
                theme = mention_contexts[i]
            elif i < len(context_themes):
                theme = context_themes[i]
            else:
                theme = "general"

            system, prompt = encoding_session_prompt(
                spec=compat, session_idx=i, context_theme=theme, seed_example=None,
            )

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] encoding {i+1}: {theme}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "encoding",
                "session_idx": i,
                "dialogue": dialogue,
                "metadata": {"context_theme": theme},
            })
        return sessions

    def _generate_perturbation(self, spec: Dict, compat: Dict) -> Dict:
        system, prompt = perturbation_session_prompt(spec=compat, seed_example=None)


        wording_hint = spec.get("perturbation", {}).get("wording_hint", "")
        if wording_hint:
            prompt += f"\n**Additional guidance:** {wording_hint}\n"

        if self.dry_run:
            dialogue = [{"role": "user", "content": f"[DRY RUN] perturbation: {spec['condition']}"}]
        else:
            raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
            dialogue = parse_dialogue(raw)

        return {
            "session_type": "perturbation",
            "dialogue": dialogue,
            "metadata": {
                "perturbation_type": spec["perturbation_type"],
                "condition": spec["condition"],
                "source_type": spec.get("perturbation", {}).get("source_type", ""),
            },
        }

    def _generate_split_p1(self, spec: Dict, compat: Dict) -> Dict:
        readable_ft = FACT_TYPE_READABLE.get(spec["fact_type"],
                                              spec["fact_type"].replace("_", " "))
        initial = spec["initial_value"]
        new = spec["new_value"]
        split_cfg = spec["split_perturbation"]
        p1_hint = split_cfg.get("p1_hint", "")

        domain = spec["domain"]
        agentic_note = ""
        if domain == "agentic":
            agentic_note = (
                "\n**AGENTIC DOMAIN**: Include [TOOL_OUTPUT] blocks where appropriate.\n"
            )

        system = (
            "You are a dialogue writer for the MemProbe agent memory testbed. "
            "You are generating PERTURBATION PART 1 (P1) — the first half of a "
            "split perturbation.\n\n"
            "P1 establishes that a change to the target fact happened and WHY, "
            "but does NOT explicitly state the new value. The new value will be "
            "confirmed in a separate later session (P2).\n\n"
            "CRITICAL RULES:\n"
            f"1. MUST mention or imply that '{initial}' is no longer current\n"
            f"2. MUST establish the trigger/reason for the change\n"
            f"3. MUST NOT explicitly state '{new}' as the new value\n"
            "4. May hint at the new value vaguely (e.g., 'the one closer to "
            "home', 'the later slot') but NOT name it\n"
            "5. 3-5 turns total (1 turn = user + assistant)\n"
        )

        prompt = f"""Generate perturbation P1 for the MemProbe testbed.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Fact type:** {readable_ft}
**Old value (being replaced):** "{initial}"
**New value (DO NOT state explicitly):** "{new}" — you know this for context but MUST NOT write it in the dialogue
{agentic_note}
**P1 guidance:** {p1_hint}

**Requirements:**
- The user communicates that a change happened to their {readable_ft}
- The trigger/reason for the change is clear
- The exact new value ("{new}") is NEVER stated — only vague references allowed
- 3-5 turns total. Do NOT exceed 5 turns.
- Natural, conversational tone

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 3-5 turns)
"""
        if self.dry_run:
            dialogue = [{"role": "user",
                         "content": f"[DRY RUN] split P1: {spec['condition']}"}]
        else:
            raw = call_llm(system, prompt, model=self.model,
                           temperature=self.temperature)
            dialogue = parse_dialogue(raw)

        return {
            "session_type": "perturbation_p1",
            "dialogue": dialogue,
            "metadata": {
                "perturbation_type": spec["perturbation_type"],
                "condition": spec["condition"],
                "split_role": "p1_trigger_reason",
            },
        }

    def _generate_split_p2(self, spec: Dict, compat: Dict) -> Dict:
        readable_ft = FACT_TYPE_READABLE.get(spec["fact_type"],
                                              spec["fact_type"].replace("_", " "))
        initial = spec["initial_value"]
        new = spec["new_value"]
        split_cfg = spec["split_perturbation"]
        p2_hint = split_cfg.get("p2_hint", "")

        domain = spec["domain"]
        agentic_note = ""
        if domain == "agentic":
            agentic_note = (
                "\n**AGENTIC DOMAIN**: Include [TOOL_OUTPUT] blocks where appropriate.\n"
            )

        system = (
            "You are a dialogue writer for the MemProbe agent memory testbed. "
            "You are generating PERTURBATION PART 2 (P2) — the second half of a "
            "split perturbation.\n\n"
            "P2 confirms the new value in a natural follow-up context. An earlier "
            "session (P1) already established that a change happened. P2 mentions "
            "the new value casually, as something the user is now acting on.\n\n"
            "CRITICAL RULES:\n"
            f"1. MUST mention '{new}' as the current value, but casually — "
            "not as a dramatic announcement\n"
            f"2. MUST NOT repeat the full trigger/reason story from P1\n"
            f"3. SHOULD refer to '{new}' as something already decided/in-use\n"
            "4. Keep it short: 2-4 turns total (1 turn = user + assistant)\n"
            f"5. MUST NOT re-mention '{initial}' — the old value should not "
            "appear in P2\n"
        )

        prompt = f"""Generate perturbation P2 for the MemProbe testbed.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Fact type:** {readable_ft}
**New value (now in use):** "{new}"
**Old value (DO NOT mention):** "{initial}"
{agentic_note}
**P2 guidance:** {p2_hint}

**Requirements:**
- The user references '{new}' casually as their current {readable_ft}
- This is a follow-up action: updating a calendar, asking about logistics,
  telling a friend, ordering something related, etc.
- Do NOT re-announce the change — treat it as already settled
- Do NOT mention the old value '{initial}'
- 2-4 turns total. Do NOT exceed 4 turns.
- Natural, task-oriented tone

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue for 2-4 turns)
"""
        if self.dry_run:
            dialogue = [{"role": "user",
                         "content": f"[DRY RUN] split P2: {spec['condition']}"}]
        else:
            raw = call_llm(system, prompt, model=self.model,
                           temperature=self.temperature)
            dialogue = parse_dialogue(raw)

        return {
            "session_type": "perturbation_p2",
            "dialogue": dialogue,
            "metadata": {
                "perturbation_type": spec["perturbation_type"],
                "condition": spec["condition"],
                "split_role": "p2_new_value",
            },
        }

    DISCOURSE_PATTERNS = {
        "ask_for_recommendation": (
            "The user asks the assistant for a recommendation related to the "
            "target domain (e.g., 'can you recommend a gym for my friend?'). "
            "The assistant provides options/advice. Conversational, helpful tone."
        ),
        "compare_two_options": (
            "The user compares two options for someone else or a hypothetical "
            "(e.g., 'which is better: X or Y for my cousin?'). Discussion-style, "
            "pros and cons."
        ),
        "check_schedule_conflict": (
            "The user checks a schedule, date, or logistics for a DIFFERENT "
            "entity (e.g., 'when does the yoga class start at Z?'). "
            "Short, task-oriented exchange."
        ),
        "check_tracker_confusion": (
            "The user looks at a tracker, dashboard, or list and asks about "
            "an entry that is NOT the target fact (e.g., 'what's the status "
            "of the other deliverable?'). Clarification-style dialogue."
        ),
        "read_review": (
            "The user reads or discusses a review/article about a related but "
            "different entity (e.g., 'I saw this review of Z — interesting'). "
            "Commentary and reaction."
        ),
        "summarize_meeting_notes": (
            "The user asks the assistant to summarize notes from a meeting "
            "where a DIFFERENT entity/project was discussed. Brief recap format."
        ),
        "draft_status_update": (
            "The user drafts a status update or message about a DIFFERENT "
            "project or team. Collaborative writing style."
        ),
        "compare_two_project_dates": (
            "The user compares timelines or deadlines for two DIFFERENT "
            "projects (neither is the target fact). Planning conversation."
        ),
    }

    def _generate_near_miss(self, spec: Dict, compat: Dict, n: int) -> List[Dict]:
        sessions = []
        fact_type = spec["fact_type"]
        templates = FILLER_TEMPLATES.get(fact_type, {})
        patterns = templates.get("near_miss_patterns", [])

        
        if patterns:
            shuffled_patterns = list(patterns)
            self.rng.shuffle(shuffled_patterns)
        else:
            shuffled_patterns = list(self.DISCOURSE_PATTERNS.keys())
            self.rng.shuffle(shuffled_patterns)

        for i in range(n):
            system, prompt = near_miss_filler_prompt(spec=compat, filler_idx=i, seed_example=None)

            pattern_key = shuffled_patterns[i % len(shuffled_patterns)]
            pattern_desc = self.DISCOURSE_PATTERNS.get(pattern_key, "Natural conversation")

            prompt += (
                f"\n**Discourse pattern:** {pattern_key}\n"
                f"  {pattern_desc}\n\n"
                "**Turn limit:** 3-5 turns total (1 turn = user + assistant). "
                "Do NOT exceed 5 turns.\n\n"
                "**Diversity constraint:** Do NOT use a generic template like "
                "'I'm helping X team coordinate Y' for every filler. Each near-miss "
                "session should feel like a distinct, natural conversation following "
                "the discourse pattern above.\n"
            )

            distractors = spec.get("distractor_values", [])
            if distractors:
                prompt += f"\n**Distractor values you may use (for the different entity):** {', '.join(distractors)}\n"

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] near-miss filler {i+1}: {pattern_key}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "filler_near_miss",
                "dialogue": dialogue,
                "metadata": {"filler_idx": i, "discourse_pattern": pattern_key},
            })
        return sessions

    def _generate_confusable(self, spec: Dict, n: int, templates: List[str]) -> List[Dict]:
        sessions = []
        for i in range(n):
            template = templates[i % len(templates)] if templates else \
                f"{{new_value}} is mentioned in passing about a different context"
            system, prompt = confusable_filler_prompt(spec, template, i)

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] confusable filler {i+1}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "filler_confusable",
                "dialogue": dialogue,
                "metadata": {"filler_idx": i, "template": template},
            })
        return sessions

    def _generate_decoy(self, spec: Dict, n: int, templates: List[str]) -> List[Dict]:
        sessions = []
        for i in range(n):
            template = templates[i % len(templates)] if templates else \
                f"User considered {{new_value}} but decided against it"
            system, prompt = decoy_nonupdate_filler_prompt(spec, template, i)

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] decoy filler {i+1}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "filler_decoy_nonupdate",
                "dialogue": dialogue,
                "metadata": {"filler_idx": i, "template": template},
            })
        return sessions

    def _generate_weakly_related(self, spec: Dict, n: int, topics: List[str]) -> List[Dict]:
        sessions = []
        for i in range(n):
            topic = topics[i % len(topics)] if topics else "general domain conversation"
            system, prompt = weakly_related_filler_prompt(spec, topic, i)

            if self.dry_run:
                dialogue = [{"role": "user", "content": f"[DRY RUN] background filler {i+1}: {topic}"}]
            else:
                raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
                dialogue = parse_dialogue(raw)

            sessions.append({
                "session_type": "filler_weakly_related",
                "dialogue": dialogue,
                "metadata": {"filler_idx": i, "topic": topic},
            })
        return sessions

    def _generate_stale_reference(self, spec: Dict, filler_idx: int) -> List[Dict]:
        system, prompt = stale_reference_filler_prompt(spec, filler_idx)

        if self.dry_run:
            dialogue = [{"role": "user", "content": f"[DRY RUN] stale-reference filler {filler_idx+1}"}]
        else:
            raw = call_llm(system, prompt, model=self.model, temperature=self.temperature)
            dialogue = parse_dialogue(raw)

        return [{
            "session_type": "filler_stale_reference",
            "dialogue": dialogue,
            "metadata": {"filler_idx": filler_idx},
        }]

    def _build_probes(self, spec: Dict) -> List[Dict]:
        gold = spec["gold"]
        expected = spec["expected_behavior"]
        probes = []

        for probe_def in spec.get("probes", []):
            probe = {
                "probe_type": probe_def["type"],
                "question": probe_def["question_hint"],
                "expected_behavior": expected,
            }

            ptype = probe_def["type"]
            if ptype == "current_value":
                probe["gold_answer"] = gold["current_value"]
            elif ptype == "previous_value":
                probe["gold_answer"] = gold.get("previous_value") or gold.get("original_value", "")
            elif ptype == "change_detection":
                if gold["has_changed"]:
                    probe["gold_answer"] = (
                        f"Yes — changed from \"{gold.get('original_value', '')}\" "
                        f"to \"{gold['current_value']}\""
                    )
                else:
                    probe["gold_answer"] = f"No — it remains \"{gold['current_value']}\""
            elif ptype == "temporal":
                tg = gold.get("temporal_gold")
                if tg and isinstance(tg, dict):
                    parts = []
                    if tg.get("old_value") and tg.get("new_value"):
                        parts.append(f"Changed from \"{tg['old_value']}\" to \"{tg['new_value']}\".")
                    if tg.get("trigger"):
                        parts.append(f"Trigger: {tg['trigger']}.")
                    if tg.get("reason"):
                        parts.append(f"Reason: {tg['reason']}.")
                    probe["gold_answer"] = " ".join(parts) if parts else gold.get("source_of_change", "")
                else:
                    probe["gold_answer"] = gold.get("source_of_change", "")
            elif ptype == "source":
                if "gold_hint" in probe_def:
                    probe["gold_answer"] = probe_def["gold_hint"]
                else:
                    probe["gold_answer"] = gold.get("source_of_change", "")
            elif ptype == "conflict_value":
                invalid = gold.get("invalid_sources", [])
                if invalid:
                    probe["gold_answer"] = (
                        f"Yes — \"{spec['canonical_new']}\" was mentioned, but from an "
                        f"invalid source ({', '.join(invalid)}). The user's "
                        f"{spec['fact_type'].replace('_', ' ')} remains \"{gold['current_value']}\"."
                    )
                else:
                    probe["gold_answer"] = "No conflicting information."

            probes.append(probe)

        return probes


def load_specs(path: str) -> List[Dict]:
    data = json.loads(Path(path).read_text())
    return data["specs"]


def run_generation(
    specs_path: str,
    output_path: str,
    seed_path: Optional[str] = None,
    filler_pool_path: Optional[str] = None,
    model: str | None = None,
    temperature: float = 0.7,
    seed: int = 42,
    dry_run: bool = False,
    limit: Optional[int] = None,
    episode_ids: Optional[List[str]] = None,
    filler_mode: str = "templated",
):
    specs = load_specs(specs_path)
    log.info(f"Loaded {len(specs)} latent specs from {specs_path}")

    if episode_ids:
        specs = [s for s in specs if s["episode_id"] in set(episode_ids)]
        log.info(f"Filtered to {len(specs)} specified episodes")

    if limit:
        specs = specs[:limit]
        log.info(f"Limited to first {limit} specs")

    if filler_mode == "pool":
        seed_index = SeedSkeletonIndex(seed_path)
        log.info(f"Loaded {len(seed_index.seeds)} seed skeleton examples")
        filler_pool = FillerPool(filler_pool_path)
        generator = EpisodeGenerator(seed_index=seed_index, filler_pool=filler_pool, model=model,
                                     temperature=temperature, seed=seed, dry_run=dry_run)
    else:
        generator = PilotGenerator(model=model or "gpt-5.4", temperature=temperature, seed=seed, dry_run=dry_run)
    log.info(f"filler mode: {filler_mode} ({generator.__class__.__name__})")

    output = Path(output_path)
    existing_episodes = {}
    if output.exists() and not dry_run:
        with output.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    ep = json.loads(line)
                    existing_episodes[ep["episode_id"]] = ep
        if existing_episodes:
            log.info(f"Resume mode: found {len(existing_episodes)} existing episodes in {output_path}")

    episodes = list(existing_episodes.values())
    generated_ids = set(existing_episodes.keys())
    failed = []
    newly_generated = 0

    for i, spec in enumerate(specs):
        eid = spec["episode_id"]

        if eid in generated_ids:
            log.info(f"[{i+1}/{len(specs)}] Skipping {eid} (already generated)")
            continue

        log.info(f"[{i+1}/{len(specs)}] Processing {eid}...")

        try:
            episode = generator.generate(spec)
            episodes.append(episode)
            generated_ids.add(eid)
            newly_generated += 1

            val = episode.get("validation") or {}
            if val and not val.get("all_passed", True):
                failed_checks = [c for c in val.get("rule_checks", []) if not c.get("passed")]
                log.warning(
                    f"  {eid}: {len(failed_checks)} checks failed: "
                    + ", ".join(c["check"] for c in failed_checks)
                )
                failed.append(eid)

        except Exception as e:
            log.error(f"  {eid}: generation failed: {e}")
            failed.append(eid)
            continue

        if not dry_run:
            with output.open("a") as f:
                f.write(json.dumps(episode, ensure_ascii=False) + "\n")

        if not dry_run and i < len(specs) - 1:
            time.sleep(0.5)

    if dry_run or not existing_episodes:
        with output.open("w") as f:
            for ep in episodes:
                f.write(json.dumps(ep, ensure_ascii=False) + "\n")

    log.info(f"\nGeneration complete:")
    log.info(f"  Total specs: {len(specs)}")
    log.info(f"  Already existed: {len(existing_episodes)}")
    log.info(f"  Newly generated: {newly_generated}")
    log.info(f"  Failed:      {len(failed)}")
    if failed:
        log.info(f"  Failed IDs:  {failed}")
    log.info(f"  Output:      {output_path}")

    if episodes:
        passed = sum(1 for e in episodes if e.get("validation", {}).get("all_passed"))
        log.info(f"  Validation:  {passed}/{len(episodes)} all-checks-passed")


def run_validation(
    input_path: str,
    specs_path: str,
):
    specs_data = json.loads(Path(specs_path).read_text())
    specs_by_id = {s["episode_id"]: s for s in specs_data["specs"]}

    validator = RuleValidator()
    total = 0
    passed = 0
    failed_episodes = []

    with open(input_path) as f:
        for line in f:
            episode = json.loads(line)
            episode_id = episode["episode_id"]
            spec = specs_by_id.get(episode_id)
            if not spec:
                log.warning(f"No spec found for {episode_id}, skipping")
                continue

            results = validator.validate_episode(episode, spec)
            total += 1
            all_ok = all(p for _, p, _ in results)
            if all_ok:
                passed += 1
            else:
                failed_checks = [(n, m) for n, p, m in results if not p]
                failed_episodes.append((episode_id, failed_checks))
                log.warning(f"{episode_id}: FAILED — {[n for n, _ in failed_checks]}")

    log.info(f"\nValidation complete: {passed}/{total} episodes passed all checks")
    if failed_episodes:
        log.info(f"Failed episodes:")
        for eid, checks in failed_episodes:
            for name, msg in checks:
                log.info(f"  {eid}: [{name}] {msg}")


def main():
    parser = argparse.ArgumentParser(
        description="MemProbe Episode Generation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--specs", default=str(P.SPECS56), help="Path to latent_specs JSON")
    parser.add_argument("--filler-mode", default="templated", choices=["templated", "pool"],
                        help="templated = 56-suite regime (all fillers LLM-realised); pool = second-suite regime "
                             "(generic fillers drawn from --filler-pool)")
    parser.add_argument("--output", "-o", required=True,
                        help="Output path for generated episodes (JSONL)")
    parser.add_argument("--seeds", default=str(P.SEED_SKELETONS),
                        help="Path to seed_skeletons.md for few-shot examples")
    parser.add_argument("--filler-pool", default=None,
                        help="Path to pre-built filler pool JSON")
    parser.add_argument("--backend", default="gemini",
                        choices=["dashscope", "azure", "local", "huggingface", "groq", "anthropic", "gemini", "openai"],
                        help="LLM backend: dashscope (Qwen, paid), azure (gpt-4o, paid), local (GPU), huggingface, groq, anthropic")
    parser.add_argument("--model", default=None,
                        help="LLM model override (default: auto per backend)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Generation temperature")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show structure without calling API")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit to first N episodes")
    parser.add_argument("--episodes", nargs="+", default=None,
                        help="Generate only these episode IDs")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate existing episodes instead of generating")
    parser.add_argument("--input", default=None,
                        help="Input episodes file for validation")

    args = parser.parse_args()

    set_llm_backend(args.backend)

    if args.validate_only:
        if not args.input:
            parser.error("--validate-only requires --input")
        run_validation(args.input, args.specs)
    else:
        run_generation(
            specs_path=args.specs,
            output_path=args.output,
            seed_path=args.seeds,
            filler_pool_path=args.filler_pool,
            model=args.model,
            temperature=args.temperature,
            seed=args.seed,
            dry_run=args.dry_run,
            limit=args.limit,
            episode_ids=args.episodes,
            filler_mode=args.filler_mode,
        )


if __name__ == "__main__":
    main()
