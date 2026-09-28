"""
the shared MemProbe evaluation protocol
"""
from __future__ import annotations

import json
import re
import sys
import logging
from typing import Dict, List, Optional, Tuple

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import paths as P  
P.add_src_to_path()
from llm import call_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def format_sessions_as_context(sessions: List[Dict], include_types: Optional[set] = None) -> str:
    parts = []
    for i, s in enumerate(sessions):
        stype = s.get("session_type") or "filler_generic"
        if include_types and stype not in include_types:
            continue
        parts.append(f"--- Session {i+1} ({stype}) ---")
        for msg in s.get("dialogue", []):
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}")
        parts.append("")
    return "\n".join(parts)


def count_mentions_in_text(text: str, value: str) -> int:
    if not value:
        return 0
    return len(re.findall(re.escape(value), text, re.IGNORECASE))


def keyword_relevance(session_text: str, keywords: List[str]) -> float:
    if not keywords:
        return 0.0
    text_lower = session_text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


JUDGE_SYSTEM = """You are a precise memory evaluation judge. You will be given a conversation history between a user and an assistant, followed by probe questions about facts discussed in the conversation.

For each probe, answer based ONLY on what is explicitly stated in the conversation. Do not guess or infer beyond what is written.

Reply in this exact JSON format:
{
  "answers": [
    {
      "probe_type": "<type>",
      "answer": "<your answer>",
      "confidence": <0.0-1.0>,
      "evidence": "<brief quote or reference from the conversation>"
    }
  ]
}"""


def run_llm_judge(episode: Dict, model: str) -> Dict:
    context = format_sessions_as_context(episode["sessions"])
    probes = episode["probes"]

    probe_list = "\n".join(
        f"{i+1}. [{p['probe_type']}] {p['question']}"
        for i, p in enumerate(probes)
    )

    prompt = f"""Here is the full conversation history:

{context}

Now answer these probe questions about the facts discussed:

{probe_list}

Answer each probe based on the conversation above. Be precise and cite evidence."""

    raw = call_llm(JUDGE_SYSTEM, prompt, model=model, temperature=0.0, max_tokens=2000)

    try:
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            result = json.loads(match.group())
            return result
    except json.JSONDecodeError:
        pass

    return {"raw": raw, "answers": []}


_OPTIONAL_PREPS = re.compile(r'\b(at|on|in|by|around|approximately|about|roughly)\s+', re.I)


_UNITS = [
    "retries", "retry", "times", "attempts", "tries",
    "ms", "seconds", "minutes", "hours", "days", "weeks", "months",
    "pm", "am",
    "gb", "mb", "kb", "tb",
    "px", "pt", "em", "rem",
    "%", "percent",
]

def _normalize_value(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'^(?:the|a|an|my|our|their|its)\s+.*?\b(?:is|was|are|were|remains)\s+', '', s)
    s = s.rstrip('.,;:!?')
    s = _OPTIONAL_PREPS.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _extract_number(s: str) -> Optional[str]:
    s = s.strip().lower()
    m = re.match(r'^(\d+(?:\.\d+)?)\s*(?:' + '|'.join(_UNITS) + r')?\.?$', s)
    if m:
        return m.group(1)
    _word_nums = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12",
    }
    word = s.split()[0] if s.split() else ""
    if word in _word_nums:
        return _word_nums[word]
    return None


def _value_match(gold: str, pred: str) -> Tuple[bool, str]:
    gold_l = gold.lower().strip()
    pred_l = pred.lower().strip()

    if gold_l in pred_l:
        return True, "value present in answer"

    gold_n = _normalize_value(gold_l)
    pred_n = _normalize_value(pred_l)
    if gold_n and gold_n in pred_n:
        return True, f"normalized value match ('{gold_n}' in pred)"
    if pred_n and pred_n in gold_n:
        if len(pred_n) >= 1 and _extract_number(pred_n):
            return True, f"reverse numeric match (pred '{pred_n}' in gold '{gold_n}')"

    gold_num = _extract_number(gold_l)
    if gold_num:
        if re.search(r'\b' + re.escape(gold_num) + r'\b', pred_l):
            return True, f"numeric match ({gold_num})"
        pred_num = _extract_number(pred_l)
        if pred_num and pred_num == gold_num:
            return True, f"numeric value match ({gold_num})"

    pred_num = _extract_number(pred_l)
    if pred_num and re.search(r'\b' + re.escape(pred_num) + r'\b', gold_l):
        return True, f"reverse numeric match (pred={pred_num})"

    return False, f"expected '{gold}' not found"


def score_answer(predicted: str, gold: str, probe_type: str,
                 spec: Optional[Dict] = None) -> Dict:
    if not gold or gold == "None":
        return {"match": "skip", "reason": "no gold answer"}

    if predicted.startswith("[ERROR:") or predicted.startswith("[error:"):
        return {"match": "execution_error",
                "reason": f"execution error: {predicted[:80]}"}

    parsed = _parse_json_response(predicted)

    if probe_type in ("current_value", "previous_value"):
        pred_text = parsed.get("answer", predicted) if parsed else predicted
        matched, reason = _value_match(gold, str(pred_text))
        if matched:
            return {"match": "correct", "reason": reason}
        else:
            return {"match": "incorrect", "reason": reason}

    if probe_type == "change_detection":
        gold_changed = gold.lower().strip().startswith("yes")
        if parsed and "changed" in parsed:
            pred_changed = bool(parsed["changed"])
            if pred_changed == gold_changed:
                return {"match": "correct",
                        "reason": f"structured: both say {'changed' if gold_changed else 'unchanged'}"}
            else:
                return {"match": "incorrect",
                        "reason": f"structured: gold={'changed' if gold_changed else 'unchanged'}, "
                                  f"pred={'changed' if pred_changed else 'unchanged'}"}
        return _score_change_detection_legacy(predicted, gold_changed)

    if probe_type == "temporal":
        return _score_temporal(predicted, gold, spec, parsed)

    if probe_type == "source":
        return _score_source(predicted, gold, spec, parsed)

    if probe_type == "conflict_value":
        return _score_conflict(predicted, gold, spec, parsed)

    return {"match": "unknown", "reason": f"unhandled probe type: {probe_type}"}


def _score_change_detection_legacy(predicted: str, gold_changed: bool) -> Dict:
    pred_lower = predicted.lower().strip()
    pred_affirm = ("yes" in pred_lower[:30] and "no" not in pred_lower[:15]) or \
                  ("changed" in pred_lower and
                   not any(neg in pred_lower for neg in
                           ["not changed", "hasn't changed", "did not change",
                            "didn't change", "no change", "unchanged"]))
    pred_deny = any(phrase in pred_lower for phrase in
                    ["no", "remains", "did not change", "hasn't changed",
                     "didn't change", "not changed", "unchanged", "no change"])

    if gold_changed and pred_affirm:
        return {"match": "correct", "reason": "both say changed"}
    elif not gold_changed and (pred_deny or not pred_affirm):
        return {"match": "correct", "reason": "both say unchanged"}
    else:
        return {"match": "incorrect",
                "reason": f"gold={'changed' if gold_changed else 'unchanged'}, "
                          f"pred_affirm={pred_affirm}, pred_deny={pred_deny}"}


def _score_temporal(predicted: str, gold: str, spec: Optional[Dict],
                    parsed: Optional[Dict] = None) -> Dict:
    tg = None
    if spec:
        tg = spec.get("gold", {}).get("temporal_gold")

    if tg and isinstance(tg, dict):
        if parsed:
            return _score_temporal_from_json(parsed, tg, spec)
        return _score_temporal_structured(predicted.lower(), tg, spec)

    return _score_temporal_legacy(predicted.lower(), gold.lower() if gold else "", spec)


def _score_temporal_structured(pred: str, tg: dict, spec: Optional[Dict]) -> Dict:
    checks = {
        "direction": False,
        "trigger": False,
        "reason": False,
        "old_value": False,
    }

    old_v = tg.get("old_value", "").lower()
    new_v = tg.get("new_value", "").lower()
    trigger = tg.get("trigger", "").lower()
    reason = tg.get("reason", "").lower()

    if new_v:
        nv_matched, _ = _value_match(new_v, pred)
        if nv_matched:
            checks["direction"] = True
    change_words = ["change", "switch", "move", "transfer", "update",
                    "adopt", "went to", "replace", "took over", "cancel",
                    "transition", "migrat"]
    if any(w in pred for w in change_words):
        checks["direction"] = True

    if trigger:
        trigger_keywords = [w.strip() for w in re.split(r'[\s,]+', trigger) if len(w.strip()) > 3]
        hits = sum(1 for kw in trigger_keywords if kw in pred)
        if trigger_keywords and hits >= max(1, len(trigger_keywords) * 0.4):
            checks["trigger"] = True
        _trigger_synonyms = {
            "user": ["user", "they", "the person", "their", "i "],
            "stated": ["stated", "said", "told", "mentioned", "announced",
                       "communicated", "explained", "noted"],
            "organizers": ["organizers", "conference", "committee", "official"],
            "team": ["team", "agreed", "decided", "consensus", "voted"],
        }
        for key, synonyms in _trigger_synonyms.items():
            if key in trigger and any(s in pred for s in synonyms):
                checks["trigger"] = True
                break

    if reason:
        reason_keywords = [w.strip() for w in re.split(r'[\s,]+', reason) if len(w.strip()) > 3]
        hits = sum(1 for kw in reason_keywords if kw in pred)
        if reason_keywords and hits >= max(1, len(reason_keywords) * 0.3):
            checks["reason"] = True

    if old_v:
        ov_matched, _ = _value_match(old_v, pred)
        if ov_matched:
            checks["old_value"] = True

    required = checks["direction"] and checks["trigger"]

    if required:
        return {"match": "correct",
                "reason": f"temporal structured checks passed: {checks}",
                "temporal_sub_scores": checks}
    elif checks["direction"] or checks["trigger"]:
        return {"match": "partial",
                "reason": f"temporal structured partial: {checks}",
                "temporal_sub_scores": checks}
    else:
        return {"match": "incorrect",
                "reason": f"temporal structured missed: {checks}",
                "temporal_sub_scores": checks}


def _score_temporal_from_json(parsed: Dict, tg: dict, spec: Optional[Dict]) -> Dict:
    checks = {
        "direction": False,
        "trigger": False,
        "old_value": False,
    }

    gold_new = tg.get("new_value", "").lower()
    gold_old = tg.get("old_value", "").lower()
    gold_trigger = tg.get("trigger", "").lower()

    pred_new = str(parsed.get("new_value", ""))
    if gold_new and pred_new:
        matched, _ = _value_match(gold_new, pred_new)
        if matched:
            checks["direction"] = True
    if parsed.get("changed") is True:
        checks["direction"] = True

    pred_trigger = str(parsed.get("trigger", "")).lower()
    if gold_trigger and pred_trigger:
        trigger_keywords = [w.strip() for w in re.split(r'[\s,]+', gold_trigger) if len(w.strip()) > 3]
        hits = sum(1 for kw in trigger_keywords if kw in pred_trigger)
        if trigger_keywords and hits >= max(1, len(trigger_keywords) * 0.3):
            checks["trigger"] = True

    pred_old = str(parsed.get("old_value", ""))
    if gold_old and pred_old:
        matched, _ = _value_match(gold_old, pred_old)
        if matched:
            checks["old_value"] = True

    if checks["direction"] and checks["trigger"]:
        return {"match": "correct",
                "reason": f"temporal JSON checks passed: {checks}",
                "temporal_sub_scores": checks}
    elif checks["direction"] or checks["trigger"]:
        return {"match": "partial",
                "reason": f"temporal JSON partial: {checks}",
                "temporal_sub_scores": checks}
    else:
        return {"match": "incorrect",
                "reason": f"temporal JSON missed: {checks}",
                "temporal_sub_scores": checks}


def _score_temporal_legacy(pred: str, gold: str, spec: Optional[Dict]) -> Dict:
    checks = {"source_agent": False, "change_direction": False}

    if "user" in gold:
        checks["source_agent"] = any(w in pred for w in
                                     ["user", "they", "the person", "their"])
    elif "assistant" in gold:
        checks["source_agent"] = "assistant" in pred
    elif "third" in gold or "party" in gold:
        checks["source_agent"] = any(w in pred for w in
                                     ["third", "someone else", "colleague", "friend"])
    else:
        checks["source_agent"] = True

    change_words = ["change", "switch", "move", "transfer", "update",
                    "adopt", "went to", "new", "replace", "took over",
                    "cancel", "transition"]
    checks["change_direction"] = any(w in pred for w in change_words)

    if all(checks.values()):
        return {"match": "correct",
                "reason": f"temporal legacy checks passed: {checks}"}
    elif any(checks.values()):
        return {"match": "partial",
                "reason": f"temporal legacy partial: {checks}"}
    else:
        return {"match": "incorrect",
                "reason": f"temporal legacy missed: {checks}"}


_SOURCE_EQUIVALENCES = {
    "user explicitly stated": [
        "user stated", "user said", "user communicated", "user told",
        "user mentioned", "user announced", "from the user",
        "the user directly", "user explicitly",
    ],
    "assistant": [
        "assistant stated", "assistant said", "assistant hallucinated",
        "assistant error", "assistant introduced",
    ],
    "third_party": [
        "third party", "someone else", "colleague", "friend",
        "another person", "external source",
    ],
    "reactivat": [
        "reactivat", "recall", "remember", "referred back",
        "brought up the old", "mentioned the previous owner",
        "after first recalling", "after mentioning",
    ],
}


def _score_source(predicted: str, gold: str, spec: Optional[Dict],
                  parsed: Optional[Dict] = None) -> Dict:
    gold_class = _get_gold_source_class(spec)

    if parsed and "source_class" in parsed:
        pred_class = str(parsed.get("source_class", "unknown")).lower().strip()

        _CLASS_ALIASES = {
            "third-party": "third_party",
            "thirdparty": "third_party",
            "hallucination": "assistant",
            "assistant_hallucination": "assistant",
        }
        pred_class = _CLASS_ALIASES.get(pred_class, pred_class)

        class_match = (pred_class == gold_class)

        cg = spec.get("gold", {}).get("conflict_gold") if spec else None
        if cg:
            gold_accepted = cg.get("applies_to_target", False)
        else:
            gold_accepted = True  

        pred_accepted = parsed.get("accepted")
        accepted_match = (pred_accepted == gold_accepted) if pred_accepted is not None else None

        if class_match:
            return {"match": "correct",
                    "reason": f"source_class match: pred={pred_class} gold={gold_class}",
                    "source_sub_scores": {"class_match": True,
                                          "accepted_match": accepted_match,
                                          "pred_class": pred_class,
                                          "gold_class": gold_class}}
        else:
            if accepted_match is True and pred_class != "unknown":
                return {"match": "partial",
                        "reason": f"source_class mismatch (pred={pred_class} vs gold={gold_class}) "
                                  f"but accepted correct",
                        "source_sub_scores": {"class_match": False,
                                              "accepted_match": True,
                                              "pred_class": pred_class,
                                              "gold_class": gold_class}}
            return {"match": "incorrect",
                    "reason": f"source_class mismatch: pred={pred_class} vs gold={gold_class}",
                    "source_sub_scores": {"class_match": False,
                                          "accepted_match": accepted_match,
                                          "pred_class": pred_class,
                                          "gold_class": gold_class}}

    return _score_source_legacy(predicted, gold, spec)


def _score_source_legacy(predicted: str, gold: str, spec: Optional[Dict]) -> Dict:
    pred_lower = predicted.lower()
    gold_lower = gold.lower()

    if gold_lower in pred_lower:
        return {"match": "correct", "reason": "exact gold substring match"}

    matched_concepts = 0
    total_concepts = 0
    for concept, synonyms in _SOURCE_EQUIVALENCES.items():
        if concept in gold_lower:
            total_concepts += 1
            if any(syn in pred_lower for syn in synonyms) or concept in pred_lower:
                matched_concepts += 1

    entity_match = False
    if spec:
        ci = spec.get("canonical_initial", "")
        cn = spec.get("canonical_new", "")
        if ci and ci.lower() in pred_lower:
            entity_match = True
        if cn and cn.lower() in pred_lower:
            entity_match = True

    if total_concepts > 0 and matched_concepts == total_concepts:
        return {"match": "correct",
                "reason": f"all {total_concepts} source concepts matched via synonyms"}
    elif total_concepts > 0 and matched_concepts > 0:
        if entity_match:
            return {"match": "correct",
                    "reason": f"{matched_concepts}/{total_concepts} concepts + entity match"}
        return {"match": "partial",
                "reason": f"{matched_concepts}/{total_concepts} source concepts matched"}

    has_agent = any(w in pred_lower for w in
                    ["user", "assistant", "they", "the person", "colleague", "friend"])
    has_action = any(w in pred_lower for w in
                     ["stated", "said", "mentioned", "communicated", "confirmed",
                      "denied", "rejected", "corrected", "introduced", "error"])
    has_verdict = any(w in pred_lower for w in
                      ["remains", "still", "unchanged", "not", "did not",
                       "switched", "changed", "transferred", "took over"])

    structural_hits = sum([has_agent, has_action, has_verdict])
    if structural_hits >= 2 and entity_match:
        return {"match": "correct",
                "reason": f"structural match (agent={has_agent}, action={has_action}, "
                          f"verdict={has_verdict}) + entity"}
    elif structural_hits >= 2:
        return {"match": "partial",
                "reason": f"structural partial (agent={has_agent}, action={has_action}, "
                          f"verdict={has_verdict}), no entity"}
    else:
        return {"match": "incorrect",
                "reason": f"source not identified (structural={structural_hits}/3)"}


_SOURCE_SIGNALS = {
    "assistant_hallucination": [
        "assistant", "hallucin", "made up", "fabricat", "error",
        "incorrect", "mistake", "wrong", "generated",
    ],
    "third_party": [
        "colleague", "friend", "coworker", "teammate", "someone",
        "third party", "third-party", "another person", "jamie",
        "they mentioned", "was mentioned by", "their",
        "new hire", "suggested", "suggestion", "rumor", "speculation",
    ],
    "stale_tool": [
        "stale", "outdated", "old", "cached", "dashboard",
        "onboarding doc", "out of date", "out-of-date", "no longer",
    ],
}

_STATUS_SIGNALS = {
    "not_accepted": [
        "not accepted", "not adopted", "rejected", "didn't adopt",
        "did not adopt", "didn't accept", "did not accept",
        "not confirmed", "speculative", "rumor", "unverified",
        "suggested", "proposed", "considered", "hypothetical",
        "not the user", "not yours", "not their", "not his", "not her",
        "guest pass", "one-time", "temporary", "promo",
        "might take over", "may take over", "helping with",
    ],
    "different_entity": [
        "different", "separate", "another", "other",
        "not the user's", "not yours", "not this",
        "their service", "their project", "their team",
        "a colleague's", "a friend's", "a teammate's",
        "for a different", "for another", "for marcus",
        "not for your", "not for the user", "not for this",
        "mock", "local test", "frontend",
    ],
    "stale": [
        "stale", "outdated", "out of date", "out-of-date",
        "no longer valid", "no longer current", "deprecated",
        "old version", "old config", "cached", "was previously",
    ],
}

_NONAPPLY_SIGNALS = [
    "not the user", "not yours", "not this service", "not this project",
    "not for your", "not for the user", "not for this",
    "remains", "still", "unchanged", "didn't change", "did not change",
    "hasn't changed", "not updated", "kept", "stuck with", "sticking with",
    "current", "is still", "stayed", "was not adopted", "not adopted",
    "separate service", "separate project", "different project",
    "different service", "another service", "another project",
    "not as the user's", "but not", "not the same",
]


def _score_conflict(predicted: str, gold: str, spec: Optional[Dict],
                    parsed: Optional[Dict] = None) -> Dict:
    cg = spec.get("gold", {}).get("conflict_gold") if spec else None
    gold_has_conflict = gold.lower().strip().startswith("yes")

    if parsed and "conflict_value_mentioned" in parsed:
        return _score_conflict_structured(parsed, cg, gold_has_conflict, spec)

    return _score_conflict_legacy(predicted, gold, spec, cg, gold_has_conflict)


def _score_conflict_structured(parsed: Dict, cg: Optional[Dict],
                               gold_has_conflict: bool, spec: Optional[Dict]) -> Dict:
    subs = {
        "value_identified": "incorrect",
        "source_identified": "incorrect",
        "status_classified": "incorrect",
        "target_applicability": "incorrect",
    }

    cn = spec.get("canonical_new", "") if spec else ""
    ci = spec.get("canonical_initial", "") if spec else ""

    if gold_has_conflict:
        gold_cv = (cg.get("conflict_value", "") if cg else cn)
        pred_mentioned = parsed.get("conflict_value_mentioned", False)
        pred_cv = str(parsed.get("conflict_value", "") or "")

        if pred_mentioned and gold_cv:
            matched, _ = _value_match(gold_cv, pred_cv)
            if matched:
                subs["value_identified"] = "correct"
        if subs["value_identified"] == "incorrect" and pred_mentioned:
            subs["value_identified"] = "correct"
    else:
        if not parsed.get("conflict_value_mentioned", True):
            subs["value_identified"] = "correct"

    gold_source_class = _get_gold_source_class(spec)
    pred_source_class = str(parsed.get("source_class", "unknown")).lower().strip()

    _SRC_ALIASES = {
        "third-party": "third_party",
        "thirdparty": "third_party",
        "hallucination": "assistant",
        "assistant_hallucination": "assistant",
    }
    pred_source_class = _SRC_ALIASES.get(pred_source_class, pred_source_class)

    if pred_source_class == gold_source_class:
        subs["source_identified"] = "correct"

    gold_status_class = _get_gold_status_class(spec)
    pred_status_class = str(parsed.get("status_class", "unknown")).lower().strip()

    _STATUS_ALIASES = {
        "different_entity": "other_entity",
        "not accepted": "not_accepted",
        "not_confirmed": "not_accepted",
    }
    pred_status_class = _STATUS_ALIASES.get(pred_status_class, pred_status_class)

    if pred_status_class == gold_status_class:
        subs["status_classified"] = "correct"

    gold_applies = cg.get("applies_to_target", False) if cg else False
    pred_applies = parsed.get("applies_to_target")
    if pred_applies is not None and bool(pred_applies) == bool(gold_applies):
        subs["target_applicability"] = "correct"

    target_remains = (cg.get("target_remains", "") if cg else ci)
    pred_current = str(parsed.get("current_value", "") or "")
    if target_remains and pred_current:
        tr_matched, _ = _value_match(target_remains, pred_current)
        if tr_matched and not gold_applies:
            subs["target_applicability"] = "correct"

    n_correct = sum(1 for v in subs.values() if v == "correct")

    if subs["value_identified"] == "incorrect":
        overall = "incorrect"
    elif n_correct >= 3:
        overall = "correct"
    else:
        overall = "partial"

    return {
        "match": overall,
        "reason": (f"value={subs['value_identified']}, source={subs['source_identified']}, "
                   f"status={subs['status_classified']}, applicability={subs['target_applicability']}"),
        "conflict_sub_scores": subs,
        "parsed_fields": {
            "source_class": str(parsed.get("source_class", "")),
            "status_class": str(parsed.get("status_class", "")),
            "applies_to_target": parsed.get("applies_to_target"),
        },
    }


def _score_conflict_legacy(predicted: str, gold: str, spec: Optional[Dict],
                           cg: Optional[Dict], gold_has_conflict: bool) -> Dict:
    pred_lower = predicted.lower()
    cn = spec.get("canonical_new", "") if spec else ""
    ci = spec.get("canonical_initial", "") if spec else ""

    subs = {
        "value_identified": "incorrect",
        "source_identified": "incorrect",
        "status_classified": "incorrect",
        "target_applicability": "incorrect",
    }

    if gold_has_conflict:
        cv = (cg.get("conflict_value", "") if cg else cn).lower()
        if cv:
            matched, _ = _value_match(cv, pred_lower)
            if matched:
                subs["value_identified"] = "correct"
        if subs["value_identified"] == "incorrect" and pred_lower.strip().startswith("yes"):
            subs["value_identified"] = "correct"
    else:
        no_signals = ["no", "none", "not", "no conflict", "wasn't", "were not"]
        if any(s in pred_lower for s in no_signals):
            subs["value_identified"] = "correct"

    expected_source = cg.get("source", "") if cg else ""
    if expected_source and expected_source in _SOURCE_SIGNALS:
        if any(kw in pred_lower for kw in _SOURCE_SIGNALS[expected_source]):
            subs["source_identified"] = "correct"
    if subs["source_identified"] == "incorrect":
        all_source_kws = [kw for kws in _SOURCE_SIGNALS.values() for kw in kws]
        if any(kw in pred_lower for kw in all_source_kws):
            subs["source_identified"] = "correct"

    expected_status = cg.get("status", "") if cg else ""
    if expected_status and expected_status in _STATUS_SIGNALS:
        if any(kw in pred_lower for kw in _STATUS_SIGNALS[expected_status]):
            subs["status_classified"] = "correct"
    if subs["status_classified"] == "incorrect":
        all_status_kws = [kw for kws in _STATUS_SIGNALS.values() for kw in kws]
        if any(kw in pred_lower for kw in all_status_kws):
            subs["status_classified"] = "correct"

    expected_applies = cg.get("applies_to_target", False) if cg else False
    target_remains = (cg.get("target_remains", "") if cg else ci).lower()
    if not expected_applies:
        if any(kw in pred_lower for kw in _NONAPPLY_SIGNALS):
            subs["target_applicability"] = "correct"
        if target_remains:
            tr_matched, _ = _value_match(target_remains, pred_lower)
            if tr_matched:
                subs["target_applicability"] = "correct"
    else:
        accept_signals = ["accepted", "adopted", "confirmed", "switched",
                          "changed to", "updated to", "moved to", "now using"]
        if any(kw in pred_lower for kw in accept_signals):
            subs["target_applicability"] = "correct"

    n_correct = sum(1 for v in subs.values() if v == "correct")
    if subs["value_identified"] == "incorrect":
        overall = "incorrect"
    elif n_correct >= 3:
        overall = "correct"
    else:
        overall = "partial"

    return {
        "match": overall,
        "reason": (f"value={subs['value_identified']}, source={subs['source_identified']}, "
                   f"status={subs['status_classified']}, applicability={subs['target_applicability']}"),
        "conflict_sub_scores": subs,
    }


READER_SYSTEM = """You are a memory system being evaluated. You have access to the full conversation history between a user and an assistant. Answer the probe question based on this history.

You MUST respond with ONLY a valid JSON object in the exact format specified in the question. Do not include any text, explanation, or markdown outside the JSON object."""


_PROBE_SCHEMAS = {
    "current_value": """\
Respond with ONLY this JSON:
{
  "answer": "<the current value>",
  "reason": "<brief evidence from conversation>"
}""",

    "previous_value": """\
Respond with ONLY this JSON:
{
  "answer": "<the previous/original value before any change>",
  "reason": "<brief evidence from conversation>"
}""",

    "change_detection": """\
Respond with ONLY this JSON:
{
  "changed": true or false,
  "current_value": "<current value>",
  "previous_value": "<previous value if changed, else null>",
  "reason": "<brief evidence from conversation>"
}""",

    "source": """\
Respond with ONLY this JSON:
{
  "source_description": "<who introduced or communicated this fact>",
  "source_class": "<one of: user, assistant, third_party, tool, stale_tool, other_entity, hypothetical, unknown>",
  "action": "<what they did: stated, mentioned, suggested, hallucinated, etc.>",
  "accepted": true or false,
  "current_value": "<the current value of the fact>",
  "reason": "<brief evidence from conversation>"
}""",

    "conflict_value": """\
Respond with ONLY this JSON:
{
  "conflict_value_mentioned": true or false,
  "conflict_value": "<the conflicting value, or null if none>",
  "source": "<who or what introduced the conflicting value>",
  "source_class": "<one of: assistant, third_party, stale_tool, other_entity, hypothetical, unknown>",
  "status": "<what happened to the conflicting value>",
  "status_class": "<one of: accepted, not_accepted, stale, hypothetical, other_entity, superseded, unknown>",
  "applies_to_target": true or false,
  "current_value": "<the actual current value>",
  "reason": "<brief evidence from conversation>"
}""",

    "temporal": """\
Respond with ONLY this JSON:
{
  "changed": true or false,
  "trigger": "<what event or reason caused the change>",
  "old_value": "<value before the change>",
  "new_value": "<value after the change>",
  "timing": "<when or in what context the change happened>",
  "reason": "<brief evidence from conversation>"
}""",
}


def _parse_json_response(text: str) -> Optional[Dict]:
    if not text or text.startswith("[ERROR:") or text.startswith("[error:"):
        return None
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)

    try:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    brace_pos = cleaned.find('{')
    if brace_pos == -1:
        return None
    fragment = cleaned[brace_pos:]
    for suffix in ['"}', '"}', 'null}', '}', '"}\n}', '}\n}']:
        try:
            return json.loads(fragment + suffix)
        except json.JSONDecodeError:
            continue

    try:
        last_comma = fragment.rfind(',')
        if last_comma > 0:
            truncated = fragment[:last_comma] + '}'
            return json.loads(truncated)
    except json.JSONDecodeError:
        pass

    return None


def _get_gold_source_class(spec: Optional[Dict]) -> str:
    if not spec:
        return "unknown"
    cg = spec.get("gold", {}).get("conflict_gold")
    if cg:
        _SRC_MAP = {
            "assistant_hallucination": "assistant",
            "third_party": "third_party",
            "stale_tool": "stale_tool",
        }
        return _SRC_MAP.get(cg.get("source", ""), "unknown")
    condition = spec.get("condition", "")
    if condition in ("user_explicit", "authoritative_update", "reactivated", "direct"):
        return "user"
    elif condition == "assistant_noise":
        return "assistant"
    elif condition in ("third_party_noise", "decoy_no_update"):
        return "third_party"
    elif condition == "stale_tool":
        return "stale_tool"
    elif condition in ("high", "low"):
        return "user"
    elif condition in ("high_weak_challenge", "low_weak_challenge",
                       "reactivated_weak", "direct_weak"):
        return "third_party"
    return "unknown"


def _get_gold_status_class(spec: Optional[Dict]) -> str:
    if not spec:
        return "unknown"
    cg = spec.get("gold", {}).get("conflict_gold")
    if not cg:
        return "unknown"
    _STATUS_MAP = {
        "not_accepted": "not_accepted",
        "different_entity": "other_entity",
        "stale": "stale",
    }
    return _STATUS_MAP.get(cg.get("status", ""), "unknown")


def run_full_context(episode: Dict, probe: Dict, model: str) -> str:
    context = format_sessions_as_context(episode["sessions"])
    schema = _PROBE_SCHEMAS.get(probe["probe_type"], "")
    prompt = f"""Conversation history:

{context}

Question: {probe['question']}

{schema}"""

    try:
        return call_llm(READER_SYSTEM, prompt, model=model, temperature=0.0, max_tokens=4096)
    except Exception as e:
        log.warning(f"  full_context call failed ({e.__class__.__name__}): {e}")
        return f"[ERROR: {e.__class__.__name__}]"


RAG_SYSTEM = """You are a memory system being evaluated. You have access to a SUBSET of conversation sessions retrieved by relevance. Answer the probe question based only on these sessions.

You MUST respond with ONLY a valid JSON object in the exact format specified in the question. Do not include any text, explanation, or markdown outside the JSON object."""


def run_naive_rag(episode: Dict, probe: Dict, spec: Dict, model: str, top_k: int = 5) -> Tuple[str, List[int]]:
    keywords = []
    ci = spec.get("canonical_initial", "")
    cn = spec.get("canonical_new", "")
    fact_type = spec.get("fact_type", "")

    for v in [ci, cn] + spec.get("distractor_values", []):
        keywords.extend(v.split())
    keywords.extend(fact_type.replace("_", " ").split())
    stop_words = {"the", "a", "an", "is", "was", "did", "does", "do", "at", "to", "of",
                  "in", "for", "and", "or", "it", "its", "any", "what", "who", "how",
                  "their", "they", "this", "that", "has", "have", "been", "ever", "point"}
    for w in probe["question"].split():
        w_clean = re.sub(r'[^\w]', '', w.lower())
        if w_clean and w_clean not in stop_words and len(w_clean) > 2:
            keywords.append(w_clean)

    keywords = list(set(keywords))

    scored = []
    for i, s in enumerate(episode["sessions"]):
        text = " ".join(m.get("content", "") for m in s.get("dialogue", []))
        score = keyword_relevance(text, keywords)
        scored.append((score, i, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_sessions = scored[:top_k]
    top_sessions.sort(key=lambda x: x[1])

    retrieved_indices = [idx for _, idx, _ in top_sessions]
    retrieved = [s for _, _, s in top_sessions]

    context = format_sessions_as_context(retrieved)
    schema = _PROBE_SCHEMAS.get(probe["probe_type"], "")
    prompt = f"""Retrieved conversation sessions (subset):

{context}

Question: {probe['question']}

{schema}"""

    try:
        answer = call_llm(RAG_SYSTEM, prompt, model=model, temperature=0.0, max_tokens=4096)
    except Exception as e:
        log.warning(f"  naive_rag call failed ({e.__class__.__name__}): {e}")
        answer = f"[ERROR: {e.__class__.__name__}]"
    return answer, retrieved_indices


def run_latest_value(episode: Dict, spec: Dict) -> Dict:
    ci = spec.get("canonical_initial", "")
    cn = spec.get("canonical_new", "")
    distractors = spec.get("distractor_values", [])

    all_values = [ci, cn] + distractors
    last_pos = {v: -1 for v in all_values}

    pos = 0
    for s in episode["sessions"]:
        text = " ".join(m.get("content", "") for m in s.get("dialogue", []))
        for v in all_values:
            if count_mentions_in_text(text, v) > 0:
                last_pos[v] = pos
        pos += 1

    best_val = ci  
    best_pos = -1
    for v, p in last_pos.items():
        if p > best_pos:
            best_pos = p
            best_val = v

    results = {}
    for probe in episode["probes"]:
        ptype = probe["probe_type"]
        if ptype == "current_value":
            results[ptype] = best_val
        elif ptype == "change_detection":
            results[ptype] = "Yes" if best_val != ci else "No"
        elif ptype == "previous_value":
            results[ptype] = ci if best_val != ci else "None"
        elif ptype in ("source", "conflict_value"):
            results[ptype] = f"Last mentioned value is {best_val}"

    return results


def run_always_update(episode: Dict, spec: Dict) -> Dict:
    ci = spec.get("canonical_initial", "")
    cn = spec.get("canonical_new", "")

    results = {}
    for probe in episode["probes"]:
        ptype = probe["probe_type"]
        if ptype == "current_value":
            results[ptype] = cn
        elif ptype == "change_detection":
            results[ptype] = "Yes, the value has changed"
        elif ptype == "previous_value":
            results[ptype] = ci
        elif ptype == "source":
            results[ptype] = f"The value was updated from {ci} to {cn}"
        elif ptype == "conflict_value":
            results[ptype] = f"Yes, {cn} was mentioned as a conflicting value"
        elif ptype == "temporal":
            results[ptype] = f"The user changed from {ci} to {cn}"
    return results


def run_always_preserve(episode: Dict, spec: Dict) -> Dict:
    ci = spec.get("canonical_initial", "")

    results = {}
    for probe in episode["probes"]:
        ptype = probe["probe_type"]
        if ptype == "current_value":
            results[ptype] = ci
        elif ptype == "change_detection":
            results[ptype] = "No, the value has not changed"
        elif ptype == "previous_value":
            results[ptype] = "None"
        elif ptype == "source":
            results[ptype] = f"The value is {ci}, as originally stated by the user"
        elif ptype == "conflict_value":
            results[ptype] = "No conflicting values were introduced"
        elif ptype == "temporal":
            results[ptype] = f"The value has always been {ci}"
    return results
