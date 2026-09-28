"""
Prompt templates for the MemProbe episode generation pipeline.
"""

from __future__ import annotations
import random
from typing import Dict, List, Optional


DOMAIN_STYLE = {
    "personal": (
        "This is a casual, personal conversation between a user and their AI assistant. "
        "The tone is informal and friendly — like texting a knowledgeable friend. "
        "The user talks about daily life: food, fitness, travel, health, scheduling, etc."
    ),
    "work": (
        "This is a professional conversation between a user and their AI assistant "
        "in a workplace context. The tone is professional but not overly formal — "
        "like talking to a competent colleague. Topics include meetings, deadlines, "
        "project management, code reviews, sprint planning, etc."
    ),
    "agentic": (
        "This is a technical conversation between a developer/engineer and an AI coding "
        "assistant. The assistant has access to tools and can show tool outputs. "
        "Include [TOOL_OUTPUT] blocks where the assistant runs commands, queries databases, "
        "or checks system status. The conversation involves git branches, configs, databases, "
        "APIs, builds, deployments, etc. Tool outputs should look realistic (command-line "
        "output, YAML configs, SQL results, kubectl output, etc.)."
    ),
}

ENCODING_CONTEXTS = {
    "personal": {
        "residential_city":          ["restaurant recommendation", "commute planning", "weather discussion", "neighborhood activity", "visitor directions"],
        "current_gym":               ["scheduling workout", "injury/stretching advice", "gym equipment question", "membership issue", "workout routine"],
        "favorite_cafe_for_work":    ["finding wifi spot", "meeting a friend", "coffee recommendation", "remote work setup", "neighborhood exploration"],
        "diet_preference":           ["ordering food", "travel food planning", "health checkup", "social event", "restaurant suggestion"],
        "sleep_schedule_preference": ["energy/productivity discussion", "social scheduling", "health question", "lifestyle preference", "morning routine"],
        "doctor_appointment_time":   ["weekly planning", "reminder request", "scheduling conflict", "preparation question", "transportation planning"],
        "meetup_location":           ["directions request", "what to wear/bring", "backup plan", "nearby activities", "timing discussion"],
        "vacation_plan_destination": ["booking help", "packing advice", "activity planning", "language/culture prep", "budget planning"],
        "current_gym_v2":            ["workout planning", "membership question", "class schedule", "commute to gym", "fitness goals"],
        "favorite_coffee":           ["morning routine", "cafe recommendation", "meeting spot", "coffee subscription", "remote work spot"],
        "commute_method":            ["route planning", "weather impact", "schedule optimization", "gear discussion", "cost comparison"],
        "diet_preference_v2":        ["meal planning", "restaurant selection", "grocery shopping", "health checkup", "social dining"],
        "sleep_schedule":            ["evening routine", "alarm setting", "energy management", "social planning", "health discussion"],
    },
    "work": {
        "meeting_room":              ["booking confirmation", "AV setup", "room change notification", "capacity question", "directions for visitor"],
        "meeting_time":              ["calendar conflict", "timezone coordination", "agenda prep", "rescheduling discussion", "reminder request"],
        "project_owner":             ["bug assignment", "roadmap planning", "escalation question", "handoff discussion", "status update"],
        "submission_deadline":       ["timeline planning", "progress check", "co-author coordination", "formatting question", "submission logistics"],
        "task_priority":             ["sprint planning", "standup update", "stakeholder report", "resource allocation", "scope discussion"],
        "current_experiment_name":   ["results review", "parameter tuning", "comparison discussion", "logging setup", "stakeholder demo"],
        "preferred_meeting_style":   ["scheduling new meeting", "team feedback", "remote/hybrid discussion", "1-on-1 format", "time management"],
        "assigned_reviewer":         ["PR status check", "review feedback", "reassignment discussion", "review timeline", "code standards"],
        "team_standup":              ["calendar planning", "timezone coordination", "attendance tracking", "format discussion", "agenda preparation"],
        "deploy_cadence":            ["release planning", "sprint review", "risk assessment", "rollback discussion", "monitoring setup"],
        "submission_deadline_v2":    ["progress tracking", "review coordination", "formatting preparation", "conflict resolution", "reminder setup"],
        "project_owner_v2":          ["bug assignment", "architecture decision", "escalation routing", "handoff planning", "status reporting"],
        "ci_provider":               ["pipeline debugging", "plugin configuration", "build optimization", "migration planning", "credential setup"],
    },
    "agentic": {
        "active_branch":             ["CI status check", "diff review", "merge discussion", "conflict resolution", "feature progress"],
        "config_value":              ["debugging failures", "performance tuning", "compliance check", "environment comparison", "deployment prep"],
        "selected_database":         ["migration planning", "query optimization", "backup discussion", "schema change", "performance analysis"],
        "current_target_table":      ["query writing", "data validation", "schema review", "ETL pipeline", "reporting setup"],
        "active_api_endpoint":       ["integration testing", "service discovery", "load testing", "migration planning", "documentation update"],
        "latest_build_status":       ["deployment decision", "test investigation", "release planning", "CI debugging", "platform compatibility"],
        "task_completion_state":     ["standup preparation", "sprint review", "blocker resolution", "handoff planning", "progress tracking"],
        "reported_port_number":      ["connection setup", "firewall configuration", "service debugging", "monitoring setup", "documentation update"],
        "reported_port":             ["connection setup", "firewall configuration", "service debugging", "monitoring setup", "documentation update"],
        "log_level":                 ["debugging session", "log volume analysis", "incident investigation", "deployment configuration", "performance monitoring"],
        "config_value_v2":           ["retry policy review", "resilience testing", "error handling discussion", "deployment config", "SLA compliance"],
        "reported_port_v2":          ["database connection", "firewall rule setup", "service health check", "connection string update", "environment configuration"],
    },
}

FACT_TYPE_READABLE = {
    "residential_city": "city of residence",
    "current_gym": "gym",
    "favorite_cafe_for_work": "favorite café for working",
    "diet_preference": "dietary preference",
    "sleep_schedule_preference": "sleep schedule",
    "doctor_appointment_time": "doctor appointment time",
    "meetup_location": "meetup location",
    "vacation_plan_destination": "vacation destination",
    "meeting_room": "meeting room",
    "meeting_time": "meeting time",
    "project_owner": "project owner",
    "submission_deadline": "submission deadline",
    "task_priority": "top priority",
    "current_experiment_name": "current experiment",
    "preferred_meeting_style": "preferred meeting style",
    "assigned_reviewer": "assigned reviewer",
    "active_branch": "active git branch",
    "config_value": "configuration value",
    "selected_database": "database engine",
    "current_target_table": "target table",
    "active_api_endpoint": "API endpoint",
    "latest_build_status": "latest build status",
    "task_completion_state": "task status",
    "reported_port_number": "service port number",
    "reported_port": "service port number",
    "current_gym_v2": "gym",
    "favorite_coffee": "go-to coffee shop",
    "commute_method": "commute method",
    "diet_preference_v2": "dietary preference",
    "sleep_schedule": "regular bedtime",
    "team_standup": "daily standup time",
    "deploy_cadence": "deployment cadence",
    "submission_deadline_v2": "report submission deadline",
    "project_owner_v2": "module owner",
    "ci_provider": "CI/CD platform",
    "log_level": "application log level",
    "config_value_v2": "API retry count",
    "reported_port_v2": "database service port",
}


def encoding_session_prompt(
    spec: Dict,
    session_idx: int,
    context_theme: str,
    seed_example: Optional[str] = None,
) -> str:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))
    total_sessions = spec["num_encoding_sessions"]

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "Your job is to generate a SINGLE realistic user-assistant conversation session "
        "where a specific fact is naturally embedded in the dialogue.\n\n"
        "CRITICAL RULES:\n"
        "1. The fact must appear NATURALLY through conversation context — the user should "
        "NOT announce it directly (e.g., 'Let me tell you my diet is...')\n"
        "2. The fact should emerge as a detail within a conversation about the given theme\n"
        "3. Keep the session 4-8 turns total (2-4 exchanges)\n"
        "4. Use ONLY the exact fact value provided — do not modify, paraphrase, or embellish it\n"
        "5. The assistant should respond helpfully and naturally\n"
    )

    agentic_note = ""
    if domain == "agentic":
        agentic_note = (
            "\n**AGENTIC DOMAIN**: Include [TOOL_OUTPUT] blocks where appropriate. "
            "The assistant runs commands/queries and shows results. Tool outputs should "
            "look realistic (command-line, YAML, JSON, SQL results, etc.).\n"
            "Format tool outputs as:\n"
            "[TOOL_OUTPUT] <realistic output>\n"
        )

    few_shot = ""
    if seed_example:
        few_shot = f"\n**Example (for reference — do NOT copy directly):**\n```\n{seed_example}\n```\n"

    prompt = f"""Generate a single encoding session for the MemProbe testbed.

**Specifications:**
- Domain: {domain}
- Domain style: {DOMAIN_STYLE[domain]}
- Fact type: {readable_ft}
- Fact to embed: "{initial_value}"
- Conversation theme: {context_theme}
- Session {session_idx + 1} of {total_sessions} encoding sessions
{agentic_note}
**Requirements:**
- The user's message should naturally lead to the fact "{initial_value}" appearing in the conversation
- The fact can appear in either the user's message or the assistant's response (or both), but the user must be the SOURCE of the information
- If this is session {session_idx + 1} of {total_sessions}, vary the angle — don't repeat the same conversational setup as other sessions
- Generate exactly ONE session (one complete user-assistant exchange)
{few_shot}
**Output format** (use exactly this format):
[USER] <user message>

[ASST] <assistant response>

[USER] <optional follow-up>

[ASST] <optional follow-up response>
"""
    return system, prompt


def _perturbation_instructions(spec: Dict) -> str:
    paradigm = spec["paradigm"]
    condition = spec["condition"]
    pt = spec["perturbation_type"]
    initial = spec["initial_value"]
    new = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(spec["fact_type"], spec["fact_type"].replace("_", " "))
    meta = spec.get("paradigm_metadata", {})

    if paradigm == "interference" and condition in ("standard", "authoritative_update"):
        return f"""**PERTURBATION TYPE: Direct Update (interference/{condition})**
The user DIRECTLY and EXPLICITLY states that their {readable_ft} has changed.
- Old value the user previously used: "{initial}"
- New value the user is switching to: "{new}"

CRITICAL — you MUST use these EXACT values verbatim:
  - The user must clearly reference "{initial}" (the old value they are moving away from).
  - The user must clearly adopt "{new}" (the new value that replaces it).
Do NOT substitute either value with an invented alternative. Do NOT paraphrase them
into different named entities. The values "{initial}" and "{new}" are experimental
controls and any substitution invalidates the episode.

The update is unambiguous — there is no question about whether it happened.
The assistant acknowledges and confirms the switch to "{new}"."""

    elif paradigm == "interference" and condition in ("noise", "decoy_no_update"):
        return f"""**PERTURBATION TYPE: Near-Miss Decoy (interference/{condition})**
The value "{new}" appears in conversation, but it is about a DIFFERENT entity/person/context
— NOT about the user's own {readable_ft}.
- User's actual {readable_ft} (UNCHANGED throughout): "{initial}"
- Decoy value (mentioned incidentally about someone/something else): "{new}"

CRITICAL — you MUST use these EXACT values verbatim:
  - The user's own {readable_ft} must be described as still "{initial}".
  - The decoy value that a third party / other context mentions must be literally "{new}".
Do NOT substitute either value with an invented alternative. Do NOT paraphrase them
into different named entities.

The user does NOT change their own {readable_ft}. The decoy value is mentioned casually
by a third party (e.g., "my friend...", "I walked past...", "I read about...").
The assistant should NOT treat this as an update to the user's {readable_ft}."""

    elif paradigm == "interference" and condition == "scope_restricted":
        return f"""**PERTURBATION TYPE: Scope-Restricted Update (interference/scope_restricted)**
A REAL change happens, confirmed by the user AND tool output, but it applies to a DIFFERENT SCOPE than the target fact.
- Target scope's {readable_ft}: "{initial}" (UNCHANGED)
- Different scope's value: "{new}" (genuinely changed, confirmed)
Example: production database stays PostgreSQL, but staging migrated to CockroachDB.
The user explicitly confirms the change applies only to the other scope.
Include [TOOL_OUTPUT] confirming the change in the other scope.
The assistant should acknowledge the scope boundary."""

    elif paradigm == "misinformation" and condition == "user_explicit":
        return f"""**PERTURBATION TYPE: User Explicit Update (misinformation/user_explicit)**
The user DIRECTLY corrects or updates the fact.
- Old value: "{initial}"
- New value: "{new}"
The user explicitly states the change (e.g., "I rescheduled...", "It's now...", "I need to change...").
This is an authoritative update from the user — the system SHOULD update."""

    elif paradigm == "misinformation" and condition == "assistant_noise":
        return f"""**PERTURBATION TYPE: Assistant Noise (misinformation/assistant_noise)**
The ASSISTANT proactively but INCORRECTLY states or implies the new value.
- Correct value: "{initial}"
- Incorrect value the assistant states: "{new}"

**CRITICAL — DIALOGUE STRUCTURE (MUST FOLLOW EXACTLY):**
1. The ASSISTANT speaks FIRST (turn 1, role=assistant) with an UNPROMPTED reminder, summary, or proactive notification that incorrectly states "{new}". There is NO user message before the assistant's first turn.
2. The USER (turn 2) corrects the assistant, rejecting "{new}" and reaffirming "{initial}".
3. The ASSISTANT apologizes and acknowledges the correct value "{initial}".
4. Continue the conversation naturally for 1-2 more turn pairs.

The first dialogue turn MUST have role="assistant". This is non-negotiable — the whole point of the assistant_noise condition is that the assistant volunteers wrong information without being asked.
CRITICAL: The user must clearly reject the incorrect value and reaffirm "{initial}"."""

    elif paradigm == "misinformation" and condition == "third_party_noise":
        return f"""**PERTURBATION TYPE: Third-Party Noise (misinformation/third_party_noise)**
A third party (relayed through the user) mentions the wrong value.
- Correct value: "{initial}"
- Incorrect value mentioned by third party: "{new}"
The user reports what someone else said/wrote (e.g., "My mom thinks...", "Marcus said...", "The old doc says...").
The user then CONFIRMS the original value is correct.
CRITICAL: The user must clearly establish that the third party is wrong and "{initial}" is still correct."""

    elif paradigm == "consolidation" and condition in ("high", "low"):
        return f"""**PERTURBATION TYPE: Direct Update (consolidation/update)**
The user DIRECTLY states a change to {readable_ft}.
- Old value: "{initial}"
- New value: "{new}"
This is the same as interference/standard — a clear, unambiguous update from the user.
The assistant acknowledges the change."""

    elif paradigm == "consolidation" and condition in ("high_challenge", "low_challenge", "high_weak_challenge", "low_weak_challenge"):
        challenge_source = meta.get("challenge_source", "non_authoritative")
        return f"""**PERTURBATION TYPE: Weak Challenge (consolidation/challenge)**
A NON-AUTHORITATIVE source provides weak evidence suggesting a different value.
- Current value: "{initial}" (should be PRESERVED)
- Challenge value: "{new}" (from a weak/non-authoritative source)
- Challenge source type: {challenge_source}
The challenge comes from something like: a news article, a blog post, a colleague's speculation,
a rumor, or an outdated document. It is NOT a direct statement from the user.
The user DOES NOT confirm the change. They may express uncertainty but ultimately decide to keep the current value.
CRITICAL: The challenge must be clearly non-authoritative. The user should NOT adopt the new value."""

    elif paradigm == "reconsolidation" and condition == "reactivated":
        return f"""**PERTURBATION TYPE: Reactivation Then Update (reconsolidation/reactivated)**
Two-part perturbation:
PART 1 — REACTIVATION: The user explicitly recalls the old memory.
  e.g., "Remember the X I told you about?" / "You know how I said my {readable_ft} is..."
  The assistant confirms the old value: "{initial}"
PART 2 — UPDATE: Immediately after reactivation, the user states the change.
  e.g., "Well, actually I've decided to change it to..."
  - Old value (reactivated): "{initial}"
  - New value: "{new}"
Both parts must happen in the SAME session. The reactivation must come BEFORE the update."""

    elif paradigm == "reconsolidation" and condition == "direct":
        return f"""**PERTURBATION TYPE: Direct Update Without Reactivation (reconsolidation/direct)**
The user states the change WITHOUT first recalling the old value.
- Old value: "{initial}" (NOT mentioned in this session)
- New value: "{new}"
The user simply announces the new state (e.g., "I changed my plan to...", "We migrated to...").
There is NO "remember when..." or recall of the old value before the update.
CRITICAL: Do NOT include any reference to the old value before stating the new one."""

    elif paradigm == "reconsolidation" and condition == "reactivated_weak":
        return f"""**PERTURBATION TYPE: Reactivation Then Weak Evidence (reconsolidation/reactivated_weak)**
Two-part perturbation:
PART 1 — REACTIVATION: The user explicitly recalls the old memory.
  e.g., "About my {readable_ft} — it's {initial}, right?"
  The assistant confirms: "{initial}"
PART 2 — WEAK EVIDENCE: After reactivation, weak/ambiguous evidence for a different value appears.
  - Current value: "{initial}" (should be PRESERVED)
  - Weak evidence value: "{new}" (from non-authoritative source)
  e.g., someone mentioned it, an article suggested it, a rumor, unconfirmed report.
  The user does NOT confirm the change — they either dismiss it or express uncertainty but keep the original.
CRITICAL: The evidence must be clearly non-authoritative. The user must NOT adopt the new value."""

    elif paradigm == "reconsolidation" and condition == "direct_weak":
        return f"""**PERTURBATION TYPE: Direct Weak Evidence Without Reactivation (reconsolidation/direct_weak)**
Weak/ambiguous evidence for a different value appears WITHOUT the user first recalling the old value.
- Current value: "{initial}" (should be PRESERVED, NOT mentioned before the evidence)
- Weak evidence value: "{new}" (from non-authoritative source)
The evidence comes from a non-authoritative source: a colleague's suggestion, an article,
a rumor, an outdated document, or an unconfirmed report.
There is NO "remember when..." or explicit recall of "{initial}" before the evidence appears.
The user does NOT confirm the change — they either dismiss it or express uncertainty but keep the original.
CRITICAL: Do NOT include any reactivation of the old value before the weak evidence.
The evidence must be clearly non-authoritative. The user must NOT adopt the new value."""

    elif paradigm == "misinformation" and condition == "stale_tool":
        return f"""**PERTURBATION TYPE: Stale Tool Output (misinformation/stale_tool)**
A TOOL or DOCUMENT returns OUTDATED information that contradicts the user's known value.
- Correct value: "{initial}"
- Stale value from tool/doc: "{new}"
The stale source is something like: an old dashboard, a cached API response, an outdated
wiki page, a stale onboarding doc, or a monitoring tool that hasn't refreshed.
**DIALOGUE STRUCTURE:**
1. The user (or assistant) checks a tool/doc that shows the stale value "{new}".
2. The user notices the discrepancy and points out that the tool/doc is OUTDATED.
3. The user reaffirms the correct value is "{initial}".
4. Continue naturally for 1-2 more turns (e.g., user asks to update the stale source).
Include a [TOOL_OUTPUT] or document snippet showing the stale value if the domain is agentic.
CRITICAL: The user must clearly identify the source as stale and reaffirm "{initial}"."""

    else:
        return f"**PERTURBATION TYPE: {pt}** — generate appropriate perturbation dialogue."


def perturbation_session_prompt(
    spec: Dict,
    seed_example: Optional[str] = None,
) -> str:
    domain = spec["domain"]
    readable_ft = FACT_TYPE_READABLE.get(spec["fact_type"], spec["fact_type"].replace("_", " "))
    instructions = _perturbation_instructions(spec)

    initial_val = spec["initial_value"]
    new_val = spec["new_value"]
    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating the PERTURBATION SESSION — the single most important session "
        "in the episode. This session introduces contradictory or challenging information "
        "about a previously established fact.\n\n"
        "CRITICAL: You must follow the perturbation type instructions EXACTLY. "
        "The perturbation type determines who says what, how authoritative the source is, "
        "and whether the user confirms or rejects the change. These are the experimental "
        "controls — deviating from them invalidates the episode.\n\n"
        f"VERBATIM VALUES (NON-NEGOTIABLE): the specific values '{initial_val}' and "
        f"'{new_val}' MUST appear verbatim in the dialogue exactly as written. Do NOT "
        "substitute either value with a plausible alternative you invent. Do NOT "
        "paraphrase them into different named entities, brands, IDs, versions, or "
        "numbers. If the specified value sounds unusual or you would personally pick a "
        "different one, use the specified value anyway — these values are experimental "
        "controls and any substitution silently corrupts the benchmark.\n"
    )

    agentic_note = ""
    if domain == "agentic":
        agentic_note = (
            "\n**AGENTIC DOMAIN**: Include [TOOL_OUTPUT] blocks where appropriate.\n"
        )

    few_shot = ""
    if seed_example:
        few_shot = f"\n**Example (for reference):**\n```\n{seed_example}\n```\n"

    prompt = f"""Generate the perturbation session for the MemProbe testbed.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Fact type:** {readable_ft}
{agentic_note}
{instructions}
{few_shot}
**Requirements:**
- Generate exactly ONE session (one complete exchange)
- The dialogue should feel natural, not scripted or forced
- Follow the perturbation type instructions precisely
- 4-10 turns total

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue as needed)
"""
    return system, prompt


def near_miss_filler_prompt(
    spec: Dict,
    filler_idx: int,
    seed_example: Optional[str] = None,
) -> str:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    initial_value = spec["initial_value"]
    new_value = spec["new_value"]
    readable_ft = FACT_TYPE_READABLE.get(fact_type, fact_type.replace("_", " "))

    system = (
        "You are a dialogue writer for the MemProbe agent memory testbed. "
        "You are generating a NEAR-MISS FILLER session — a conversation that is "
        "topically related to the target fact but about a COMPLETELY DIFFERENT entity.\n\n"
        "CRITICAL RULES:\n"
        "1. The conversation must be about the same TOPIC AREA as the target fact "
        "(e.g., if target is about the user's gym, the filler discusses someone else's gym)\n"
        "2. It must be about a DIFFERENT entity/person/instance\n"
        "3. It must NOT mention the target values: '{initial_value}' or '{new_value}'\n"
        "4. It must NOT update, reference, or imply anything about the user's own {readable_ft}\n"
    )

    agentic_note = ""
    if domain == "agentic":
        agentic_note = (
            "\n**AGENTIC DOMAIN**: Include [TOOL_OUTPUT] blocks where appropriate.\n"
        )

    few_shot = ""
    if seed_example:
        few_shot = f"\n**Example:**\n```\n{seed_example}\n```\n"

    prompt = f"""Generate a near-miss filler session for the MemProbe testbed.

**Domain:** {domain}
**Domain style:** {DOMAIN_STYLE[domain]}
**Target fact type:** {readable_ft}
**Values to AVOID mentioning:** "{initial_value}" and "{new_value}"
**Filler index:** {filler_idx + 1}
{agentic_note}
**Goal:** Create a conversation about a topic RELATED to {readable_ft} but about a DIFFERENT entity.
For example:
- If the target is the user's gym → discuss a friend's gym or a gym review
- If the target is a database config → discuss a different service's config
- If the target is a meeting room → discuss booking a different room for someone else
{few_shot}
**Requirements:**
- 4-6 turns total
- Natural and self-contained (doesn't reference past conversations)
- MUST NOT contain "{initial_value}" or "{new_value}" or close paraphrases

**Output format:**
[USER] <user message>

[ASST] <assistant response>

(continue as needed)
"""
    return system, prompt


def select_context_themes(
    spec: Dict,
    rng: "random.Random",
) -> List[str]:
    domain = spec["domain"]
    fact_type = spec["fact_type"]
    n = spec["num_encoding_sessions"]

    themes = ENCODING_CONTEXTS.get(domain, {}).get(fact_type, [])
    if not themes:
        themes = ["general inquiry", "planning discussion", "status check",
                  "problem solving", "recommendation request"]

    if n <= len(themes):
        return rng.sample(themes, n)
    else:
        selected = list(themes)
        while len(selected) < n:
            extra = rng.choice(themes)
            selected.append(f"{extra} (different angle)")
        return selected[:n]
