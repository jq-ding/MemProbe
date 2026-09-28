from __future__ import annotations
from typing import Dict, List, Tuple
import re


class RuleValidator:
    @staticmethod
    def check_initial_value_in_encoding(
        encoding_sessions: List[Dict],
        initial_value: str,
    ) -> Tuple[bool, str]:
        all_text = " ".join(
            turn["content"]
            for session in encoding_sessions
            for turn in session.get("dialogue", [])
        ).lower()

        if initial_value.lower() in all_text:
            return True, "initial_value found in encoding sessions"

        if _fuzzy_match(initial_value.lower(), all_text):
            return True, "initial_value fuzzy-matched in encoding sessions"

        return False, f"initial_value '{initial_value}' NOT found in encoding sessions"

    @staticmethod
    def check_perturbation_value(
        perturbation_session: Dict,
        spec: Dict,
    ) -> Tuple[bool, str]:
        all_text = " ".join(
            turn["content"]
            for turn in perturbation_session.get("dialogue", [])
        ).lower()

        expected_behavior = spec["expected_behavior"]
        new_value = spec["new_value"].lower()
        initial_value = spec["initial_value"].lower()

        if expected_behavior == "should_update":
            if new_value in all_text or _fuzzy_match(new_value, all_text):
                return True, "new_value found in perturbation (should_update)"
            return False, f"new_value '{spec['new_value']}' NOT in perturbation session"
        else:
            condition = spec["condition"]
            if condition in ("assistant_noise", "third_party_noise"):
                has_noise = new_value in all_text or _fuzzy_match(new_value, all_text)
                has_original = initial_value in all_text or _fuzzy_match(initial_value, all_text)
                if has_noise and has_original:
                    return True, "both noise and original values in perturbation (misinformation)"
                if not has_noise:
                    return False, f"noise value '{spec['new_value']}' NOT in perturbation"
                if not has_original:
                    return False, f"original value '{spec['initial_value']}' NOT reaffirmed in perturbation"
            elif condition == "noise":
                if new_value in all_text or _fuzzy_match(new_value, all_text):
                    return True, "noise value found in perturbation (interference/noise)"
                return False, f"noise value NOT in perturbation"
            elif condition == "scope_restricted":
                if new_value in all_text or _fuzzy_match(new_value, all_text):
                    return True, "scope-restricted value in perturbation"
                return False, "scope-restricted value NOT in perturbation"
            else:
                if new_value in all_text or _fuzzy_match(new_value, all_text):
                    return True, "challenge/weak value in perturbation"
                return False, "challenge/weak value NOT in perturbation"

    @staticmethod
    def check_encoding_count(
        encoding_sessions: List[Dict],
        spec: Dict,
    ) -> Tuple[bool, str]:
        expected = spec["num_encoding_sessions"]
        actual = len(encoding_sessions)
        if actual == expected:
            return True, f"encoding count matches: {actual}"
        return False, f"encoding count mismatch: expected {expected}, got {actual}"

    @staticmethod
    def check_filler_leak(
        filler_sessions: List[Dict],
        initial_value: str,
        new_value: str,
    ) -> Tuple[bool, str]:
        leaks = []
        for i, session in enumerate(filler_sessions):
            text = " ".join(
                turn["content"]
                for turn in session.get("dialogue", [])
            ).lower()
            if initial_value.lower() in text:
                leaks.append(f"filler {i}: contains initial_value")
            if new_value.lower() in text:
                leaks.append(f"filler {i}: contains new_value")

        if not leaks:
            return True, "no target value leaks in fillers"
        return False, f"target value leaks detected: {'; '.join(leaks)}"

    @staticmethod

    @staticmethod
    def check_probe_coverage(
        probes: List[Dict],
        spec: Dict,
    ) -> Tuple[bool, str]:
        legal = {"current_value", "previous_value", "change_detection",
                 "source", "conflict_value", "temporal"}
        core = {"current_value", "change_detection"}

        present = {p["probe_type"] for p in probes}
        illegal = present - legal
        if illegal:
            return False, f"illegal probe types: {sorted(illegal)}"
        missing_core = core - present
        if missing_core:
            return False, f"missing core probes: {sorted(missing_core)}"

        spec_probes = spec.get("probes")
        if spec_probes:
            spec_types = {p["type"] if isinstance(p, dict) else p for p in spec_probes}
            if spec_types != present:
                return False, (f"probe mix mismatch — spec asked for {sorted(spec_types)}, "
                               f"got {sorted(present)}")
        return True, f"{len(present)} legal probes present ({sorted(present)})"

    @staticmethod
    def check_speaker_roles(
        perturbation_session: Dict,
        spec: Dict,
    ) -> Tuple[bool, str]:
        condition = spec["condition"]
        dialogue = perturbation_session.get("dialogue", [])

        if condition == "assistant_noise":
            if dialogue and dialogue[0].get("role") == "assistant":
                return True, "assistant speaks first in assistant_noise perturbation"
            return False, "assistant_noise: first turn should be from assistant"

        elif condition in ("user_explicit", "standard", "high", "low",
                           "reactivated", "direct", "scope_restricted"):
            if dialogue and dialogue[0].get("role") == "user":
                return True, "user speaks first in user-initiated perturbation"
            return False, f"{condition}: first turn should be from user"

        return True, f"speaker role check not applicable for condition '{condition}'"

    def validate_episode(
        self, episode: Dict, spec: Dict
    ) -> List[Tuple[str, bool, str]]:
        results = []

        encoding = [s for s in episode.get("sessions", []) if s.get("session_type") == "encoding"]
        fillers = [s for s in episode.get("sessions", [])
                   if s.get("session_type", "").startswith("filler")]
        perturbation = [s for s in episode.get("sessions", []) if s.get("session_type") == "perturbation"]
        probes = episode.get("probes", [])

        results.append(("encoding_count", *self.check_encoding_count(encoding, spec)))
        results.append(("initial_value_present", *self.check_initial_value_in_encoding(encoding, spec["initial_value"])))

        if perturbation:
            results.append(("perturbation_value", *self.check_perturbation_value(perturbation[0], spec)))
            results.append(("speaker_roles", *self.check_speaker_roles(perturbation[0], spec)))

        if fillers:
            results.append(("filler_leak", *self.check_filler_leak(fillers, spec["initial_value"], spec["new_value"])))

        results.append(("probe_coverage", *self.check_probe_coverage(probes, spec)))

        return results


def _fuzzy_match(target: str, text: str, threshold: float = 0.7) -> bool:
    stripped = re.sub(r'[^\w\s]', ' ', target)
    tokens = [t for t in stripped.split() if len(t) > 3]
    if not tokens:
        return target in text
    text_words = re.findall(r'\w+', text)

    def token_matches(tok: str) -> bool:
        if tok in text:
            return True
        stem_len = max(4, len(tok) - 3)
        prefix = tok[:stem_len]
        for w in text_words:
            if w.startswith(prefix) or tok.startswith(w[:stem_len]):
                return True
        return False

    matched = sum(1 for t in tokens if token_matches(t))
    return matched >= len(tokens) * threshold


def source_clarity_prompt(perturbation_text: str, expected_source: str) -> str:
    system = (
        "You are evaluating whether a dialogue excerpt clearly establishes "
        "the SOURCE of a piece of information. Source clarity is critical for "
        "the MemProbe testbed — each perturbation must have an unambiguous source.\n"
    )

    prompt = f"""Evaluate the source clarity of the following perturbation dialogue.

<perturbation>
{perturbation_text}
</perturbation>

**Expected source type:** {expected_source}

Answer these questions:
1. Is the source of the new/conflicting information clearly identifiable? (yes/no)
2. What source would a reader attribute the information to? (user/assistant/third_party/article/tool/ambiguous)
3. Does the identified source match the expected source type?
4. If the expected behavior is "should_preserve", does the user clearly reject or not adopt the conflicting value?

Output as JSON:
{{
  "source_clear": true/false,
  "identified_source": "user|assistant|third_party|article|tool|ambiguous",
  "matches_expected": true/false,
  "rejection_clear": true/false/null,
  "issues": "<any issues found>"
}}
"""
    return system, prompt


def filler_leak_semantic_check_prompt(
    filler_text: str,
    fact_type: str,
    initial_value: str,
    new_value: str,
) -> str:
    readable_ft = fact_type.replace("_", " ")

    system = (
        "You are checking a filler dialogue session for information leaks. "
        "A 'leak' is any mention, paraphrase, indirect reference, or contextual "
        "cue that could prime or reveal the target fact.\n"
    )

    prompt = f"""Check this filler session for leaks about the target fact.

**Target fact type:** {readable_ft}
**Values to check for:**
- Initial value: "{initial_value}"
- New value: "{new_value}"

<filler_session>
{filler_text}
</filler_session>

Check for:
1. Exact mentions of either value
2. Paraphrases or close variants
3. Indirect references that could prime the target
4. Contextual cues that make the target fact more salient

Output as JSON:
{{
  "has_leak": true/false,
  "leak_type": "exact|paraphrase|indirect|contextual|none",
  "leaked_value": "<what was leaked, if any>",
  "severity": "critical|moderate|minor|none",
  "details": "<explanation>"
}}
"""
    return system, prompt


def probe_consistency_check_prompt(
    probes: List[Dict],
    spec: Dict,
) -> str:
    system = (
        "You are checking whether a set of probe questions and their gold answers "
        "are internally consistent — they should all point to the same underlying "
        "fact state.\n\n"
        "IMPORTANT design note: There are two expected behavior types:\n"
        "- **should_update**: The fact genuinely changed. All probes should reflect the change.\n"
        "- **should_preserve**: A conflicting value was mentioned but NOT adopted. The "
        "conflict_value probe is SUPPOSED to mention the conflicting value — this is NOT "
        "an inconsistency. The correct pattern for should_preserve is:\n"
        "  - current_value = original value (unchanged)\n"
        "  - original_value = same as current_value\n"
        "  - conflict_value = mentions the conflicting value AND explains it was not adopted\n"
        "  - change_detection = 'No' (fact did not change)\n"
        "All four probes pointing to 'the original value is still correct despite a "
        "conflict being mentioned' is CONSISTENT, not contradictory.\n"
    )

    probes_text = "\n".join(
        f"  {i+1}. [{p['probe_type']}] Q: {p['question']}\n"
        f"     Gold: {p['gold_answer']}"
        for i, p in enumerate(probes)
    )

    prompt = f"""Check the consistency of these probe questions and gold answers.

**Expected behavior:** {spec['expected_behavior']}
**Fact type:** {spec['fact_type']}
**Initial value:** "{spec['initial_value']}"
**New value:** "{spec['new_value']}"

**Probes:**
{probes_text}

Check:
1. For should_update: Do current_value and change_detection both confirm the change?
2. For should_update: Does previous_value correctly reference the old value?
3. For should_preserve: Do current_value and original_value both match the initial value?
4. For should_preserve: Does conflict_value correctly identify what was mentioned but NOT adopted?
5. For should_preserve: Does change_detection correctly say the fact did NOT change?
6. Are any gold answers internally contradictory or ambiguous?

Output as JSON:
{{
  "consistent": true/false,
  "issues": ["<list of genuine inconsistencies, if any>"],
  "severity": "none|minor|critical"
}}
"""
    return system, prompt
