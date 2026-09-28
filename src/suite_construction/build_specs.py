#!/usr/bin/env python3
"""
python src/suite_construction/build_specs.py --out /tmp/latent_specs_rebuilt.json

"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  # noqa: E402

import argparse
import json
from collections import Counter
from pathlib import Path

SEED_IDS = ["PILOT-01A", "PILOT-01B", "PILOT-02A", "PILOT-02B", "PILOT-02C",
            "PILOT-03A", "PILOT-03B", "PILOT-04A", "PILOT-04B"]

FILLER_PLAN_CORE = {
    "pre_perturbation": {
        "total": 15,
        "weakly_related_background": 6,
        "near_miss": 4,
        "confusable": 3,
        "decoy_nonupdate": 2
    },
    "post_perturbation": {
        "total": 2,
        "types": ["weakly_related_background", "near_miss"]
    }
}


def load_value_pairs(path):
    vp = json.loads(Path(path).read_text())
    return {ft["fact_type"]: ft for ft in vp["fact_types"]}


def stage_24(existing_specs, vp_by_type):
    def make_spec(
        episode_id, group_id, group_role, paradigm, condition, fact_type,
        expected_behavior, encoding_contexts, perturbation, probes, gold,
        matched_variables, variant_variables,
        filler_plan=None, num_encoding=3, perturbation_type="direct_update",
        paradigm_metadata=None,
    ):
        ft = vp_by_type[fact_type]
        vp_data = ft["value_pair"]

        spec = {
            "episode_id": episode_id,
            "group_id": group_id,
            "group_role": group_role,
            "matched_variables": matched_variables,
            "variant_variables": variant_variables,
            "paradigm": paradigm,
            "condition": condition,
            "domain": ft["domain"],
            "fact_type": fact_type,
            "length_tier": "core",
            "initial_value": vp_data["surface_initial"],
            "new_value": vp_data["surface_new"] if expected_behavior == "should_update" else vp_data["canonical_new"],
            "canonical_initial": vp_data["canonical_initial"],
            "canonical_new": vp_data["canonical_new"],
            "distractor_values": ft["distractor_values"],
            "expected_behavior": expected_behavior,
            "encoding": {
                "support_count": num_encoding,
                "mention_contexts": encoding_contexts,
            },
            "perturbation": perturbation,
            "filler_plan": filler_plan or FILLER_PLAN_CORE,
            "num_encoding_sessions": num_encoding,
            "num_pre_perturbation_fillers": (filler_plan or FILLER_PLAN_CORE)["pre_perturbation"]["total"],
            "num_perturbation_sessions": 1,
            "num_post_perturbation_fillers": (filler_plan or FILLER_PLAN_CORE)["post_perturbation"]["total"],
            "perturbation_type": perturbation_type,
            "probes": probes,
            "gold": gold,
            "probe_types": [p["type"] for p in probes],
        }
        if paradigm_metadata:
            spec["paradigm_metadata"] = paradigm_metadata
        return spec

    diet_encoding_high = [
        "user plans weekly vegetarian meal prep and asks for recipe ideas",
        "user mentions being vegetarian for three years while discussing a dinner invitation",
        "user asks about plant-based protein sources for post-workout recovery",
        "user checks whether a restaurant's menu has vegetarian options before booking"
    ]
    diet_encoding_low = [
        "user mentions being vegetarian in passing while ordering lunch"
    ]

    cons_preserve_probes = [
        {"type": "current_value", "question_hint": "What diet does the user currently follow?"},
        {"type": "conflict_value", "question_hint": "Was Mediterranean diet mentioned? In what context and did the user adopt it?"},
        {"type": "change_detection", "question_hint": "Did the user's dietary preference change?"},
        {"type": "source", "question_hint": "Who or what suggested the Mediterranean diet, and did the user confirm switching?",
         "gold_hint": "Mediterranean diet was suggested by a third party or mentioned in passing; the user did not confirm adopting it."},
    ]

    cons_preserve_gold = {
        "current_value": "vegetarian",
        "original_value": "vegetarian",
        "previous_value": None,
        "has_changed": False,
        "source_of_change": None,
        "invalid_sources": ["third_party_suggestion_of_Mediterranean_diet"]
    }

    spec_03C = make_spec(
        episode_id="PILOT-03C",
        group_id="GRP-CONS-02",
        group_role="high_support_weak_challenge",
        paradigm="consolidation",
        condition="high_weak_challenge",
        fact_type="diet_preference",
        expected_behavior="should_preserve",
        encoding_contexts=diet_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A friend casually suggests the user should try the Mediterranean diet because it's trendy. The user shows mild interest but does NOT say they are switching. No commitment, no confirmation."
        },
        perturbation_type="noise",
        probes=cons_preserve_probes,
        gold=cons_preserve_gold,
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "high", "challenge_strength": "weak"},
    )

    spec_03D = make_spec(
        episode_id="PILOT-03D",
        group_id="GRP-CONS-02",
        group_role="low_support_weak_challenge",
        paradigm="consolidation",
        condition="low_weak_challenge",
        fact_type="diet_preference",
        expected_behavior="should_preserve",
        encoding_contexts=diet_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A colleague mentions Mediterranean diet benefits at lunch. The user says 'sounds interesting' but does NOT commit to trying it. No explicit switch."
        },
        perturbation_type="noise",
        probes=cons_preserve_probes,
        gold=cons_preserve_gold,
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "low", "challenge_strength": "weak"},
    )

    owner_encoding = [
        "user assigns a code review to Sarah Kim as auth module owner",
        "user mentions Sarah Kim is the point of contact for auth-related tickets",
        "user cc's Sarah Kim on an auth deployment email"
    ]

    recon_preserve_probes = [
        {"type": "current_value", "question_hint": "Who currently owns the authentication module?"},
        {"type": "conflict_value", "question_hint": "Was David Chen mentioned in connection to the auth module? In what context?"},
        {"type": "change_detection", "question_hint": "Did ownership of the authentication module change?"},
        {"type": "source", "question_hint": "Who suggested David Chen might take over auth, and was it confirmed?",
         "gold_hint": "David Chen was mentioned as a possible future owner or was discussed in a hypothetical context; no confirmed transfer occurred."},
    ]

    recon_preserve_gold = {
        "current_value": "Sarah Kim",
        "original_value": "Sarah Kim",
        "previous_value": None,
        "has_changed": False,
        "source_of_change": None,
        "invalid_sources": ["ambiguous_suggestion_of_David_Chen"]
    }

    spec_04C = make_spec(
        episode_id="PILOT-04C",
        group_id="GRP-RECON-02",
        group_role="reactivated_weak_evidence",
        paradigm="reconsolidation",
        condition="reactivated_weak",
        fact_type="project_owner",
        expected_behavior="should_preserve",
        encoding_contexts=owner_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": True,
            "wording_hint": "User first recalls that Sarah Kim owns auth (reactivation). Then a colleague casually says 'I think David Chen might take over auth at some point.' This is speculative — no decision has been made. User does NOT confirm the transfer."
        },
        perturbation_type="noise",
        probes=recon_preserve_probes,
        gold=recon_preserve_gold,
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "reactivation": True, "evidence_strength": "weak"},
    )

    spec_04D = make_spec(
        episode_id="PILOT-04D",
        group_id="GRP-RECON-02",
        group_role="direct_weak_evidence",
        paradigm="reconsolidation",
        condition="direct_weak",
        fact_type="project_owner",
        expected_behavior="should_preserve",
        encoding_contexts=owner_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "Without first recalling Sarah Kim, a colleague mentions in a side conversation that 'David Chen has been helping with auth stuff lately.' This is ambiguous — could mean a one-off code review, not ownership transfer. User does NOT confirm any change."
        },
        perturbation_type="noise",
        probes=recon_preserve_probes,
        gold=recon_preserve_gold,
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "reactivation": False, "evidence_strength": "weak"},
    )

    config_encoding = [
        "user configures the API gateway and sets request timeout to 30 seconds",
        "user discusses retry logic and mentions the 30-second timeout limit",
        "user asks about monitoring slow endpoints relative to the 30-second threshold"
    ]

    spec_05A = make_spec(
        episode_id="PILOT-05A",
        group_id="GRP-INT-02",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="config_value",
        expected_behavior="should_update",
        encoding_contexts=config_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they increased the timeout to 60 seconds after profiling showed P99 latencies hitting 28 seconds under load."
        },
        probes=[
            {"type": "current_value", "question_hint": "What is the current API request timeout setting?"},
            {"type": "previous_value", "question_hint": "What was the timeout before the user changed it?"},
            {"type": "change_detection", "question_hint": "Did the API timeout setting change?"},
            {"type": "temporal", "question_hint": "When or why did the user change the timeout?"},
        ],
        gold={
            "current_value": "60 seconds",
            "original_value": "30 seconds",
            "previous_value": "30 seconds",
            "has_changed": True,
            "source_of_change": "user explicitly stated the change",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
    )

    spec_05B = make_spec(
        episode_id="PILOT-05B",
        group_id="GRP-INT-02",
        group_role="decoy_preserve",
        paradigm="interference",
        condition="decoy_no_update",
        fact_type="config_value",
        expected_behavior="should_preserve",
        encoding_contexts=config_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A teammate mentions they use 60 seconds for their own service's timeout. The user acknowledges but does NOT change their own setting — it stays at 30 seconds."
        },
        perturbation_type="noise",
        probes=[
            {"type": "current_value", "question_hint": "What is the current API request timeout for the user's service?"},
            {"type": "conflict_value", "question_hint": "Was 60 seconds mentioned? Whose setting was it?"},
            {"type": "change_detection", "question_hint": "Did the user's own timeout setting change?"},
            {"type": "source", "question_hint": "Who mentioned 60 seconds and did the user adopt it?",
             "gold_hint": "60 seconds was mentioned as a teammate's setting for a different service; the user did not change their own timeout from 30 seconds."},
        ],
        gold={
            "current_value": "30 seconds",
            "original_value": "30 seconds",
            "previous_value": None,
            "has_changed": False,
            "source_of_change": None,
            "invalid_sources": ["third_party_mention_of_60s_timeout"]
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
    )

    port_encoding = [
        "user starts the API service and confirms it's running on port 8080",
        "user configures the reverse proxy to forward to port 8080",
        "user shares the health-check URL including port 8080 with a teammate"
    ]

    spec_06A = make_spec(
        episode_id="PILOT-06A",
        group_id="GRP-MIS-02",
        group_role="user_update",
        paradigm="misinformation",
        condition="user_explicit",
        fact_type="reported_port",
        expected_behavior="should_update",
        encoding_contexts=port_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they moved the service to port 3000 to avoid a conflict with the new monitoring stack on 8080."
        },
        probes=[
            {"type": "current_value", "question_hint": "What port is the user's API service currently running on?"},
            {"type": "previous_value", "question_hint": "What port was the service on before the change?"},
            {"type": "source", "question_hint": "Who communicated the port change and why?"},
            {"type": "change_detection", "question_hint": "Did the user's API service port change?"},
        ],
        gold={
            "current_value": "3000",
            "original_value": "8080",
            "previous_value": "8080",
            "has_changed": True,
            "source_of_change": "user explicitly stated the change",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior", "perturbation.source_type"],
        paradigm_metadata={"test_type": "plasticity", "source_type": "user_explicit"},
    )

    spec_06B = make_spec(
        episode_id="PILOT-06B",
        group_id="GRP-MIS-02",
        group_role="assistant_noise",
        paradigm="misinformation",
        condition="assistant_noise",
        fact_type="reported_port",
        expected_behavior="should_preserve",
        encoding_contexts=port_encoding,
        perturbation={
            "source_type": "assistant_hallucination",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "The assistant incorrectly states the service is on port 3000. The user corrects: 'No, it's still on 8080.'"
        },
        perturbation_type="noise",
        probes=[
            {"type": "current_value", "question_hint": "What port is the user's API service currently running on?"},
            {"type": "conflict_value", "question_hint": "Was port 3000 mentioned? By whom and was it confirmed?"},
            {"type": "source", "question_hint": "Did the assistant ever state a different port? How did the user respond?",
             "gold_hint": "Port 3000 was incorrectly stated by the assistant; the user corrected it and confirmed the service remains on port 8080."},
            {"type": "change_detection", "question_hint": "Did the user's API service port change?"},
        ],
        gold={
            "current_value": "8080",
            "original_value": "8080",
            "previous_value": None,
            "has_changed": False,
            "source_of_change": None,
            "invalid_sources": ["assistant_hallucinated_port_3000"]
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior", "perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "assistant_hallucination"},
    )

    spec_06C = make_spec(
        episode_id="PILOT-06C",
        group_id="GRP-MIS-02",
        group_role="third_party_noise",
        paradigm="misinformation",
        condition="third_party_noise",
        fact_type="reported_port",
        expected_behavior="should_preserve",
        encoding_contexts=port_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A colleague mentions their own service runs on port 3000. The user does NOT confirm any change to their own service — it remains on 8080."
        },
        perturbation_type="noise",
        probes=[
            {"type": "current_value", "question_hint": "What port is the user's own API service on?"},
            {"type": "conflict_value", "question_hint": "Was port 3000 mentioned? Whose service was it?"},
            {"type": "source", "question_hint": "Who mentioned port 3000 and did the user confirm it for their own service?",
             "gold_hint": "Port 3000 was mentioned as a colleague's service port; the user did not confirm it applied to their own API service."},
            {"type": "change_detection", "question_hint": "Did the user's own API service port change?"},
        ],
        gold={
            "current_value": "8080",
            "original_value": "8080",
            "previous_value": None,
            "has_changed": False,
            "source_of_change": None,
            "invalid_sources": ["third_party_mention_of_port_3000_for_different_service"]
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior", "perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "third_party"},
    )

    branch_encoding_high = [
        "user runs tests on feature/auth-redesign and discusses failing test cases",
        "user opens a PR from feature/auth-redesign and asks for review",
        "user mentions rebasing feature/auth-redesign onto main",
        "user asks about merge conflicts on feature/auth-redesign"
    ]
    branch_encoding_low = [
        "user mentions they're on feature/auth-redesign while checking something quickly"
    ]

    spec_07A = make_spec(
        episode_id="PILOT-07A",
        group_id="GRP-CONS-03",
        group_role="high_support_strong_update",
        paradigm="consolidation",
        condition="high",
        fact_type="active_branch",
        expected_behavior="should_update",
        encoding_contexts=branch_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they finished auth-redesign, merged the PR, and switched to feature/payment-v2 for the next sprint."
        },
        probes=[
            {"type": "current_value", "question_hint": "What git branch is the user currently working on?"},
            {"type": "previous_value", "question_hint": "What branch was the user on before switching?"},
            {"type": "change_detection", "question_hint": "Did the user's active branch change?"},
            {"type": "temporal", "question_hint": "When or why did the user switch branches?"},
        ],
        gold={
            "current_value": "feature/payment-v2",
            "original_value": "feature/auth-redesign",
            "previous_value": "feature/auth-redesign",
            "has_changed": True,
            "source_of_change": "user explicitly stated the switch",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "high"},
    )

    spec_07B = make_spec(
        episode_id="PILOT-07B",
        group_id="GRP-CONS-03",
        group_role="low_support_strong_update",
        paradigm="consolidation",
        condition="low",
        fact_type="active_branch",
        expected_behavior="should_update",
        encoding_contexts=branch_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they switched to feature/payment-v2 to start the payment integration work."
        },
        probes=[
            {"type": "current_value", "question_hint": "What git branch is the user currently working on?"},
            {"type": "previous_value", "question_hint": "What branch was the user on before switching?"},
            {"type": "change_detection", "question_hint": "Did the user's active branch change?"},
            {"type": "temporal", "question_hint": "When or why did the user switch branches?"},
        ],
        gold={
            "current_value": "feature/payment-v2",
            "original_value": "feature/auth-redesign",
            "previous_value": "feature/auth-redesign",
            "has_changed": True,
            "source_of_change": "user explicitly stated the switch",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "low"},
    )

    db_encoding = [
        "user runs SQL migrations on the PostgreSQL instance",
        "user discusses indexing strategies specific to PostgreSQL",
        "user configures the connection pool for the PostgreSQL database"
    ]

    spec_08A = make_spec(
        episode_id="PILOT-08A",
        group_id="GRP-RECON-03",
        group_role="reactivated_strong_update",
        paradigm="reconsolidation",
        condition="reactivated",
        fact_type="selected_database",
        expected_behavior="should_update",
        encoding_contexts=db_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": True,
            "wording_hint": "User first recalls they were using PostgreSQL (reactivation), then says they decided to migrate to MongoDB because the data model is a better fit for the new document-heavy feature."
        },
        probes=[
            {"type": "current_value", "question_hint": "What database does the user's project currently use?"},
            {"type": "previous_value", "question_hint": "What database was the project using before the migration?"},
            {"type": "change_detection", "question_hint": "Did the project's database change?"},
            {"type": "source", "question_hint": "Who decided to change the database and how was it communicated?"},
        ],
        gold={
            "current_value": "MongoDB",
            "original_value": "PostgreSQL",
            "previous_value": "PostgreSQL",
            "has_changed": True,
            "source_of_change": "user explicitly stated after reactivating the old memory",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "reactivation": True, "evidence_strength": "strong"},
    )

    spec_08B = make_spec(
        episode_id="PILOT-08B",
        group_id="GRP-RECON-03",
        group_role="direct_strong_update",
        paradigm="reconsolidation",
        condition="direct",
        fact_type="selected_database",
        expected_behavior="should_update",
        encoding_contexts=db_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User directly states they migrated the project to MongoDB without first mentioning PostgreSQL. They say the migration is done and all services now point to MongoDB."
        },
        probes=[
            {"type": "current_value", "question_hint": "What database does the user's project currently use?"},
            {"type": "previous_value", "question_hint": "What database was the project using before?"},
            {"type": "change_detection", "question_hint": "Did the project's database change?"},
            {"type": "source", "question_hint": "How was the database change communicated?"},
        ],
        gold={
            "current_value": "MongoDB",
            "original_value": "PostgreSQL",
            "previous_value": "PostgreSQL",
            "has_changed": True,
            "source_of_change": "user explicitly stated the migration",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "reactivation": False, "evidence_strength": "strong"},
    )

    spec_09A = make_spec(
        episode_id="PILOT-09A",
        group_id="GRP-INT-03",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="selected_database",
        expected_behavior="should_update",
        encoding_contexts=db_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User states they completed the migration from PostgreSQL to MongoDB. All services are now connected to MongoDB."
        },
        probes=[
            {"type": "current_value", "question_hint": "What database does the user's project use now?"},
            {"type": "previous_value", "question_hint": "What database was the project on before?"},
            {"type": "change_detection", "question_hint": "Did the project database change?"},
            {"type": "temporal", "question_hint": "When or why did the database change?"},
        ],
        gold={
            "current_value": "MongoDB",
            "original_value": "PostgreSQL",
            "previous_value": "PostgreSQL",
            "has_changed": True,
            "source_of_change": "user explicitly stated the migration",
            "invalid_sources": []
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
    )

    spec_09B = make_spec(
        episode_id="PILOT-09B",
        group_id="GRP-INT-03",
        group_role="decoy_preserve",
        paradigm="interference",
        condition="decoy_no_update",
        fact_type="selected_database",
        expected_behavior="should_preserve",
        encoding_contexts=db_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A teammate mentions their microservice uses MongoDB. User acknowledges but does NOT change their own project's database — it stays on PostgreSQL."
        },
        perturbation_type="noise",
        probes=[
            {"type": "current_value", "question_hint": "What database does the user's own project use?"},
            {"type": "conflict_value", "question_hint": "Was MongoDB mentioned? Whose project was it for?"},
            {"type": "change_detection", "question_hint": "Did the user's own project database change?"},
            {"type": "source", "question_hint": "Who mentioned MongoDB and did the user adopt it for their project?",
             "gold_hint": "MongoDB was mentioned as a teammate's database choice for a different microservice; the user did not migrate their own project from PostgreSQL."},
        ],
        gold={
            "current_value": "PostgreSQL",
            "original_value": "PostgreSQL",
            "previous_value": None,
            "has_changed": False,
            "source_of_change": None,
            "invalid_sources": ["third_party_mention_of_MongoDB_for_different_service"]
        },
        matched_variables=["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["perturbation", "gold", "expected_behavior"],
    )

    new_specs = [
        spec_03C, spec_03D,
        spec_04C, spec_04D,
        spec_05A, spec_05B,
        spec_06A, spec_06B, spec_06C,
        spec_07A, spec_07B,
        spec_08A, spec_08B,
        spec_09A, spec_09B,
    ]

    return existing_specs + new_specs


def stage_56(existing_specs, vp_by_type):
    def _base_fact_type(fact_type: str) -> str:
        import re
        return re.sub(r'_v\d+$', '', fact_type)

    def make_spec(
        episode_id, group_id, group_role, paradigm, condition, fact_type,
        expected_behavior, encoding_contexts, perturbation, probes, gold,
        matched_variables, variant_variables,
        filler_plan=None, num_encoding=3, perturbation_type="direct_update",
        paradigm_metadata=None,
    ):
        ft = vp_by_type[fact_type]
        vp_data = ft["value_pair"]

        spec = {
            "episode_id": episode_id,
            "group_id": group_id,
            "group_role": group_role,
            "matched_variables": matched_variables,
            "variant_variables": variant_variables,
            "paradigm": paradigm,
            "condition": condition,
            "domain": ft["domain"],
            "fact_type": fact_type,
            "base_fact_type": _base_fact_type(fact_type),
            "length_tier": "core",
            "difficulty_target": "core",
            "initial_value": vp_data["surface_initial"],
            "new_value": vp_data["surface_new"] if expected_behavior == "should_update" else vp_data["canonical_new"],
            "canonical_initial": vp_data["canonical_initial"],
            "canonical_new": vp_data["canonical_new"],
            "distractor_values": ft["distractor_values"],
            "expected_behavior": expected_behavior,
            "encoding": {
                "support_count": num_encoding,
                "mention_contexts": encoding_contexts,
            },
            "perturbation": perturbation,
            "filler_plan": filler_plan or FILLER_PLAN_CORE,
            "num_encoding_sessions": num_encoding,
            "num_pre_perturbation_fillers": (filler_plan or FILLER_PLAN_CORE)["pre_perturbation"]["total"],
            "num_perturbation_sessions": 1,
            "num_post_perturbation_fillers": (filler_plan or FILLER_PLAN_CORE)["post_perturbation"]["total"],
            "perturbation_type": perturbation_type,
            "probes": probes,
            "gold": gold,
            "probe_types": [p["type"] for p in probes],
        }
        if paradigm_metadata:
            spec["paradigm_metadata"] = paradigm_metadata
        return spec

    def update_probes(fact_readable, initial, new):
        return [
            {"type": "current_value", "question_hint": f"What is {fact_readable} now?"},
            {"type": "previous_value", "question_hint": f"What was {fact_readable} before the change?"},
            {"type": "change_detection", "question_hint": f"Did {fact_readable} change?"},
            {"type": "temporal", "question_hint": f"When or why did {fact_readable} change?"},
        ]

    def update_gold(initial, new, source="user explicitly stated the change"):
        return {
            "current_value": new,
            "original_value": initial,
            "previous_value": initial,
            "has_changed": True,
            "source_of_change": source,
            "invalid_sources": []
        }

    def preserve_probes(fact_readable, initial, new):
        return [
            {"type": "current_value", "question_hint": f"What is {fact_readable} now?"},
            {"type": "conflict_value", "question_hint": f"Was {new} mentioned? In what context and was it adopted?"},
            {"type": "change_detection", "question_hint": f"Did {fact_readable} change?"},
            {"type": "source", "question_hint": f"Who or what mentioned {new}, and did the user confirm it?",
             "gold_hint": f"{new} was mentioned in a non-authoritative context; the user did not confirm adopting it."},
        ]

    def preserve_gold(initial, new, invalid_source_tag):
        return {
            "current_value": initial,
            "original_value": initial,
            "previous_value": None,
            "has_changed": False,
            "source_of_change": None,
            "invalid_sources": [invalid_source_tag]
        }

    MATCHED_STD = ["fact_type", "encoding", "distractor_values", "filler_plan", "length_tier"]
    VARIANT_STD = ["perturbation", "gold", "expected_behavior"]

    gym2_encoding = [
        "user mentions their YMCA Downtown membership while planning a workout",
        "user asks about group fitness classes available at YMCA Downtown",
        "user discusses commute time to YMCA Downtown after work"
    ]

    spec_10A = make_spec(
        episode_id="PILOT-10A",
        group_id="GRP-INT-04",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="current_gym_v2",
        expected_behavior="should_update",
        encoding_contexts=gym2_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they cancelled YMCA Downtown and joined Summit Climbing Gym because they want to focus on bouldering."
        },
        probes=update_probes("the user's gym", "YMCA Downtown", "Summit Climbing Gym"),
        gold=update_gold("YMCA Downtown", "Summit Climbing Gym"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    spec_10B = make_spec(
        episode_id="PILOT-10B",
        group_id="GRP-INT-04",
        group_role="decoy_preserve",
        paradigm="interference",
        condition="decoy_no_update",
        fact_type="current_gym_v2",
        expected_behavior="should_preserve",
        encoding_contexts=gym2_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A friend raves about Summit Climbing Gym and suggests the user try it. The user says 'sounds cool' but does NOT cancel YMCA Downtown or join."
        },
        perturbation_type="noise",
        probes=preserve_probes("the user's gym", "YMCA Downtown", "Summit Climbing Gym"),
        gold=preserve_gold("YMCA Downtown", "Summit Climbing Gym", "friend_suggestion_of_Summit_Climbing_Gym"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    standup_encoding = [
        "user joins the 9:30 AM standup and gives a status update",
        "user asks a teammate to present their blockers at the 9:30 AM standup",
        "user sets a recurring calendar event for the 9:30 AM standup"
    ]

    spec_11A = make_spec(
        episode_id="PILOT-11A",
        group_id="GRP-INT-05",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="team_standup",
        expected_behavior="should_update",
        encoding_contexts=standup_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says the team agreed to move standup to 10:00 AM to accommodate the new remote teammates in a later time zone."
        },
        probes=update_probes("the team standup time", "9:30 AM", "10:00 AM"),
        gold=update_gold("9:30 AM", "10:00 AM"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    spec_11B = make_spec(
        episode_id="PILOT-11B",
        group_id="GRP-INT-05",
        group_role="decoy_preserve",
        paradigm="interference",
        condition="decoy_no_update",
        fact_type="team_standup",
        expected_behavior="should_preserve",
        encoding_contexts=standup_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "Another team's lead mentions their standup is at 10:00 AM and suggests aligning. The user says they'll consider it but makes no commitment — standup stays at 9:30 AM."
        },
        perturbation_type="noise",
        probes=preserve_probes("the team standup time", "9:30 AM", "10:00 AM"),
        gold=preserve_gold("9:30 AM", "10:00 AM", "other_team_suggestion_of_10AM"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    coffee_encoding = [
        "user mentions grabbing coffee from Blue Bottle Coffee before their morning meeting",
        "user recommends Blue Bottle Coffee to a colleague who asks for a cafe suggestion",
        "user discusses their Blue Bottle Coffee subscription and favorite roast"
    ]

    spec_12A = make_spec(
        episode_id="PILOT-12A",
        group_id="GRP-INT-06",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="favorite_coffee",
        expected_behavior="should_update",
        encoding_contexts=coffee_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they switched to Stumptown Coffee after discovering their single-origin Ethiopian blend. Blue Bottle raised prices and they prefer Stumptown now."
        },
        probes=update_probes("the user's go-to coffee shop", "Blue Bottle Coffee", "Stumptown Coffee"),
        gold=update_gold("Blue Bottle Coffee", "Stumptown Coffee"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD,
    )

    deploy_encoding = [
        "user coordinates a weekly deployment and sends the release checklist",
        "user mentions the weekly deployment cadence during sprint planning",
        "user sets up a monitoring dashboard refresh aligned to the weekly deploy schedule"
    ]

    spec_12B = make_spec(
        episode_id="PILOT-12B",
        group_id="GRP-INT-07",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="deploy_cadence",
        expected_behavior="should_update",
        encoding_contexts=deploy_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says the team decided to switch to bi-weekly deployments after two back-to-back hotfixes caused by rushed weekly releases."
        },
        probes=update_probes("the team's deployment cadence", "weekly", "bi-weekly"),
        gold=update_gold("weekly", "bi-weekly"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD,
    )

    log_encoding = [
        "user configures the logging framework and sets the level to INFO for production",
        "user discusses log volume at INFO level and how it affects storage costs",
        "user filters logs by INFO level while investigating a customer report"
    ]

    spec_13A = make_spec(
        episode_id="PILOT-13A",
        group_id="GRP-INT-08",
        group_role="update",
        paradigm="interference",
        condition="authoritative_update",
        fact_type="log_level",
        expected_behavior="should_update",
        encoding_contexts=log_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they switched the log level to DEBUG to investigate an intermittent connection timeout. They updated the config and redeployed."
        },
        probes=update_probes("the application log level", "INFO", "DEBUG"),
        gold=update_gold("INFO", "DEBUG"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    spec_13B = make_spec(
        episode_id="PILOT-13B",
        group_id="GRP-INT-08",
        group_role="decoy_preserve",
        paradigm="interference",
        condition="decoy_no_update",
        fact_type="log_level",
        expected_behavior="should_preserve",
        encoding_contexts=log_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A teammate mentions they run DEBUG level on their staging server. The user acknowledges but does NOT change their own production log level — it stays at INFO."
        },
        perturbation_type="noise",
        probes=preserve_probes("the application log level", "INFO", "DEBUG"),
        gold=preserve_gold("INFO", "DEBUG", "teammate_mention_of_DEBUG_for_staging"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
    )

    commute_encoding = [
        "user mentions biking to work and asks about a route with less traffic",
        "user discusses their cycling commute gear for rainy days",
        "user mentions locking up their bike at the office rack"
    ]

    spec_14A = make_spec(
        episode_id="PILOT-14A",
        group_id="GRP-MIS-03",
        group_role="user_update",
        paradigm="misinformation",
        condition="user_explicit",
        fact_type="commute_method",
        expected_behavior="should_update",
        encoding_contexts=commute_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they sold their bike and now take the subway because it's faster and they don't arrive sweaty."
        },
        probes=update_probes("the user's commute method", "cycling", "the subway"),
        gold=update_gold("cycling", "the subway"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "plasticity", "source_type": "user_explicit"},
    )

    spec_14B = make_spec(
        episode_id="PILOT-14B",
        group_id="GRP-MIS-03",
        group_role="assistant_noise",
        paradigm="misinformation",
        condition="assistant_noise",
        fact_type="commute_method",
        expected_behavior="should_preserve",
        encoding_contexts=commute_encoding,
        perturbation={
            "source_type": "assistant_hallucination",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "The assistant incorrectly says 'Since you take the subway...' The user corrects: 'No, I bike to work.'"
        },
        perturbation_type="noise",
        probes=preserve_probes("the user's commute method", "cycling", "the subway"),
        gold=preserve_gold("cycling", "the subway", "assistant_hallucinated_subway_commute"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "assistant_hallucination"},
    )

    spec_14C = make_spec(
        episode_id="PILOT-14C",
        group_id="GRP-MIS-03",
        group_role="third_party_noise",
        paradigm="misinformation",
        condition="third_party_noise",
        fact_type="commute_method",
        expected_behavior="should_preserve",
        encoding_contexts=commute_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A colleague mentions they saw the user at the subway station. The user clarifies they were just meeting a friend there — they still bike to work."
        },
        perturbation_type="noise",
        probes=preserve_probes("the user's commute method", "cycling", "the subway"),
        gold=preserve_gold("cycling", "the subway", "third_party_mistaken_sighting_at_subway"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "third_party"},
    )

    owner2_encoding = [
        "user assigns a billing-related bug to Priya Nair as billing module owner",
        "user mentions Priya Nair is the go-to person for billing architecture decisions",
        "user cc's Priya Nair on a billing module deployment email"
    ]

    spec_15A = make_spec(
        episode_id="PILOT-15A",
        group_id="GRP-MIS-04",
        group_role="user_update",
        paradigm="misinformation",
        condition="user_explicit",
        fact_type="project_owner_v2",
        expected_behavior="should_update",
        encoding_contexts=owner2_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says Priya moved to the platform team and Marcus Lee has taken over ownership of the billing module effective this sprint."
        },
        probes=update_probes("who owns the billing module", "Priya Nair", "Marcus Lee"),
        gold=update_gold("Priya Nair", "Marcus Lee"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "plasticity", "source_type": "user_explicit"},
    )

    spec_15B = make_spec(
        episode_id="PILOT-15B",
        group_id="GRP-MIS-04",
        group_role="assistant_noise",
        paradigm="misinformation",
        condition="assistant_noise",
        fact_type="project_owner_v2",
        expected_behavior="should_preserve",
        encoding_contexts=owner2_encoding,
        perturbation={
            "source_type": "assistant_hallucination",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "The assistant mistakenly refers to Marcus Lee as the billing module owner. The user corrects: 'That's Priya Nair, not Marcus.'"
        },
        perturbation_type="noise",
        probes=preserve_probes("who owns the billing module", "Priya Nair", "Marcus Lee"),
        gold=preserve_gold("Priya Nair", "Marcus Lee", "assistant_hallucinated_Marcus_as_owner"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "assistant_hallucination"},
    )

    spec_15C = make_spec(
        episode_id="PILOT-15C",
        group_id="GRP-MIS-04",
        group_role="third_party_noise",
        paradigm="misinformation",
        condition="third_party_noise",
        fact_type="project_owner_v2",
        expected_behavior="should_preserve",
        encoding_contexts=owner2_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A new hire asks Marcus Lee a billing question, assuming he owns it. The user clarifies that Priya Nair is the actual owner."
        },
        perturbation_type="noise",
        probes=preserve_probes("who owns the billing module", "Priya Nair", "Marcus Lee"),
        gold=preserve_gold("Priya Nair", "Marcus Lee", "new_hire_confusion_about_billing_owner"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "third_party"},
    )

    port2_encoding = [
        "user configures the database client to connect on port 5432",
        "user checks the connection pool health on port 5432",
        "user shares a connection string with port 5432 in the team wiki"
    ]

    spec_16A = make_spec(
        episode_id="PILOT-16A",
        group_id="GRP-MIS-05",
        group_role="stale_tool",
        paradigm="misinformation",
        condition="stale_tool",
        fact_type="reported_port_v2",
        expected_behavior="should_preserve",
        encoding_contexts=port2_encoding,
        perturbation={
            "source_type": "stale_tool",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A monitoring dashboard (last updated 3 weeks ago) shows the database on port 8443. The user notices and says the dashboard is stale — the service is still on 5432 and the dashboard needs updating."
        },
        perturbation_type="noise",
        probes=preserve_probes("the database service port", "5432", "8443"),
        gold=preserve_gold("5432", "8443", "stale_dashboard_showing_port_8443"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "stale_tool"},
    )

    ci_encoding = [
        "user triggers a build on Jenkins and checks the pipeline status",
        "user discusses Jenkins plugin configuration for the linting step",
        "user shares a Jenkins build URL with the team for a failing test"
    ]

    spec_16B = make_spec(
        episode_id="PILOT-16B",
        group_id="GRP-MIS-06",
        group_role="stale_tool",
        paradigm="misinformation",
        condition="stale_tool",
        fact_type="ci_provider",
        expected_behavior="should_preserve",
        encoding_contexts=ci_encoding,
        perturbation={
            "source_type": "stale_tool",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "An old onboarding doc references GitHub Actions as the CI system. The user points out the doc is outdated — the team still uses Jenkins and the doc was never updated after a cancelled migration attempt."
        },
        perturbation_type="noise",
        probes=preserve_probes("the team's CI/CD platform", "Jenkins", "GitHub Actions"),
        gold=preserve_gold("Jenkins", "GitHub Actions", "stale_onboarding_doc_showing_github_actions"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD + ["perturbation.source_type"],
        paradigm_metadata={"test_type": "stability", "source_type": "stale_tool"},
    )

    deadline2_encoding_high = [
        "user blocks off Friday afternoon to finalize the report before the Friday 5 PM deadline",
        "user asks a colleague to review their draft ahead of the Friday 5 PM submission",
        "user mentions the Friday 5 PM deadline while prioritizing tasks at Monday standup",
        "user sets a reminder for Thursday to do final edits before Friday 5 PM"
    ]
    deadline2_encoding_low = [
        "user mentions the report is due Friday 5 PM while discussing their week"
    ]

    spec_17A = make_spec(
        episode_id="PILOT-17A",
        group_id="GRP-CONS-04",
        group_role="high_support_strong_update",
        paradigm="consolidation",
        condition="high",
        fact_type="submission_deadline_v2",
        expected_behavior="should_update",
        encoding_contexts=deadline2_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says the manager emailed that the deadline is extended to Monday noon because the review committee meeting was pushed to Tuesday."
        },
        probes=update_probes("the report submission deadline", "Friday 5 PM", "Monday noon"),
        gold=update_gold("Friday 5 PM", "Monday noon"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "high"},
    )

    spec_17B = make_spec(
        episode_id="PILOT-17B",
        group_id="GRP-CONS-04",
        group_role="low_support_strong_update",
        paradigm="consolidation",
        condition="low",
        fact_type="submission_deadline_v2",
        expected_behavior="should_update",
        encoding_contexts=deadline2_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says the deadline moved to Monday noon per the latest team email."
        },
        probes=update_probes("the report submission deadline", "Friday 5 PM", "Monday noon"),
        gold=update_gold("Friday 5 PM", "Monday noon"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "low"},
    )

    cons_deadline2_preserve_probes = preserve_probes(
        "the report submission deadline", "Friday 5 PM", "Monday noon")
    cons_deadline2_preserve_gold = preserve_gold(
        "Friday 5 PM", "Monday noon", "third_party_rumor_of_Monday_noon")

    spec_17C = make_spec(
        episode_id="PILOT-17C",
        group_id="GRP-CONS-04",
        group_role="high_support_weak_challenge",
        paradigm="consolidation",
        condition="high_weak_challenge",
        fact_type="submission_deadline_v2",
        expected_behavior="should_preserve",
        encoding_contexts=deadline2_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A colleague from another department says they heard the deadline might move to Monday noon. The user says they haven't seen any official communication and are still targeting Friday 5 PM."
        },
        perturbation_type="noise",
        probes=cons_deadline2_preserve_probes,
        gold=cons_deadline2_preserve_gold,
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "high", "challenge_strength": "weak"},
    )

    spec_17D = make_spec(
        episode_id="PILOT-17D",
        group_id="GRP-CONS-04",
        group_role="low_support_weak_challenge",
        paradigm="consolidation",
        condition="low_weak_challenge",
        fact_type="submission_deadline_v2",
        expected_behavior="should_preserve",
        encoding_contexts=deadline2_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A teammate mentions in Slack that 'someone said the deadline is Monday noon now.' The user replies they haven't received any update — still Friday 5 PM as far as they know."
        },
        perturbation_type="noise",
        probes=cons_deadline2_preserve_probes,
        gold=cons_deadline2_preserve_gold,
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "low", "challenge_strength": "weak"},
    )

    diet2_encoding_high = [
        "user discusses their paleo meal prep routine and favorite recipes",
        "user asks about paleo-friendly restaurants for a dinner with friends",
        "user mentions following paleo for two years while talking about energy levels",
        "user asks for paleo-compatible snack ideas for a road trip"
    ]
    diet2_encoding_low = [
        "user mentions following a paleo diet in passing while discussing lunch"
    ]

    spec_18A = make_spec(
        episode_id="PILOT-18A",
        group_id="GRP-CONS-05",
        group_role="high_support_strong_update",
        paradigm="consolidation",
        condition="high",
        fact_type="diet_preference_v2",
        expected_behavior="should_update",
        encoding_contexts=diet2_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says their doctor recommended switching to a whole-food plant-based diet for cholesterol. They started this week and are fully committed."
        },
        probes=update_probes("the user's dietary preference", "paleo", "whole-food plant-based"),
        gold=update_gold("paleo", "whole-food plant-based"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "high"},
    )

    spec_18B = make_spec(
        episode_id="PILOT-18B",
        group_id="GRP-CONS-05",
        group_role="low_support_strong_update",
        paradigm="consolidation",
        condition="low",
        fact_type="diet_preference_v2",
        expected_behavior="should_update",
        encoding_contexts=diet2_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User says they switched to a whole-food plant-based diet after reading about its health benefits."
        },
        probes=update_probes("the user's dietary preference", "paleo", "whole-food plant-based"),
        gold=update_gold("paleo", "whole-food plant-based"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "plasticity", "encoding_strength": "low"},
    )

    sleep_encoding_high = [
        "user mentions their 11 PM bedtime while discussing their morning routine",
        "user sets an alarm for 11 PM to start winding down",
        "user declines a late event because their bedtime is 11 PM",
        "user asks about sleep hygiene tips to improve their 11 PM routine"
    ]

    spec_18C = make_spec(
        episode_id="PILOT-18C",
        group_id="GRP-CONS-06",
        group_role="high_support_weak_challenge",
        paradigm="consolidation",
        condition="high_weak_challenge",
        fact_type="sleep_schedule",
        expected_behavior="should_preserve",
        encoding_contexts=sleep_encoding_high,
        num_encoding=4,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A wellness podcast the user listens to recommends a 10 PM bedtime. The user says 'interesting idea' but does NOT change their bedtime from 11 PM."
        },
        perturbation_type="noise",
        probes=preserve_probes("the user's bedtime", "11 PM", "10 PM"),
        gold=preserve_gold("11 PM", "10 PM", "podcast_recommendation_of_10PM"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "high", "challenge_strength": "weak"},
    )

    retry_encoding_low = [
        "user configures the API client with 3 retries and checks error handling"
    ]

    spec_18D = make_spec(
        episode_id="PILOT-18D",
        group_id="GRP-CONS-07",
        group_role="low_support_weak_challenge",
        paradigm="consolidation",
        condition="low_weak_challenge",
        fact_type="config_value_v2",
        expected_behavior="should_preserve",
        encoding_contexts=retry_encoding_low,
        num_encoding=1,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "A blog post recommends 5 retries as the default. The user reads it but says their service handles failures differently and sticks with 3 retries."
        },
        perturbation_type="noise",
        probes=preserve_probes("the API retry count", "3 retries", "5 retries"),
        gold=preserve_gold("3 retries", "5 retries", "blog_post_recommendation_of_5_retries"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=["encoding", "perturbation", "gold", "expected_behavior"],
        paradigm_metadata={"test_type": "stability", "encoding_strength": "low", "challenge_strength": "weak"},
    )

    spec_19A = make_spec(
        episode_id="PILOT-19A",
        group_id="GRP-RECON-04",
        group_role="reactivated_strong_update",
        paradigm="reconsolidation",
        condition="reactivated",
        fact_type="favorite_coffee",
        expected_behavior="should_update",
        encoding_contexts=coffee_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": True,
            "wording_hint": "User first recalls they usually go to Blue Bottle Coffee (reactivation). Then says they tried Stumptown Coffee last week and it's now their go-to — better quality and closer to the office."
        },
        probes=update_probes("the user's go-to coffee shop", "Blue Bottle Coffee", "Stumptown Coffee"),
        gold=update_gold("Blue Bottle Coffee", "Stumptown Coffee",
                         "user explicitly stated after reactivating the old memory"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "plasticity", "reactivation": True, "evidence_strength": "strong"},
    )

    spec_19B = make_spec(
        episode_id="PILOT-19B",
        group_id="GRP-RECON-04",
        group_role="direct_strong_update",
        paradigm="reconsolidation",
        condition="direct",
        fact_type="favorite_coffee",
        expected_behavior="should_update",
        encoding_contexts=coffee_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User directly says they switched to Stumptown Coffee without first mentioning Blue Bottle. They say Stumptown is their new regular spot."
        },
        probes=update_probes("the user's go-to coffee shop", "Blue Bottle Coffee", "Stumptown Coffee"),
        gold=update_gold("Blue Bottle Coffee", "Stumptown Coffee",
                         "user explicitly stated the switch"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "plasticity", "reactivation": False, "evidence_strength": "strong"},
    )

    spec_19C = make_spec(
        episode_id="PILOT-19C",
        group_id="GRP-RECON-05",
        group_role="reactivated_weak_evidence",
        paradigm="reconsolidation",
        condition="reactivated_weak",
        fact_type="reported_port_v2",
        expected_behavior="should_preserve",
        encoding_contexts=port2_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": True,
            "wording_hint": "User first recalls the database is on port 5432 (reactivation). Then a colleague mentions port 8443 from an old config file they found. User says that config is outdated — the service is on 5432."
        },
        perturbation_type="noise",
        probes=preserve_probes("the database service port", "5432", "8443"),
        gold=preserve_gold("5432", "8443", "colleague_found_outdated_config_with_8443"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "stability", "reactivation": True, "evidence_strength": "weak"},
    )

    spec_19D = make_spec(
        episode_id="PILOT-19D",
        group_id="GRP-RECON-05",
        group_role="direct_weak_evidence",
        paradigm="reconsolidation",
        condition="direct_weak",
        fact_type="reported_port_v2",
        expected_behavior="should_preserve",
        encoding_contexts=port2_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "Without first mentioning port 5432, a colleague says 'I think the database moved to 8443.' The user checks and confirms it's still on 5432 — the colleague was looking at a different environment."
        },
        perturbation_type="noise",
        probes=preserve_probes("the database service port", "5432", "8443"),
        gold=preserve_gold("5432", "8443", "colleague_confusion_about_port_8443"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "stability", "reactivation": False, "evidence_strength": "weak"},
    )

    spec_20A = make_spec(
        episode_id="PILOT-20A",
        group_id="GRP-RECON-06",
        group_role="reactivated_strong_update",
        paradigm="reconsolidation",
        condition="reactivated",
        fact_type="ci_provider",
        expected_behavior="should_update",
        encoding_contexts=ci_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": True,
            "wording_hint": "User first recalls they run builds on Jenkins (reactivation). Then says the team completed the migration to GitHub Actions over the weekend — all pipelines are now on GH Actions and Jenkins is decommissioned."
        },
        probes=update_probes("the team's CI/CD platform", "Jenkins", "GitHub Actions"),
        gold=update_gold("Jenkins", "GitHub Actions",
                         "user explicitly stated after reactivating the old memory"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "plasticity", "reactivation": True, "evidence_strength": "strong"},
    )

    retry_encoding = [
        "user configures the API client with 3 retries and checks error handling",
        "user discusses the 3-retry policy during a resilience review meeting",
        "user tests the retry logic to verify it stops at 3 attempts"
    ]

    spec_20B = make_spec(
        episode_id="PILOT-20B",
        group_id="GRP-RECON-07",
        group_role="direct_strong_update",
        paradigm="reconsolidation",
        condition="direct",
        fact_type="config_value_v2",
        expected_behavior="should_update",
        encoding_contexts=retry_encoding,
        perturbation={
            "source_type": "user_explicit",
            "evidence_strength": "strong",
            "authoritative": True,
            "reactivation": False,
            "wording_hint": "User directly says they bumped the retry count to 5 retries after load testing showed 3 wasn't enough for the new upstream dependency that has higher P99 latency."
        },
        probes=update_probes("the API retry count", "3 retries", "5 retries"),
        gold=update_gold("3 retries", "5 retries",
                         "user explicitly stated the change"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "plasticity", "reactivation": False, "evidence_strength": "strong"},
    )

    sleep_encoding_std = [
        "user mentions their 11 PM bedtime while planning their evening",
        "user sets a phone reminder for 11 PM wind-down",
        "user declines a late movie because of their 11 PM bedtime"
    ]

    spec_20C = make_spec(
        episode_id="PILOT-20C",
        group_id="GRP-RECON-08",
        group_role="reactivated_weak_evidence",
        paradigm="reconsolidation",
        condition="reactivated_weak",
        fact_type="sleep_schedule",
        expected_behavior="should_preserve",
        encoding_contexts=sleep_encoding_std,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": True,
            "wording_hint": "User first recalls their 11 PM bedtime (reactivation). Then a friend says 'you should really try going to bed at 10 PM — it changed my life.' The user says 'maybe someday' but does NOT change their bedtime."
        },
        perturbation_type="noise",
        probes=preserve_probes("the user's bedtime", "11 PM", "10 PM"),
        gold=preserve_gold("11 PM", "10 PM", "friend_suggestion_of_10PM_bedtime"),
        matched_variables=MATCHED_STD,
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "stability", "reactivation": True, "evidence_strength": "weak"},
    )

    spec_20D = make_spec(
        episode_id="PILOT-20D",
        group_id="GRP-RECON-09",
        group_role="direct_weak_evidence",
        paradigm="reconsolidation",
        condition="direct_weak",
        fact_type="deploy_cadence",
        expected_behavior="should_preserve",
        encoding_contexts=deploy_encoding,
        perturbation={
            "source_type": "third_party",
            "evidence_strength": "weak",
            "authoritative": False,
            "reactivation": False,
            "wording_hint": "Without first mentioning weekly deploys, a platform engineer suggests the team consider bi-weekly deployments for stability. The user says they'll discuss it with the team but makes no commitment — stays weekly for now."
        },
        perturbation_type="noise",
        probes=preserve_probes("the team's deployment cadence", "weekly", "bi-weekly"),
        gold=preserve_gold("weekly", "bi-weekly", "platform_eng_suggestion_of_biweekly"),
        matched_variables=["fact_type", "distractor_values", "filler_plan", "length_tier"],
        variant_variables=VARIANT_STD,
        paradigm_metadata={"test_type": "stability", "reactivation": False, "evidence_strength": "weak"},
    )

    new_specs = [
        spec_10A, spec_10B,
        spec_11A, spec_11B,
        spec_12A,
        spec_12B,
        spec_13A, spec_13B,
        spec_14A, spec_14B, spec_14C,
        spec_15A, spec_15B, spec_15C,
        spec_16A,
        spec_16B,
        spec_17A, spec_17B, spec_17C, spec_17D,
        spec_18A, spec_18B,
        spec_18C,
        spec_18D,
        spec_19A, spec_19B,
        spec_19C, spec_19D,
        spec_20A,
        spec_20B,
        spec_20C,
        spec_20D,
    ]

    all_specs = existing_specs + new_specs

    for s in all_specs:
        if "base_fact_type" not in s:
            s["base_fact_type"] = _base_fact_type(s["fact_type"])
        if "difficulty_target" not in s:
            s["difficulty_target"] = "core"

    group_sizes = Counter(s["group_id"] for s in all_specs)
    _DESIGN_LABELS = {1: "standalone", 2: "paired", 3: "triplet", 4: "quad"}
    for s in all_specs:
        size = group_sizes[s["group_id"]]
        s["group_design"] = _DESIGN_LABELS.get(size, f"group_{size}")

    return all_specs


def summarize(all_specs, vp_by_type, existing_n, new_n, out_path):
    existing_specs = all_specs[:existing_n]; new_specs = all_specs[existing_n:]
    print(f"Wrote {len(all_specs)} specs to {out_path}")
    print(f"  Existing (24-pilot): {len(existing_specs)}")
    print(f"  New:                 {len(new_specs)}")
    print()

    paradigms = Counter(s["paradigm"] for s in all_specs)
    print(f"Paradigm:   {dict(paradigms)}")
    assert all(v == 14 for v in paradigms.values()), f"Paradigm imbalance: {paradigms}"

    domains = Counter(s["domain"] for s in all_specs)
    print(f"Domain:     {dict(domains)}")

    behaviors = Counter(s["expected_behavior"] for s in all_specs)
    print(f"Behavior:   {dict(behaviors)}")

    conditions = Counter(s["condition"] for s in all_specs)
    print(f"Conditions: {dict(conditions)}")

    fact_types = Counter(s["fact_type"] for s in all_specs)
    print(f"\nFact types ({len(fact_types)} unique):")
    for ft, count in sorted(fact_types.items()):
        domain = vp_by_type[ft]["domain"]
        print(f"  {ft:<25} {domain:<10} ×{count}")

    print(f"\nParadigm × Behavior:")
    for p in ["interference", "misinformation", "consolidation", "reconsolidation"]:
        up = sum(1 for s in all_specs if s["paradigm"] == p and s["expected_behavior"] == "should_update")
        pr = sum(1 for s in all_specs if s["paradigm"] == p and s["expected_behavior"] == "should_preserve")
        print(f"  {p:<18} update={up}  preserve={pr}")

    print(f"\nEvidence strength (from perturbation metadata):")
    strong = sum(1 for s in all_specs if s.get("paradigm_metadata", {}).get("evidence_strength") == "strong"
                 or s["perturbation"].get("evidence_strength") == "strong")
    weak = sum(1 for s in all_specs if s.get("paradigm_metadata", {}).get("evidence_strength") == "weak"
               or s["perturbation"].get("evidence_strength") == "weak")
    print(f"  strong={strong}  weak={weak}")

    eids = [s["episode_id"] for s in all_specs]
    assert len(eids) == len(set(eids)), f"Duplicate episode IDs: {[e for e in eids if eids.count(e) > 1]}"
    print(f"\nAll {len(eids)} episode IDs unique ✓")

    missing_ft = [s["fact_type"] for s in all_specs if s["fact_type"] not in vp_by_type]
    assert not missing_ft, f"Missing value pairs for: {missing_ft}"
    print(f"All fact types have value pairs ✓")

    base_fts = Counter(s["base_fact_type"] for s in all_specs)
    print(f"\nBase fact type families ({len(base_fts)} unique):")
    for bft, count in sorted(base_fts.items()):
        variants = sorted(set(s["fact_type"] for s in all_specs if s["base_fact_type"] == bft))
        variants_str = ", ".join(variants) if len(variants) > 1 else variants[0]
        print(f"  {bft:<25} ×{count}  [{variants_str}]")

    group_designs = Counter(s["group_design"] for s in all_specs)
    print(f"\nGroup design: {dict(group_designs)}")

    standalone = [s["episode_id"] for s in all_specs if s["group_design"] == "standalone"]
    if standalone:
        print(f"  Standalone episodes: {', '.join(standalone)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specs", default=str(P.SPECS56), help="shipped latent_specs.json (source of the 9 seed specs)")
    ap.add_argument("--value-pairs", default=str(P.DATA56 / "value_pairs.json"))
    ap.add_argument("--out", default="/tmp/latent_specs_rebuilt.json")
    ap.add_argument("--diff", action="store_true", help="report differences against the shipped file")
    args = ap.parse_args()
    shipped = json.loads(Path(args.specs).read_text())
    by_id = {s["episode_id"]: s for s in shipped["specs"]}
    seeds = [json.loads(json.dumps(by_id[i])) for i in SEED_IDS]
    vp_by_type = load_value_pairs(args.value_pairs)
    specs_24 = stage_24(seeds, vp_by_type)
    specs_56 = stage_56(specs_24, vp_by_type)
    output = {"description": shipped.get("description"), "backend": shipped.get("backend"),
              "model": shipped.get("model"), "specs": specs_56}
    Path(args.out).write_text(json.dumps(output, indent=2, ensure_ascii=False))
    summarize(specs_56, vp_by_type, len(specs_24), len(specs_56) - len(specs_24), args.out)
    if args.diff:
        print("\n=== differences vs shipped file ===")
        for s in specs_56:
            t = by_id.get(s["episode_id"])
            if t is None: print(f"  {s['episode_id']}: not in shipped file"); continue
            for k in sorted(set(s) | set(t)):
                if s.get(k) != t.get(k): print(f"  {s['episode_id']}.{k}: differs")


if __name__ == "__main__":
    main()
