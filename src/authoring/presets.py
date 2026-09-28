"""shared lookup tables used by expand_specs.py, validate_suite.py, scaffold_suite.py.
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Any


PARADIGMS: List[str] = [
    "interference",
    "misinformation",
    "consolidation",
    "reconsolidation",
]

CONDITIONS_BY_PARADIGM: Dict[str, List[str]] = {
    "interference":    ["authoritative_update", "decoy_no_update"],
    "misinformation":  ["user_explicit", "assistant_noise", "third_party_noise", "stale_tool"],
    "consolidation":   ["high", "low", "high_weak_challenge", "low_weak_challenge"],
    "reconsolidation": ["reactivated", "direct", "reactivated_weak", "direct_weak"],
}

EXPECTED_BEHAVIOR: Dict[Tuple[str, str], str] = {
    ("interference", "authoritative_update"):       "should_update",
    ("interference", "decoy_no_update"):            "should_preserve",
    ("misinformation", "user_explicit"):            "should_update",
    ("misinformation", "assistant_noise"):          "should_preserve",
    ("misinformation", "third_party_noise"):        "should_preserve",
    ("misinformation", "stale_tool"):               "should_preserve",
    ("consolidation", "high"):                      "should_update",
    ("consolidation", "low"):                       "should_update",
    ("consolidation", "high_weak_challenge"):       "should_preserve",
    ("consolidation", "low_weak_challenge"):        "should_preserve",
    ("reconsolidation", "reactivated"):             "should_update",
    ("reconsolidation", "direct"):                  "should_update",
    ("reconsolidation", "reactivated_weak"):        "should_preserve",
    ("reconsolidation", "direct_weak"):             "should_preserve",
}


PERTURBATION_TEMPLATES: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("interference", "authoritative_update"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": False,
        "wording_hint": "User clearly states they switched from {initial} to {new}, giving a brief reason.",
    },
    ("interference", "decoy_no_update"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "User's friend mentions that THEY just started using {new}. User does NOT switch — they keep {initial}.",
    },
    ("misinformation", "user_explicit"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": False,
        "wording_hint": "User explicitly tells assistant the {fact} changed from {initial} to {new}.",
    },
    ("misinformation", "assistant_noise"): {
        "source_type": "assistant_hallucination", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "Assistant mistakenly says '{new}' as the {fact}. User corrects: the {fact} is still {initial}.",
    },
    ("misinformation", "third_party_noise"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "A third party mentions {new} in a different context. User's own {fact} remains {initial}.",
    },
    ("misinformation", "stale_tool"): {
        "source_type": "stale_tool", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "A stale tool output shows {new}, but the live state is still {initial}; user notices and dismisses it.",
    },
    ("consolidation", "high"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": False,
        "wording_hint": "After repeatedly reinforcing {initial}, user explicitly switches to {new}.",
    },
    ("consolidation", "low"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": False,
        "wording_hint": "Even though {initial} was only mentioned in passing, user explicitly switches to {new}.",
    },
    ("consolidation", "high_weak_challenge"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "Despite many mentions of {initial}, a weak third-party suggestion of {new} appears; user does not adopt it.",
    },
    ("consolidation", "low_weak_challenge"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "A weak third-party mention of {new} appears; the lightly-reinforced {initial} still wins because nothing replaces it.",
    },
    ("reconsolidation", "reactivated"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": True,
        "wording_hint": "User first revisits/reminds the assistant about {initial} (reactivation), then in the same session updates it to {new}.",
    },
    ("reconsolidation", "direct"): {
        "source_type": "user_explicit", "evidence_strength": "strong",
        "authoritative": True, "reactivation": False,
        "wording_hint": "User updates {initial} → {new} directly, without first revisiting the old value.",
    },
    ("reconsolidation", "reactivated_weak"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": True,
        "wording_hint": "After user reactivates {initial}, a third party ambiguously suggests {new}; user does not accept.",
    },
    ("reconsolidation", "direct_weak"): {
        "source_type": "third_party", "evidence_strength": "weak",
        "authoritative": False, "reactivation": False,
        "wording_hint": "A third party ambiguously suggests {new} without any reactivation of {initial}; user does not accept.",
    },
}


PARADIGM_METADATA_TEMPLATES: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("interference", "authoritative_update"): {"update_type": "authoritative", "interference_test_type": "strong_update"},
    ("interference", "decoy_no_update"):      {"update_type": "decoy",         "interference_test_type": "decoy_resistance"},
    ("misinformation", "user_explicit"):      {"test_type": "plasticity",       "source_type": "user_explicit"},
    ("misinformation", "assistant_noise"):    {"test_type": "noise_resistance", "source_type": "assistant_hallucination"},
    ("misinformation", "third_party_noise"):  {"test_type": "noise_resistance", "source_type": "third_party_noise"},
    ("misinformation", "stale_tool"):         {"test_type": "noise_resistance", "source_type": "stale_tool"},
    ("consolidation", "high"):                {"consolidation_level": "high", "consolidation_test_type": "strong_update", "num_encoding_mentions": 4},
    ("consolidation", "low"):                 {"consolidation_level": "low",  "consolidation_test_type": "strong_update", "num_encoding_mentions": 2},
    ("consolidation", "high_weak_challenge"): {"consolidation_level": "high", "consolidation_test_type": "weak_challenge", "num_encoding_mentions": 4},
    ("consolidation", "low_weak_challenge"):  {"consolidation_level": "low",  "consolidation_test_type": "weak_challenge", "num_encoding_mentions": 2},
    ("reconsolidation", "reactivated"):       {"reactivation": True,  "reconsolidation_test_type": "reactivated_update"},
    ("reconsolidation", "direct"):            {"reactivation": False, "reconsolidation_test_type": "direct_update"},
    ("reconsolidation", "reactivated_weak"):  {"reactivation": True,  "reconsolidation_test_type": "reactivated_weak_challenge"},
    ("reconsolidation", "direct_weak"):       {"reactivation": False, "reconsolidation_test_type": "direct_weak_challenge"},
}


LENGTH_TIERS: Dict[str, Dict[str, int]] = {
    "short": {"num_encoding_sessions": 2, "num_pre_perturbation_fillers": 8,  "num_post_perturbation_fillers": 1},
    "core":  {"num_encoding_sessions": 3, "num_pre_perturbation_fillers": 15, "num_post_perturbation_fillers": 2},
    "long":  {"num_encoding_sessions": 4, "num_pre_perturbation_fillers": 25, "num_post_perturbation_fillers": 3},
}

ENCODING_COUNT_OVERRIDES: Dict[Tuple[str, str], int] = {
    ("consolidation", "high"):                4,
    ("consolidation", "low"):                 2,
    ("consolidation", "high_weak_challenge"): 4,
    ("consolidation", "low_weak_challenge"):  2,
}


def make_filler_plan(length_tier: str) -> Dict[str, Any]:
    counts = LENGTH_TIERS[length_tier]
    pre_total = counts["num_pre_perturbation_fillers"]
    post_total = counts["num_post_perturbation_fillers"]
    weak = max(1, round(pre_total * 0.40))
    near = max(1, round(pre_total * 0.27))
    conf = max(1, round(pre_total * 0.20))
    decoy = max(0, pre_total - weak - near - conf)
    return {
        "pre_perturbation": {
            "total": pre_total,
            "weakly_related_background": weak,
            "near_miss": near,
            "confusable": conf,
            "decoy_nonupdate": decoy,
        },
        "post_perturbation": {
            "total": post_total,
            "types": ["weakly_related_background", "near_miss"][:post_total or 0] or
                     ["weakly_related_background"],
        },
    }


PROBE_TEMPLATES: Dict[Tuple[str, str], List[Dict[str, str]]] = {
    ("interference", "authoritative_update"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "temporal",          "question_hint": "When or why did the user change {fact}?"},
    ],
    ("interference", "decoy_no_update"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a different {fact} mentioned, and if so by whom and does it apply?"},
        {"type": "change_detection",  "question_hint": "Has the user's own {fact} changed?"},
        {"type": "source",            "question_hint": "Who mentioned the alternative {fact}?"},
    ],
    ("misinformation", "user_explicit"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "source",            "question_hint": "Who provided the new {fact} value?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
    ],
    ("misinformation", "assistant_noise"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a different {fact} mentioned in error, and was it accepted?"},
        {"type": "source",            "question_hint": "Who introduced the incorrect {fact}?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
    ],
    ("misinformation", "third_party_noise"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a different {fact} mentioned, and did it apply to the user?"},
        {"type": "source",            "question_hint": "Who mentioned the alternative {fact}?"},
        {"type": "change_detection",  "question_hint": "Has the user's own {fact} changed?"},
    ],
    ("misinformation", "stale_tool"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Did a stale tool output suggest a different {fact}, and did the user accept it?"},
        {"type": "source",            "question_hint": "What was the source of the alternative {fact}?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
    ],
    ("consolidation", "high"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "temporal",          "question_hint": "When or why did the user change {fact}?"},
    ],
    ("consolidation", "low"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "temporal",          "question_hint": "When or why did the user change {fact}?"},
    ],
    ("consolidation", "high_weak_challenge"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a weak challenge to {fact} mentioned, and was it accepted?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who suggested the alternative {fact}?"},
    ],
    ("consolidation", "low_weak_challenge"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a weak challenge to {fact} mentioned, and was it accepted?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who suggested the alternative {fact}?"},
    ],
    ("reconsolidation", "reactivated"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who provided the new {fact} value?"},
    ],
    ("reconsolidation", "direct"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "previous_value",    "question_hint": "What was the user's {fact} before the change?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who provided the new {fact} value?"},
    ],
    ("reconsolidation", "reactivated_weak"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a weak alternative to {fact} mentioned, and was it accepted?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who suggested the alternative {fact}?"},
    ],
    ("reconsolidation", "direct_weak"): [
        {"type": "current_value",     "question_hint": "What is the user's current {fact}?"},
        {"type": "conflict_value",    "question_hint": "Was a weak alternative to {fact} mentioned, and was it accepted?"},
        {"type": "change_detection",  "question_hint": "Has the user's {fact} changed?"},
        {"type": "source",            "question_hint": "Who suggested the alternative {fact}?"},
    ],
}


def build_gold(initial: str, new: str, paradigm: str, condition: str) -> Dict[str, Any]:
    expected = EXPECTED_BEHAVIOR[(paradigm, condition)]
    if expected == "should_update":
        return {
            "current_value":   new,
            "original_value":  initial,
            "previous_value":  initial,
            "has_changed":     True,
            "source_of_change": _source_of_change(paradigm, condition),
            "invalid_sources": [],
        }
    perturb = PERTURBATION_TEMPLATES[(paradigm, condition)]
    status = _conflict_status(paradigm, condition)
    src_label = f"{perturb['source_type']}_mention_of_{new.replace(' ', '_')}"
    return {
        "current_value":   initial,
        "original_value":  initial,
        "previous_value":  None,
        "has_changed":     False,
        "source_of_change": None,
        "invalid_sources": [src_label],
        "conflict_gold": {
            "conflict_value":      new,
            "mentioned":           True,
            "source":              perturb["source_type"],
            "source_label":        src_label,
            "status":              status,
            "applies_to_target":   False,
            "target_remains":      initial,
        },
    }


def _source_of_change(paradigm: str, condition: str) -> str:
    pt = PERTURBATION_TEMPLATES[(paradigm, condition)]
    if pt["source_type"] == "user_explicit":
        return "user explicitly stated the change"
    return f"{pt['source_type']} indicated the new value"


def _conflict_status(paradigm: str, condition: str) -> str:
    return {
        ("interference", "decoy_no_update"):           "different_entity",
        ("misinformation", "assistant_noise"):         "not_accepted",
        ("misinformation", "third_party_noise"):       "different_entity",
        ("misinformation", "stale_tool"):              "stale",
        ("consolidation", "high_weak_challenge"):      "not_accepted",
        ("consolidation", "low_weak_challenge"):       "not_accepted",
        ("reconsolidation", "reactivated_weak"):       "not_accepted",
        ("reconsolidation", "direct_weak"):            "not_accepted",
    }.get((paradigm, condition), "not_accepted")
