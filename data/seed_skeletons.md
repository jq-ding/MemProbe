# Seed Skeletons for MemProbe Pilot

This file contains 15 seed skeleton groups covering all 8 condition types across all 3 domains. Each skeleton provides:

- **Metadata**: latent spec fields for reference
- **Encoding sessions**: 2-3 fully written sessions showing natural fact embedding
- **Near-miss filler**: 1 example filler session that mentions a topic close to the target fact (but about a different entity)
- **Perturbation session**: the experimental manipulation (fully written — this is the core)
- **Probe questions**: 3-4 probes with gold answers
- **Episode structure**: showing where `[FROM POOL]` generic fillers are inserted

**Conventions**:
- `[USER]` = user turn, `[ASST]` = assistant turn
- `[TOOL_OUTPUT]` = simulated tool/system output (Domain C only)
- `[FROM POOL: generic × N]` = N generic filler sessions drawn from existing benchmark material
- `[FROM POOL: near-miss × N]` = N near-miss fillers to be generated (topic-adjacent, different entity)
- Sessions are numbered within their phase for clarity
- Target fact is **bolded** on first natural appearance for annotator reference only (not in final output)

---

## Seed 1: Interference/Standard × Personal — `residential_city`

### Metadata

```yaml
paradigm: interference
condition: standard
domain: personal
fact_type: residential_city
initial_value: "Brooklyn, New York"
new_value: "Santa Monica, Los Angeles"
expected_behavior: should_update
perturbation_type: direct_update
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×28] → [FROM POOL: near-miss ×5] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~43 sessions
```

### Encoding Session 1

```
[USER] Hey, I need a good brunch recommendation. Something walkable
       from my place — I'm in **Brooklyn**.

[ASST] Sure! If you're in Brooklyn, I'd recommend Egg on North 3rd Street
       in Williamsburg, or Five Leaves on Bedford Ave. Both are walkable
       depending on your exact neighborhood. What part of Brooklyn are you in?

[USER] I'm near Prospect Park area. Five Leaves might be a bit far.

[ASST] Got it! For the Prospect Park area, try Winner on Vanderbilt Ave —
       great pastries and solid egg dishes. Tom's Restaurant on Washington Ave
       is also a classic if you don't mind a short wait on weekends.
```

### Encoding Session 2

```
[USER] Can you help me figure out the best subway route to get to
       Midtown from my place? I always end up transferring too many times.

[ASST] Where exactly in Brooklyn are you starting from?

[USER] Near Prospect Park — the B/Q stop at 7th Ave.

[ASST] Great, that's actually a pretty direct route. Take the B or Q from
       7th Ave — both go express through Manhattan. The B will take you to
       47-50th St/Rockefeller Center, and the Q goes to 57th St/7th Ave.
       No transfers needed. It's about 30 minutes.
```

### Encoding Session 3

```
[USER] It's supposed to rain all week in Brooklyn. I need to find
       an indoor activity for the weekend. Any ideas?

[ASST] There's a lot to do indoors in Brooklyn! The Brooklyn Museum is
       always a good option — they often have interesting exhibitions.
       Brooklyn Boulders is fun if you want something more active. Or if
       you're in the mood for something chill, Nitehawk Cinema in Prospect
       Park does dine-in movies.
```

### Near-Miss Filler Example

> Topic: a friend's apartment situation — mentions a neighborhood but about someone else

```
[USER] My friend Mia just signed a lease in the East Village. She's asking
       me whether she should get a Citi Bike membership. What do you think?

[ASST] For the East Village, Citi Bike is a great call. The area is very
       bike-friendly with stations on almost every block, and it's flat
       enough to make short commutes easy. If she's commuting to Midtown
       or the West Village, it'll be faster than the subway for those trips.

[USER] Good point. I'll tell her to go for it.
```

### Perturbation Session (direct_update)

```
[USER] Big news — I just moved! I'm now in Santa Monica, Los Angeles.
       Still getting settled but I love being near the beach.

[ASST] Congratulations on the move! Santa Monica is beautiful — the beach
       access and weather are hard to beat. Are you near the Promenade area
       or more towards Ocean Park?

[USER] Closer to Ocean Park, a few blocks from the pier.

[ASST] Great neighborhood! Let me know if you need help finding local spots —
       grocery stores, coffee shops, anything. Moving to a new city is
       a lot but Santa Monica is very walkable once you know the layout.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "Where does the user currently live?"
   Gold: "Santa Monica, Los Angeles"

2. [Previous-value probe]
   Q: "Where did the user live before their most recent move?"
   Gold: "Brooklyn, New York"

3. [Temporal probe]
   Q: "Has the user's city of residence changed during our conversations?"
   Gold: "Yes — moved from Brooklyn, New York to Santa Monica, Los Angeles"

4. [Source probe]
   Q: "How did we learn about the user's current location?"
   Gold: "The user directly told us they moved to Santa Monica"
```

---

## Seed 2: Interference/Standard × Work — `project_owner`

### Metadata

```yaml
paradigm: interference
condition: standard
domain: work
fact_type: project_owner
initial_value: "Sarah Kim owns the authentication module"
new_value: "ownership transferred to David Chen"
expected_behavior: should_update
perturbation_type: direct_update
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×30] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×3] → Probes ×4
Total: ~45 sessions
```

### Encoding Session 1

```
[USER] I need to file a bug about the login flow — the OAuth callback
       is returning a 500 intermittently. Who should I tag?

[ASST] What module does the OAuth callback fall under? Is that part of
       the authentication system?

[USER] Yeah, it's the auth module. **Sarah Kim** owns that. I'll tag her
       but wanted to document the issue first.

[ASST] Good idea. For the bug report, include the endpoint that's failing,
       the frequency (intermittent suggests it might be a race condition
       or timeout), and any error logs you can pull. Sarah's team will
       likely want the request IDs too.
```

### Encoding Session 2

```
[USER] I'm reviewing the Q3 roadmap. Can you remind me of the module
       owners so I can assign the right epics?

[ASST] I know Sarah Kim owns the authentication module. Could you remind me
       of the other module owners? I want to make sure I have the latest info.

[USER] Right, Sarah has auth. Marcus has payments, and Amy's team
       handles the analytics dashboard.

[ASST] Got it. So for the Q3 roadmap:
       - Auth epics → Sarah Kim
       - Payment epics → Marcus
       - Analytics epics → Amy's team
       Want me to draft the assignment list?
```

### Near-Miss Filler Example

> Topic: code review on a different module — mentions a person but not re: auth ownership

```
[USER] Marcus left some comments on my payments PR. He wants me to add
       retry logic for the Stripe webhook handler. Thoughts on the
       best pattern here?

[ASST] For webhook handlers, I'd recommend an exponential backoff pattern
       with a dead-letter queue. If the retry fails after 3-5 attempts,
       push the event to a DLQ so it can be manually inspected...
```

### Perturbation Session (direct_update)

```
[USER] Heads up — there was a reorg this week. Sarah Kim moved to the
       platform team, so David Chen is taking over the authentication
       module effective immediately.

[ASST] Thanks for the update. So David Chen is now the owner of the auth
       module. Should I update any of the tracking docs I have? And does
       David want the existing auth-related tickets reassigned to him?

[USER] Yeah, all auth tickets should go to David now. Sarah already
       did a handoff meeting with him last Friday.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "Who currently owns the authentication module?"
   Gold: "David Chen"

2. [Previous-value probe]
   Q: "Who owned the authentication module before the recent change?"
   Gold: "Sarah Kim"

3. [Source probe]
   Q: "How was the ownership change communicated?"
   Gold: "The user directly informed us about the reorg"

4. [Temporal probe]
   Q: "Has the auth module ownership changed?"
   Gold: "Yes — transferred from Sarah Kim to David Chen"
```

---

## Seed 3: Interference/Standard × Agentic — `active_branch`

### Metadata

```yaml
paradigm: interference
condition: standard
domain: agentic
fact_type: active_branch
initial_value: "working on feature/auth-v2"
new_value: "main"
expected_behavior: should_update
perturbation_type: direct_update
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×32] → [FROM POOL: near-miss ×3] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~45 sessions
```

### Encoding Session 1

```
[USER] I'm working on the new auth flow. Can you check if there are any
       failing tests on my branch?

[ASST] Which branch are you on?

[USER] **feature/auth-v2**

[ASST] Let me check the CI status for feature/auth-v2.

[TOOL_OUTPUT] Branch: feature/auth-v2
              Last commit: a3f29c1 "add PKCE support to OAuth flow"
              CI Status: 47/48 tests passing
              Failing: test_token_refresh_expired_session (timeout)

[ASST] You have one failing test on feature/auth-v2:
       `test_token_refresh_expired_session` — it's timing out. The other
       47 tests pass. This looks like it might be a test infrastructure
       issue rather than a code bug. Want me to look at the test?
```

### Encoding Session 2

```
[USER] Can you show me the diff between my branch and main for the
       auth controller file?

[ASST] Pulling the diff for feature/auth-v2 vs main.

[TOOL_OUTPUT] Diff: feature/auth-v2...main — src/controllers/auth.ts
              +42 lines, -8 lines
              Key changes:
              - Added PKCE challenge/verifier generation
              - Modified token endpoint to accept code_verifier
              - Added new error handling for invalid verifier

[ASST] On feature/auth-v2, you've added 42 lines and removed 8 in the
       auth controller. The main changes are PKCE support — challenge
       generation, verifier validation, and associated error handling.
```

### Near-Miss Filler Example

> Topic: a different branch being discussed, but about someone else's work

```
[USER] The frontend team merged feature/ui-redesign yesterday. Did that
       cause any conflicts with open PRs?

[ASST] Let me check for merge conflicts.

[TOOL_OUTPUT] Merge conflict check:
              feature/ui-redesign merged to main at 14:32 UTC
              Open PRs with conflicts: 2
              - PR #342 (feature/dashboard-v3): conflict in styles.css
              - PR #356 (bugfix/nav-overflow): conflict in layout.tsx

[ASST] Two open PRs have conflicts after the ui-redesign merge...
```

### Perturbation Session (direct_update)

```
[USER] I just merged feature/auth-v2 into main and deleted the feature
       branch. I'm back on main now.

[ASST] Nice, congrats on merging the auth v2 work! You're now on main.
       Want me to pull the latest main status or is there something else
       you'd like to work on next?

[USER] Yeah, let's see what's on main now.

[TOOL_OUTPUT] Branch: main
              Last commit: 8d4e1f2 "Merge feature/auth-v2 (#389)"
              CI Status: all 52 tests passing
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What branch is the user currently working on?"
   Gold: "main"

2. [Previous-value probe]
   Q: "What branch was the user on before?"
   Gold: "feature/auth-v2"

3. [Temporal probe]
   Q: "Has the user's active branch changed?"
   Gold: "Yes — merged feature/auth-v2 into main and switched to main"

4. [Source probe]
   Q: "How do we know the user is on main?"
   Gold: "The user told us they merged and switched; confirmed by tool output"
```

---

## Seed 4: Interference/Noise × Personal — `current_gym`

### Metadata

```yaml
paradigm: interference
condition: noise
domain: personal
fact_type: current_gym
initial_value: "FitLife on 5th Ave"
new_value: "CrossFit Central on Main St"  # used as noise_value
expected_behavior: should_preserve
perturbation_type: near_miss_noise
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×30] → [FROM POOL: near-miss ×5] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~45 sessions
```

### Encoding Session 1

```
[USER] I need to cancel my gym session for tomorrow morning. Can you
       remind me what time I usually go?

[ASST] Which gym do you go to? I can check if they have an app or online
       cancellation policy.

[USER] **FitLife on 5th Ave**. I think I usually have a 7am slot on Tuesdays.

[ASST] For FitLife, most locations allow cancellation up to 2 hours before
       the class via their app. If your Tuesday 7am session is tomorrow,
       you'd need to cancel by 5am — so doing it now would be safe.
```

### Encoding Session 2

```
[USER] My shoulder's been sore after workouts. Any stretching routines
       I can do at the gym before my session?

[ASST] What kind of workouts do you usually do at FitLife? Free weights,
       machines, or classes?

[USER] Mostly free weights and some machine work. They have a good
       stretching area near the back.

[ASST] For pre-workout shoulder care, try these before your FitLife session:
       1. Arm circles — 30 seconds each direction
       2. Band pull-aparts — 2×15 reps
       3. Wall slides — 2×10
       These should take about 5 minutes in the stretching area.
```

### Near-Miss Filler Example

> Topic: a friend's gym — mentions a different gym name, about a different person

```
[USER] My coworker Jake just signed up for a new gym — some place called
       Iron Works on 8th. He wants me to try a guest pass. Is it worth it?

[ASST] Iron Works locations tend to be more powerlifting-focused — squat racks,
       platforms, chalk allowed. If you enjoy free weights, a guest pass
       is a low-commitment way to check it out. What's Jake hoping to get
       out of it?

[USER] He says they have better barbells. I might check it out just to
       compare, but I'm happy where I am for now.
```

### Perturbation Session (near_miss_noise)

> The perturbation introduces the noise value incidentally, through a different entity.
> This is NOT the user changing their gym — it's environmental noise that the system should NOT treat as an update.

```
[USER] I walked past CrossFit Central on Main St today and saw they're
       running some kind of open day this weekend. My friend is thinking
       of trying it. Have you heard anything about CrossFit Central?

[ASST] CrossFit Central is a popular CrossFit affiliate — they typically
       offer intro classes and open house events for newcomers. If your
       friend is interested in CrossFit, an open day is a great low-pressure
       way to try it. They usually include a sample WOD (workout of the day)
       and a tour.

[USER] Cool, I'll pass that along to her.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What gym does the user go to?"
   Gold: "FitLife on 5th Ave"

2. [Original-value probe]
   Q: "What gym did the user originally tell us they go to?"
   Gold: "FitLife on 5th Ave"

3. [Conflict-value probe]
   Q: "Were any other gyms mentioned in conversation? If so, which?"
   Gold: "Yes — CrossFit Central on Main St was mentioned, but only in
          the context of a friend's interest, not the user switching gyms"

4. [Change-detection probe]
   Q: "Has the user changed gyms?"
   Gold: "No — the user still goes to FitLife on 5th Ave"
```

---

## Seed 5: Interference/Noise × Agentic — `config_value`

### Metadata

```yaml
paradigm: interference
condition: noise
domain: agentic
fact_type: config_value
initial_value: "MAX_RETRIES set to 3"
new_value: "increased to 5 after timeout issues"  # used as noise_value
expected_behavior: should_preserve
perturbation_type: near_miss_noise
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×31] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×3] → Probes ×4
Total: ~46 sessions
```

### Encoding Session 1

```
[USER] Can you check the current retry config for the ingestion service?

[ASST] Let me look at the config file.

[TOOL_OUTPUT] File: config/ingestion.yaml
              service: ingestion-pipeline
              retry:
                max_retries: 3
                backoff_ms: 1000
                backoff_multiplier: 2.0

[ASST] The ingestion service has **MAX_RETRIES set to 3**, with exponential
       backoff starting at 1000ms and a 2x multiplier. So retries happen
       at ~1s, ~2s, and ~4s.
```

### Encoding Session 2

```
[USER] We had a few transient failures in the ingestion pipeline last night.
       Should I increase the retry count?

[ASST] Looking at the current config, you have MAX_RETRIES at 3 with
       exponential backoff. Before changing it, what were the failure modes?
       If the failures are transient network blips, 3 retries with your
       current backoff should cover most cases. If they're upstream service
       cold-starts taking 10+ seconds, you might need to increase the
       initial backoff rather than the retry count.

[USER] Good point. Let me check the logs first. For now keep it at 3.
```

### Near-Miss Filler Example

> Topic: retry config for a *different* service

```
[USER] The notification service keeps dropping messages. Can you check
       its retry settings?

[ASST] Let me pull the notification service config.

[TOOL_OUTPUT] File: config/notifications.yaml
              service: notification-dispatcher
              retry:
                max_retries: 5
                backoff_ms: 500
                backoff_multiplier: 1.5

[ASST] The notification service has max_retries at 5 with 500ms initial
       backoff and 1.5x multiplier. That's more aggressive than the
       ingestion service. Are the dropped messages happening after all
       5 retries exhaust?
```

### Perturbation Session (near_miss_noise)

> Stale documentation references the noise value. This is NOT an actual config change.

```
[USER] I found an old runbook in the wiki that says MAX_RETRIES should be
       set to 5 for the ingestion pipeline. But I think that's outdated.
       Can you check what the current config actually says?

[ASST] Let me verify the live config.

[TOOL_OUTPUT] File: config/ingestion.yaml (current, last modified 2024-11-02)
              service: ingestion-pipeline
              retry:
                max_retries: 3
                backoff_ms: 1000
                backoff_multiplier: 2.0

[ASST] The current live config still shows MAX_RETRIES at 3 for the
       ingestion pipeline. That wiki runbook is likely outdated — it may
       reference an older default or a different environment. The config
       file was last modified on November 2nd.

[USER] Yeah, figured. I'll update the wiki to match the actual config.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What is the MAX_RETRIES setting for the ingestion service?"
   Gold: "3"

2. [Original-value probe]
   Q: "What was the MAX_RETRIES value when we first checked the config?"
   Gold: "3"

3. [Conflict-value probe]
   Q: "Was any different value for MAX_RETRIES mentioned? If so, what and where?"
   Gold: "Yes — an outdated wiki runbook listed MAX_RETRIES as 5, but the
          live config confirmed the actual value is 3"

4. [Change-detection probe]
   Q: "Has the MAX_RETRIES config for the ingestion service changed?"
   Gold: "No — it has remained at 3"
```

---

## Seed 6: Misinformation Triplet × Personal — `doctor_appointment_time`

### Metadata

```yaml
paradigm: misinformation
domain: personal
fact_type: doctor_appointment_time
initial_value: "Tuesday at 2pm with Dr. Park"
new_value: "Thursday at 10am with Dr. Park"  # perturbation value

# Three conditions share encoding + fillers, differ only in perturbation:
# Condition A (user_explicit): should_update, direct_update
# Condition B (assistant_noise): should_preserve, noise_injection
# Condition C (third_party_noise): should_preserve, noise_injection
```

### Episode Structure (shared across triplet)

```
Encoding ×3 → [FROM POOL: generic ×35] → [FROM POOL: near-miss ×3] → Perturbation ×1 [VARIES] → [FROM POOL: generic ×2] → Probes ×4
Total: ~48 sessions
```

### Shared Encoding Session 1

```
[USER] I need to remember my doctor's appointment. It's **Tuesday at 2pm
       with Dr. Park**. Can you make a note?

[ASST] Got it — your appointment is Tuesday at 2pm with Dr. Park.
       Would you like me to remind you the day before?

[USER] Yes please, Monday evening would be great.
```

### Shared Encoding Session 2

```
[USER] I'm trying to plan my week. Tuesday is going to be busy — I have
       the doctor at 2, then I need to pick up groceries after.

[ASST] Right, your appointment with Dr. Park is at 2pm on Tuesday. Depending
       on how long the visit takes, you might want to identify a grocery
       store near Dr. Park's office to save time on the commute back.

[USER] Smart idea. I think there's a Trader Joe's near the clinic.
```

### Shared Encoding Session 3

```
[USER] Should I eat before my doctor's appointment or is it a fasting one?

[ASST] That depends on the type of appointment. If Dr. Park ordered blood
       work, you may need to fast for 8-12 hours beforehand — which means
       no food after 2am Monday night for your 2pm Tuesday appointment.
       Do you know if blood work is involved?

[USER] I don't think so — it's just a regular checkup. I'll eat normally.
```

### Near-Miss Filler Example

> Topic: scheduling — mentions a time/appointment, but for a completely different event

```
[USER] I also need to schedule a dentist appointment sometime this month.
       What days do you think work best?

[ASST] Since your Tuesday is already committed with Dr. Park, you might
       want to look at Wednesday or Thursday mornings for the dentist.
       Most dental offices have better availability mid-week. Do you have
       a dentist in mind?

[USER] I'll check with my usual place and see what they have.
```

### Perturbation — Condition A: `user_explicit` (should_update)

```
[USER] Hey, I need to reschedule my appointment with Dr. Park. It's now
       Thursday at 10am instead of Tuesday at 2pm.

[ASST] Updated — your appointment with Dr. Park is now Thursday at 10am.
       Want me to adjust the reminder to Wednesday evening?

[USER] Yes, that would be great.
```

### Perturbation — Condition B: `assistant_noise` (should_preserve)

> The assistant incorrectly states the wrong time in a proactive reminder.

```
[ASST] Just a reminder — you have your appointment with Dr. Park coming up
       on Thursday at 10am. Would you like me to suggest what to bring?

[USER] Wait, I thought it was Tuesday at 2pm? Let me double-check...
       No, it's definitely Tuesday at 2pm. I have the confirmation text.

[ASST] You're right, I apologize for the confusion. Your appointment is
       Tuesday at 2pm with Dr. Park. Sorry about that.
```

### Perturbation — Condition C: `third_party_noise` (should_preserve)

> A family member (relayed by the user) mentions the wrong time.

```
[USER] My mom just texted me saying she thinks my doctor appointment is
       Thursday at 10am. But I'm pretty sure I told her the wrong time.
       Can you confirm what I originally told you?

[ASST] Based on what you told me, your appointment with Dr. Park is
       Tuesday at 2pm. It sounds like your mom may have mixed up the
       details.

[USER] Yeah, that's what I thought. Tuesday at 2pm is correct.
```

### Probe Questions

**Condition A (user_explicit) — gold = new_value:**
```
1. Q: "When is the user's appointment with Dr. Park?"
   Gold: "Thursday at 10am"

2. Q: "What was the original appointment time?"
   Gold: "Tuesday at 2pm"

3. Q: "Who changed the appointment?"
   Gold: "The user rescheduled it"

4. Q: "Has the appointment time changed?"
   Gold: "Yes — from Tuesday at 2pm to Thursday at 10am"
```

**Conditions B & C (assistant_noise / third_party_noise) — gold = initial_value:**
```
1. [Current-state probe]
   Q: "When is the user's appointment with Dr. Park?"
   Gold: "Tuesday at 2pm"

2. [Original-value probe]
   Q: "What appointment time did the user originally tell us?"
   Gold: "Tuesday at 2pm"

3. [Conflict-value probe]
   Q: "Was any different appointment time mentioned? If so, what and by whom?"
   Gold: "Yes — Thursday at 10am was mentioned by [the assistant in error /
          the user's mom], but the user confirmed the correct time is
          Tuesday at 2pm"

4. [Change-detection probe]
   Q: "Has the appointment time changed?"
   Gold: "No — it remains Tuesday at 2pm"
```

---

## Seed 7: Misinformation Triplet × Work — `assigned_reviewer`

### Metadata

```yaml
paradigm: misinformation
domain: work
fact_type: assigned_reviewer
initial_value: "PR reviewer is Alex from the backend team"
new_value: "changed to Priya because Alex is on leave"  # perturbation value

# Condition A (user_explicit): should_update
# Condition B (assistant_noise): should_preserve
# Condition C (third_party_noise): should_preserve
```

### Episode Structure

```
Encoding ×4 → [FROM POOL: generic ×30] → [FROM POOL: near-miss ×4] → Perturbation ×1 [VARIES] → [FROM POOL: generic ×2] → Probes ×4
Total: ~45 sessions
```

### Shared Encoding Session 1

```
[USER] I just opened PR #412 for the caching refactor. **Alex from the
       backend team** is assigned as reviewer. Can you keep track of that?

[ASST] Got it — PR #412 (caching refactor), reviewer is Alex from the
       backend team. Want me to follow up if there's no review in a
       certain timeframe?

[USER] Yeah, ping me if it's been more than 2 days without comments.
```

### Shared Encoding Session 2

```
[USER] Alex left a few initial comments on my PR — mostly nits. Should
       I address them all before the next round of review?

[ASST] Generally yes, it's good practice to address all comments before
       requesting re-review. Nits are quick to fix and it shows Alex you
       took the feedback seriously. It also makes the second review pass
       faster since he won't have to re-flag the same items.
```

### Near-Miss Filler Example

> Topic: a different PR with a different reviewer

```
[USER] Jordan finished reviewing PR #408 — the UI component library update.
       She approved it. Should I merge now or wait for CI?

[ASST] Wait for CI to pass first. Even with Jordan's approval, if CI fails
       after merge you'll be rolling back. Once CI is green, merge away.
```

### Perturbation — Condition A: `user_explicit` (should_update)

```
[USER] Hey, Alex is going on leave starting tomorrow. I need to reassign
       PR #412 to Priya. She's also on the backend team and has context
       on the caching layer.

[ASST] Makes sense. So Priya is now the reviewer for PR #412 instead of
       Alex. Should I update my tracking?

[USER] Yes, Priya's the reviewer from now on.
```

### Perturbation — Condition B: `assistant_noise` (should_preserve)

> The assistant proactively but incorrectly states the reviewer has changed.

```
[ASST] I noticed Alex hasn't left comments in 3 days on PR #412. I believe
       the reviewer may have been changed to Priya — would you like me
       to check?

[USER] No, Alex is still the reviewer. He mentioned he'd get to it by
       end of week. Don't reassign anything.

[ASST] Understood, Alex is still the reviewer for PR #412. I'll continue
       tracking and follow up if needed.
```

### Perturbation — Condition C: `third_party_noise` (should_preserve)

> A colleague (relayed by user) assumes the wrong reviewer.

```
[USER] Marcus just messaged me asking if Priya is reviewing my caching PR.
       I think he's confused — Alex is the reviewer, right?

[ASST] Yes, based on what you told me, Alex from the backend team is the
       assigned reviewer for PR #412. Marcus may be thinking of a different
       PR or mixing up assignments.

[USER] That's what I thought. I'll let Marcus know.
```

### Probe Questions

**Condition A (user_explicit) — gold = Priya:**
```
1. Q: "Who is the reviewer for PR #412?"
   Gold: "Priya"

2. Q: "Who was the original reviewer?"
   Gold: "Alex from the backend team"

3. Q: "Why was the reviewer changed?"
   Gold: "Alex is going on leave"

4. Q: "Has the reviewer assignment changed?"
   Gold: "Yes — from Alex to Priya"
```

**Conditions B & C (assistant_noise / third_party_noise) — gold = Alex:**
```
1. [Current-state probe]
   Q: "Who is the current reviewer for PR #412?"
   Gold: "Alex from the backend team"

2. [Original-value probe]
   Q: "Who did the user originally assign as reviewer for PR #412?"
   Gold: "Alex from the backend team"

3. [Conflict-value probe]
   Q: "Was any other person mentioned as a possible reviewer? If so, who and by whom?"
   Gold: "Yes — Priya was mentioned by [the assistant speculatively /
          Marcus in a Slack message], but the user confirmed Alex is
          still the reviewer"

4. [Change-detection probe]
   Q: "Has the reviewer for PR #412 changed?"
   Gold: "No — Alex remains the reviewer"
```

---

## Seed 8: Misinformation Triplet × Agentic — `reported_port_number`

### Metadata

```yaml
paradigm: misinformation
domain: agentic
fact_type: reported_port_number
initial_value: "service running on port 5432"
new_value: "migrated to port 5433"  # perturbation value

# Condition A (user_explicit): should_update
# Condition B (assistant_noise): should_preserve
# Condition C (third_party_noise): should_preserve
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×33] → [FROM POOL: near-miss ×4] → Perturbation ×1 [VARIES] → [FROM POOL: generic ×3] → Probes ×4
Total: ~48 sessions
```

### Shared Encoding Session 1

```
[USER] Can you check what port the primary database is running on?

[ASST] Let me check.

[TOOL_OUTPUT] $ ss -tlnp | grep postgres
              LISTEN  0  128  0.0.0.0:5432  0.0.0.0:*  users:(("postgres",pid=1234))

[ASST] The primary PostgreSQL database is listening on **port 5432** —
       that's the standard default port.
```

### Shared Encoding Session 2

```
[USER] I need to update the connection string in our staging config.
       What's the DB port again?

[ASST] The database is running on port 5432. Your connection string should
       look like: `postgresql://user:pass@db-host:5432/dbname`

[USER] Perfect, thanks.
```

### Near-Miss Filler Example

> Topic: port for a different service

```
[USER] What port is the Redis cache running on?

[ASST] Let me check.

[TOOL_OUTPUT] $ ss -tlnp | grep redis
              LISTEN  0  128  0.0.0.0:6379  0.0.0.0:*  users:(("redis-server",pid=5678))

[ASST] Redis is on port 6379, which is the standard Redis port.
```

### Perturbation — Condition A: `user_explicit` (should_update)

```
[USER] We just migrated the primary database to port 5433 because of a
       conflict with the test instance. The new port is 5433.

[ASST] Got it — the primary database is now on port 5433. Should I update
       the connection string references I have?

[USER] Yes. Everything should point to 5433 now.

[TOOL_OUTPUT] $ ss -tlnp | grep postgres
              LISTEN  0  128  0.0.0.0:5433  0.0.0.0:*  users:(("postgres",pid=2345))
```

### Perturbation — Condition B: `assistant_noise` (should_preserve)

> The assistant misremembers / confuses the port.

```
[ASST] I want to confirm — for the database connection you're configuring,
       the port is 5433, correct?

[USER] No, it's 5432. Where did you get 5433?

[ASST] I apologize, you're right. The primary database port is 5432.
       I must have confused it with another service.

[USER] Yeah, 5432. That hasn't changed.
```

### Perturbation — Condition C: `third_party_noise` (should_preserve)

> An outdated operations document mentions the wrong port.

```
[USER] I was looking at the old ops runbook and it says the database
       port is 5433. But I think that's from before the last migration.
       What do our records show?

[ASST] Based on our previous checks, the primary database is running on
       port 5432. The runbook entry for 5433 is likely outdated — it may
       refer to a previous configuration or a different environment.

[TOOL_OUTPUT] $ ss -tlnp | grep postgres
              LISTEN  0  128  0.0.0.0:5432  0.0.0.0:*  users:(("postgres",pid=1234))

[ASST] Confirmed — the live system shows port 5432.

[USER] Good, I'll update the runbook.
```

### Probe Questions

**Condition A (user_explicit) — gold = 5433:**
```
1. Q: "What port is the primary database running on?"
   Gold: "5433"

2. Q: "What was the previous port?"
   Gold: "5432"

3. Q: "Why was the port changed?"
   Gold: "Conflict with the test instance"

4. Q: "Has the database port changed?"
   Gold: "Yes — from 5432 to 5433"
```

**Conditions B & C — gold = 5432:**
```
1. [Current-state probe]
   Q: "What port is the primary database running on?"
   Gold: "5432"

2. [Original-value probe]
   Q: "What port did we originally confirm for the primary database?"
   Gold: "5432"

3. [Conflict-value probe]
   Q: "Was any different port number mentioned? If so, what and where?"
   Gold: "Yes — port 5433 was mentioned by [the assistant in error /
          an outdated ops runbook], but the live system confirmed 5432"

4. [Change-detection probe]
   Q: "Has the primary database port changed?"
   Gold: "No — it remains 5432"
```

---

## Seed 9: Consolidation/Update Pair × Personal — `diet_preference`

### Metadata

```yaml
paradigm: consolidation
domain: personal
fact_type: diet_preference
initial_value: "strict vegetarian for 7 years"
new_value: "started eating fish occasionally (pescatarian)"
expected_behavior: should_update
perturbation_type: direct_update

# HIGH condition: 5 encoding sessions (target fact mentioned in diverse contexts)
# LOW condition: 1 encoding session (same perturbation + probes)
```

### Episode Structure

**HIGH condition:**
```
Encoding ×5 → [FROM POOL: generic ×32] → [FROM POOL: near-miss ×3] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~47 sessions
```

**LOW condition:**
```
Encoding ×1 → [FROM POOL: generic ×36] → [FROM POOL: near-miss ×3] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~47 sessions (fillers increased to match total length)
```

### HIGH Encoding Session 1 (ordering food)

```
[USER] We're ordering team lunch today. I need a vegetarian option.
       I've been **vegetarian for about 7 years** so no meat or fish.

[ASST] Here are some good vegetarian options depending on what cuisine
       you're ordering:
       - Indian: paneer tikka masala or chana masala
       - Italian: eggplant parmigiana or mushroom risotto
       - Thai: vegetable pad thai (make sure they skip fish sauce)
       Need me to be more specific for a particular restaurant?

[USER] We're doing Indian — chana masala sounds perfect.
```

### HIGH Encoding Session 2 (travel planning)

```
[USER] I'm planning a trip to Japan. I'm worried about finding vegetarian
       food there — I've heard it's tough.

[ASST] It can be challenging since many Japanese dishes use dashi (fish stock)
       even in seemingly vegetarian items. Since you're strictly vegetarian,
       I'd recommend:
       - Search for "shojin ryori" restaurants (Buddhist temple cuisine, fully veg)
       - Download the "Is It Vegan Japan" app
       - Learn to say "niku, sakana nashi" (no meat, no fish)
       - Pack some protein bars as backup

[USER] Great tips. I'll look into shojin ryori — that sounds amazing.
```

### HIGH Encoding Session 3 (health checkup)

```
[USER] My doctor asked about my protein intake since I'm vegetarian.
       She wants me to track it for a week. What are good plant-based
       protein sources I might be missing?

[ASST] For a long-term vegetarian like yourself, here are key sources
       to track: lentils (18g/cup), chickpeas (15g/cup), tofu (20g/block),
       tempeh (31g/cup), quinoa (8g/cup), and Greek yogurt if you eat
       dairy (17g/cup). Are you including dairy and eggs, or are you
       closer to vegan?

[USER] I eat dairy and eggs, just no meat or fish.
```

### HIGH Encoding Session 4 (social event)

```
[USER] My friend is hosting a BBQ this weekend and asked about dietary
       restrictions. I told her I'm vegetarian but she forgets every time.
       Can you draft a quick text for me?

[ASST] How about: "Hey! Looking forward to Saturday. Just a reminder —
       I'm vegetarian (no meat or fish, but dairy and eggs are fine).
       Happy to bring a veggie burger or some grilled halloumi to throw
       on the grill! Let me know if I can bring anything else."

[USER] Perfect, sending that now.
```

### HIGH Encoding Session 5 (restaurant suggestion)

```
[USER] Date night tonight — any restaurant suggestions? Needs to have
       good vegetarian options. My partner eats everything but I need
       more than just a side salad.

[ASST] Since you need substantial vegetarian options, here are some ideas:
       - An Indian restaurant (always great for vegetarians)
       - A modern Mediterranean place — they often have dedicated veg mains
       - A farm-to-table spot that rotates seasonal vegetable dishes
       Avoid steakhouses or BBQ joints where the veg options are afterthoughts.
```

### LOW Encoding Session (only 1 — same as HIGH Session 1)

```
[USER] We're ordering team lunch today. I need a vegetarian option.
       I've been vegetarian for about 7 years so no meat or fish.

[ASST] Here are some good vegetarian options depending on what cuisine...
       [same as HIGH Session 1]
```

### Shared Perturbation Session (direct_update)

```
[USER] So I've actually started eating fish occasionally. My doctor
       recommended it for omega-3s and I've been slowly introducing it
       over the past month. I guess I'm more pescatarian now.

[ASST] That's a notable change after 7 years of being vegetarian! Pescatarian
       is a great middle ground for the omega-3 benefits. Are you finding
       it easy to adjust? Some long-term vegetarians find the transition
       takes a little getting used to.

[USER] It's been fine, actually. I started with sushi and now I have
       salmon about once a week. Still no meat though.
```

### Probe Questions (shared)

```
1. [Current-state probe]
   Q: "What is the user's current diet?"
   Gold: "Pescatarian — mostly vegetarian but now eats fish occasionally"

2. [Previous-value probe]
   Q: "What was the user's previous diet?"
   Gold: "Strict vegetarian for 7 years (no meat or fish)"

3. [Source probe]
   Q: "Why did the user change their diet?"
   Gold: "Their doctor recommended fish for omega-3s"

4. [Change-detection probe]
   Q: "Has the user's dietary preference changed?"
   Gold: "Yes — transitioned from vegetarian to pescatarian on doctor's advice"
```

**Key diagnostic**: The HIGH condition has the target fact mentioned 5 times across diverse contexts (food ordering, travel, health, social, restaurant). The LOW condition mentions it only once. Both receive the same direct update perturbation. If the system is consolidation-sensitive, `Update_rate(LOW) > Update_rate(HIGH)`.

---

## Seed 10: Consolidation/Challenge Pair × Personal — `sleep_schedule_preference`

### Metadata

```yaml
paradigm: consolidation
condition: high_challenge / low_challenge
domain: personal
fact_type: sleep_schedule_preference
initial_value: "night owl, usually sleeps around 1am"
new_value: "shifted to sleeping by 10:30pm for a new job"  # challenge_value
expected_behavior: should_preserve
perturbation_type: weak_challenge
```

### Episode Structure

**HIGH condition (5 encoding → weak challenge):**
```
Encoding ×5 → [FROM POOL: generic ×30] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~46 sessions
```

**LOW condition (1 encoding → same weak challenge):**
```
Encoding ×1 → [FROM POOL: generic ×34] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~46 sessions
```

### HIGH Encoding Session 1

```
[USER] I can never fall asleep before midnight. I'm such a **night owl** —
       usually don't get to bed until around 1am.

[ASST] Night owls are pretty common. As long as you're getting enough total
       sleep, a late schedule isn't necessarily unhealthy. What time do you
       usually wake up?

[USER] Around 8:30-9am, so I get about 7.5-8 hours. It works for me since
       I work remote and don't have early meetings.
```

### HIGH Encoding Session 2

```
[USER] My most productive hours are between 10pm and midnight. That's when
       I do my best thinking. Is that unusual?

[ASST] Not at all — research on chronotypes shows that evening types often
       have peak cognitive performance later in the day. Since you're
       naturally a night owl going to bed around 1am, your 10pm-midnight
       productivity window aligns perfectly with your circadian rhythm.
```

### HIGH Encoding Session 3

```
[USER] My partner wants us to go to a 7am yoga class tomorrow. I'm
       dreading it — I'm barely functional before 9.

[ASST] That's a tough ask for someone who usually sleeps until 8:30-9am!
       If you go, you might want to set multiple alarms and prepare your
       yoga clothes the night before. Or you could suggest a later class —
       many studios offer 9am or 10am sessions that would be more
       compatible with your schedule.
```

### HIGH Encoding Session 4

```
[USER] I love that my neighborhood is so alive at night. There's a great
       taco truck that opens at 11pm right down the block. Perfect for
       my late-night snack routine.

[ASST] That's one of the perks of being a night owl! A neighborhood with
       late-night food options makes a big difference when you're up
       until 1am. What do you usually get from the taco truck?
```

### HIGH Encoding Session 5

```
[USER] People keep telling me I should become a morning person. I've tried
       and it just doesn't work for me.

[ASST] Chronotype has a strong genetic component — it's not just about
       discipline. If you've consistently been a night owl and your current
       schedule (bed at 1am, up at 8:30-9am) gives you enough sleep and
       works with your obligations, there's no medical reason to force
       a change. "Morning person" culture gets a lot of press but it
       isn't inherently healthier.
```

### Shared Perturbation Session (weak_challenge)

> A non-authoritative source (article/blog) indirectly suggests a different schedule.
> This is NOT the user changing their schedule — it's weak environmental evidence.

```
[USER] I read an article that says people who sleep by 10:30pm have better
       health outcomes. It mentioned something about cortisol cycles.
       Should I be worried about my schedule?

[ASST] Those studies typically compare large populations and don't account
       for individual chronotypes. While cortisol rhythms do follow a
       general pattern, night owls who get adequate sleep and maintain
       consistency (like your 1am-8:30am schedule) don't necessarily
       have worse outcomes than early sleepers. The key factors are total
       sleep duration and regularity, not absolute clock time.

[USER] Yeah, I figured. I feel fine with my current schedule. Just wanted
       to make sure I'm not doing damage.

[ASST] Based on what you've described — consistent 7.5-8 hours, feeling
       rested, good productivity — your schedule sounds healthy.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What is the user's sleep schedule?"
   Gold: "Night owl — usually sleeps around 1am, wakes around 8:30-9am"

2. [Original-value probe]
   Q: "What sleep schedule did the user originally describe?"
   Gold: "Night owl, usually sleeps around 1am, wakes around 8:30-9am"

3. [Conflict-value probe]
   Q: "Was any alternative sleep schedule suggested? If so, what and from where?"
   Gold: "Yes — an article suggested sleeping by 10:30pm for health benefits,
          but the user evaluated it and decided their current schedule is fine"

4. [Change-detection probe]
   Q: "Has the user's sleep schedule changed?"
   Gold: "No — still a night owl sleeping around 1am"
```

**Key diagnostic**: HIGH condition has the sleep schedule mentioned in 5 diverse contexts (self-description, productivity, social, lifestyle, cultural pressure). LOW mentions it once. Both see the same weak challenge (an article, not the user deciding to change). A consolidation-sensitive system should preserve the highly-consolidated fact more reliably.

---

## Seed 11: Consolidation/Challenge Pair × Work — `task_priority`

### Metadata

```yaml
paradigm: consolidation
condition: high_challenge / low_challenge
domain: work
fact_type: task_priority
initial_value: "top priority is the payment system refactor"
new_value: "shifted to mobile app redesign as P0"  # challenge_value
expected_behavior: should_preserve
perturbation_type: weak_challenge
```

### Episode Structure

**HIGH condition:**
```
Encoding ×5 → [FROM POOL: generic ×30] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×3] → Probes ×4
Total: ~47 sessions
```

**LOW condition:**
```
Encoding ×1 → [FROM POOL: generic ×34] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×3] → Probes ×4
Total: ~47 sessions
```

### HIGH Encoding Session 1 (sprint planning)

```
[USER] Sprint planning today. Our **top priority is the payment system
       refactor** — that's been designated P0 by the VP of Engineering.

[ASST] Got it — the payment system refactor is the P0 item for this sprint.
       How are you breaking it down? Do you have a rough scope or specific
       milestones within the sprint?

[USER] We're targeting the checkout flow migration this sprint, card
       management next sprint. Two phases.
```

### HIGH Encoding Session 2 (standup)

```
[USER] In standup I mentioned that I'll be spending 80% of my time on the
       payment refactor this week. The remaining 20% is on code reviews.

[ASST] That's a significant allocation. With 80% on the payment refactor,
       you should be able to make solid progress on the checkout flow
       migration. For the code reviews, are there specific PRs you need
       to prioritize, or first-come-first-served?
```

### HIGH Encoding Session 3 (stakeholder update)

```
[USER] I need to write a status update email for the VP. Can you help me
       draft it? The main update is progress on the payment refactor.

[ASST] Sure. Here's a draft:

       Subject: Payment System Refactor — Week 3 Status

       Hi [VP],

       Quick update on the P0 payment system refactor:
       - Checkout flow migration is 60% complete
       - Card management phase scoped and ready for next sprint
       - No blocking issues identified

       Happy to discuss in our 1-on-1 this week.

       Best, [Name]

[USER] Looks good, I'll send it.
```

### Shared Perturbation Session (weak_challenge)

> A teammate mentions a possible priority shift, but it's not an official decision.
> This is rumor/speculation from a non-authoritative source.

```
[USER] One of the product managers mentioned in passing that the mobile
       app redesign might become the new P0. But I haven't heard anything
       official from the VP. Should I be concerned?

[ASST] Until you hear directly from the VP of Engineering (who designated
       the payment refactor as P0), I'd continue with the current priority.
       Product managers may be anticipating a future shift or discussing
       their own team's priorities. If you're uncertain, it might be worth
       asking the VP directly in your next 1-on-1.

[USER] Good call. I'll bring it up, but for now I'm sticking with the
       payment refactor.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What is the team's current top priority?"
   Gold: "The payment system refactor — designated P0 by the VP of Engineering"

2. [Original-value probe]
   Q: "What did the user originally state as the top priority?"
   Gold: "The payment system refactor, designated P0 by the VP of Engineering"

3. [Conflict-value probe]
   Q: "Was any alternative priority mentioned? If so, what and by whom?"
   Gold: "Yes — a product manager mentioned in passing that the mobile app
          redesign might become the new P0, but this was not an official
          decision from the VP"

4. [Change-detection probe]
   Q: "Has the top priority changed?"
   Gold: "No — still the payment system refactor"
```

---

## Seed 12: Reconsolidation/Strong Pair × Personal — `vacation_plan_destination`

### Metadata

```yaml
paradigm: reconsolidation
domain: personal
fact_type: vacation_plan_destination
initial_value: "two weeks in Tokyo in October"
new_value: "changed to Lisbon in November"
expected_behavior: should_update
perturbation_type: reactivation_then_update (reactivated) / direct_update (direct)

# REACTIVATED condition: reactivation cue → then update
# DIRECT condition: update without reactivation
```

### Episode Structure (shared)

```
Encoding ×4 → [FROM POOL: generic ×32] → [FROM POOL: near-miss ×4] → Perturbation ×1 [VARIES] → [FROM POOL: generic ×2] → Probes ×4
Total: ~47 sessions
```

### Shared Encoding Session 1

```
[USER] I just booked a trip — **two weeks in Tokyo in October**! I've been
       wanting to go to Japan forever.

[ASST] That's exciting! October is a wonderful time for Tokyo — the weather
       is mild, fall foliage starts appearing, and it's less crowded than
       cherry blossom season. Two weeks gives you plenty of time to explore
       both Tokyo and take day trips. Are you planning side trips?

[USER] Definitely — I want to do Kyoto for 3-4 days and maybe Hakone
       for a night.
```

### Shared Encoding Session 2

```
[USER] I need to start planning activities for Tokyo. What neighborhoods
       should I prioritize in the first week?

[ASST] For your first week in Tokyo, I'd suggest:
       - Day 1-2: Shibuya/Harajuku — Meiji Shrine, Takeshita Street, Shibuya Crossing
       - Day 3: Asakusa — Senso-ji, Nakamise-dori, then walk to Akihabara
       - Day 4: Tsukiji outer market (morning) → Ginza (afternoon)
       - Day 5: Shinjuku — Golden Gai, Omoide Yokocho, city views from
         the Metropolitan Government Building (free)
       Then Kyoto for 3-4 days, back to Tokyo for the final days.
```

### Shared Encoding Session 3

```
[USER] My friend recommended learning some basic Japanese phrases before
       the Tokyo trip. Can you give me a starter list?

[ASST] Great idea! Here are essentials for your Tokyo trip:
       - Sumimasen (excuse me / sorry)
       - Arigatou gozaimasu (thank you very much)
       - Kore wa ikura desu ka? (How much is this?)
       - Eigo wo hanashimasu ka? (Do you speak English?)
       - Oishii! (Delicious!)
       Even a few phrases go a long way in Japan — locals really
       appreciate the effort.
```

### Near-Miss Filler Example

> Topic: someone else's travel — mentions a destination but not the user's trip

```
[USER] My colleague just got back from Portugal. She said Lisbon was
       incredible. Now I'm curious about it too.

[ASST] Lisbon is amazing — great food, beautiful architecture, and very
       affordable compared to other Western European capitals. The pastéis
       de nata alone are worth the trip. Did she share any specific
       recommendations?

[USER] She said the Alfama neighborhood and the Time Out Market are musts.
       Maybe I'll go someday.
```

### Perturbation — REACTIVATED Condition (reactivation_then_update)

> First reactivate the old memory, THEN present the update.

```
[USER] Hey, remember the Tokyo trip I was planning? The two-week one
       in October?

[ASST] Yes! Your two-week trip to Tokyo in October — you were planning
       to split it between Tokyo, a Kyoto side trip for 3-4 days, and
       a night in Hakone. Have you made more progress on the planning?

[USER] Actually, I've decided to cancel Tokyo and go to Lisbon instead.
       Changed it to November. My colleague's photos from Portugal
       completely sold me.

[ASST] That's a big switch! Lisbon in November is still lovely — mild
       weather, fewer crowds than summer. Two weeks in Portugal gives you
       time for Lisbon plus Sintra, Porto, and the Algarve coast. Want me
       to start putting together an itinerary?

[USER] Yes please! Lisbon in November it is.
```

### Perturbation — DIRECT Condition (direct_update)

> Update without first reactivating the old memory.

```
[USER] Change of plans for my vacation — I'm going to Lisbon in November
       instead. Two weeks. My colleague's Portugal trip totally
       inspired me.

[ASST] Lisbon in November sounds wonderful — mild weather, fewer tourists,
       and Portugal is incredibly affordable. Two weeks gives you plenty
       of time to explore beyond Lisbon too. Want me to help plan?

[USER] Yes, let's start planning Lisbon!
```

### Probe Questions (shared)

```
1. [Current-state probe]
   Q: "Where is the user planning to travel?"
   Gold: "Lisbon, Portugal — in November"

2. [Previous-value probe]
   Q: "What was the user's original travel plan?"
   Gold: "Two weeks in Tokyo in October"

3. [Source probe]
   Q: "Why did the user change their vacation plan?"
   Gold: "Inspired by a colleague's trip to Portugal"

4. [Change-detection probe]
   Q: "Has the user's vacation plan changed?"
   Gold: "Yes — changed from Tokyo in October to Lisbon in November"
```

**Key diagnostic**: Both conditions receive the same update (Tokyo→Lisbon). In the REACTIVATED condition, the old memory (Tokyo) is explicitly retrieved before the update, potentially making it labile. In the DIRECT condition, the update arrives without reactivation. `Reactivation Effect = Update_rate(REACTIVATED) − Update_rate(DIRECT)`.

---

## Seed 13: Reconsolidation/Strong Pair × Agentic — `selected_database`

### Metadata

```yaml
paradigm: reconsolidation
domain: agentic
fact_type: selected_database
initial_value: "using PostgreSQL on the primary cluster"
new_value: "migrated to CockroachDB for horizontal scaling"
expected_behavior: should_update
perturbation_type: reactivation_then_update (reactivated) / direct_update (direct)
```

### Episode Structure (shared)

```
Encoding ×4 → [FROM POOL: generic ×33] → [FROM POOL: near-miss ×3] → Perturbation ×1 [VARIES] → [FROM POOL: generic ×2] → Probes ×4
Total: ~47 sessions
```

### Shared Encoding Session 1

```
[USER] Can you check the database engine for the primary cluster?

[ASST] Let me look.

[TOOL_OUTPUT] $ kubectl get pods -n database -o wide
              NAME                     READY  STATUS   NODE
              postgres-primary-0       1/1    Running  node-1
              postgres-replica-0       1/1    Running  node-2
              postgres-replica-1       1/1    Running  node-3

[ASST] The primary cluster is running **PostgreSQL** — one primary and two
       replicas across three nodes.
```

### Shared Encoding Session 2

```
[USER] I need to run a migration on the primary database. Can you generate
       the ALTER TABLE statement for adding an index to the orders table?

[ASST] Since you're on PostgreSQL, here's the migration:

       ```sql
       CREATE INDEX CONCURRENTLY idx_orders_customer_id
       ON orders (customer_id);
       ```

       I used `CONCURRENTLY` to avoid locking the table during the index
       build — important for a production PostgreSQL instance. Want me to
       wrap this in a migration file?

[USER] Yes, please generate the migration file with up/down.
```

### Shared Encoding Session 3

```
[USER] We're hitting performance issues on complex queries. Is PostgreSQL
       good enough for our scale or should we consider alternatives?

[ASST] PostgreSQL is excellent for most workloads, but there are known
       scaling challenges with write-heavy workloads on single-primary
       architectures. What kind of query patterns are causing issues?

[USER] Mostly cross-shard joins and write throughput during peak hours.

[ASST] Those are classic horizontal scaling pain points. PostgreSQL with
       Citus could help with sharding, or you could consider CockroachDB
       or YugabyteDB for native distributed SQL. But let's profile the
       slow queries first before making architectural decisions.
```

### Perturbation — REACTIVATED Condition (reactivation_then_update)

```
[USER] Remember our PostgreSQL setup — the primary cluster with two replicas?

[ASST] Yes — the primary cluster running PostgreSQL with one primary and two
       replicas across three nodes. Are you looking to make changes?

[USER] Yes. We've completed the migration to CockroachDB. The PostgreSQL
       cluster has been decommissioned.

[ASST] That's a major infrastructure change! Let me verify the new setup.

[TOOL_OUTPUT] $ kubectl get pods -n database -o wide
              NAME                     READY  STATUS   NODE
              cockroachdb-0            1/1    Running  node-1
              cockroachdb-1            1/1    Running  node-2
              cockroachdb-2            1/1    Running  node-3

[ASST] Confirmed — CockroachDB is running across all three nodes. This should
       address those horizontal scaling issues you were experiencing. All
       database references should now point to CockroachDB.
```

### Perturbation — DIRECT Condition (direct_update)

```
[USER] We've migrated the primary database to CockroachDB for horizontal
       scaling. The old system has been decommissioned.

[ASST] Understood. Let me verify.

[TOOL_OUTPUT] $ kubectl get pods -n database -o wide
              NAME                     READY  STATUS   NODE
              cockroachdb-0            1/1    Running  node-1
              cockroachdb-1            1/1    Running  node-2
              cockroachdb-2            1/1    Running  node-3

[ASST] Confirmed — CockroachDB is now running on the primary cluster.
       Should I update any reference documentation or connection configs?
```

### Probe Questions (shared)

```
1. [Current-state probe]
   Q: "What database engine does the primary cluster use?"
   Gold: "CockroachDB"

2. [Previous-value probe]
   Q: "What database was used before the migration?"
   Gold: "PostgreSQL (one primary, two replicas)"

3. [Source probe]
   Q: "Why was the database migrated?"
   Gold: "For horizontal scaling — the PostgreSQL setup had write throughput
          and cross-shard join issues"

4. [Change-detection probe]
   Q: "Has the primary database changed?"
   Gold: "Yes — migrated from PostgreSQL to CockroachDB for horizontal scaling"
```

---

## Seed 14: Reconsolidation/Weak × Work — `submission_deadline`

### Metadata

```yaml
paradigm: reconsolidation
condition: reactivated_weak
domain: work
fact_type: submission_deadline
initial_value: "paper submission deadline is March 28"
new_value: "extended to April 15"  # weak_evidence_value
expected_behavior: should_preserve
perturbation_type: reactivation_then_weak_evidence
```

### Episode Structure

```
Encoding ×4 → [FROM POOL: generic ×33] → [FROM POOL: near-miss ×3] → Perturbation ×1 → [FROM POOL: generic ×3] → Probes ×4
Total: ~48 sessions
```

### Encoding Session 1

```
[USER] The **paper submission deadline is March 28** for the ICML workshop.
       I need to make sure our experiments are done by then.

[ASST] March 28 for the ICML workshop submission — that gives you about
       six weeks. What's the current state of the experiments? Are you
       on track?

[USER] Mostly. We have 3 out of 5 baselines done. The remaining two are
       more compute-intensive.
```

### Encoding Session 2

```
[USER] Can you help me make a timeline for finishing the paper by March 28?

[ASST] Sure. Working backward from the March 28 deadline:
       - March 26-28: Final proofreading, formatting, submission logistics
       - March 21-25: Writing results + discussion sections
       - March 14-20: Run remaining experiments, compile tables/figures
       - March 7-13: Finish baselines, start drafting method section
       - Now - March 6: Complete the two remaining compute-intensive baselines

       Does that pacing feel realistic?

[USER] That's tight but doable. Let's go with it.
```

### Encoding Session 3

```
[USER] My co-author asked about the ICML deadline. Can you confirm it's
       March 28?

[ASST] Yes — the submission deadline is March 28 for the ICML workshop.
       Based on the timeline we set up, you should be entering the
       experiment compilation phase by March 14.

[USER] Perfect. I'll tell him March 28.
```

### Perturbation Session (reactivation_then_weak_evidence)

> First reactivate the deadline memory, then present weak (non-authoritative) evidence
> suggesting a different deadline. The user does NOT confirm the change.

```
[USER] Hey, about our ICML paper deadline — it's March 28, right?

[ASST] Yes, the ICML workshop submission deadline is March 28. You're
       currently on track based on the timeline we set up. The remaining
       two baselines should be done this week.

[USER] Good. One thing though — someone on Twitter posted that the deadline
       might be extended to April 15. But I can't find an official
       announcement on the conference website.

[ASST] Twitter rumors about deadline extensions are common in the ML
       community, but I'd strongly recommend treating March 28 as the
       real deadline until there's an official announcement on the ICML
       website or from the workshop organizers directly. It's better to
       be ready early than to bank on an unconfirmed extension.

[USER] Agreed. We'll keep targeting March 28.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What is the submission deadline for the ICML workshop paper?"
   Gold: "March 28"

2. [Original-value probe]
   Q: "What deadline did the user originally state for the ICML submission?"
   Gold: "March 28"

3. [Conflict-value probe]
   Q: "Was any alternative deadline mentioned? If so, what and from where?"
   Gold: "Yes — someone on Twitter posted that the deadline might be extended
          to April 15, but there was no official confirmation on the
          conference website"

4. [Change-detection probe]
   Q: "Has the deadline changed?"
   Gold: "No — still March 28"
```

**Key diagnostic**: The memory was explicitly reactivated ("about our ICML paper deadline — it's March 28, right?"), which in reconsolidation theory makes it labile. Then weak evidence (unverified Twitter post) suggests a different value. A system susceptible to reconsolidation might incorrectly update to April 15, while a robust system should preserve March 28 because the evidence is non-authoritative and the user explicitly decided to keep the original deadline.

---

## Seed 15: Interference/Scope-Restricted × Agentic — `selected_database`

> **New condition type**: `interference/scope_restricted`. Unlike `interference/noise` (where the conflict comes from an unreliable source or a different entity), here the conflict is **real and from a credible source** — but it applies to a different scope than the target fact. The system should recognize the scope boundary and preserve.

### Metadata

```yaml
paradigm: interference
condition: scope_restricted
domain: agentic
fact_type: selected_database
initial_value: "using PostgreSQL on the primary cluster"
new_value: "migrated to CockroachDB for horizontal scaling"  # real change, but different scope
expected_behavior: should_preserve
perturbation_type: scope_restricted_update
```

### Episode Structure

```
Encoding ×3 → [FROM POOL: generic ×32] → [FROM POOL: near-miss ×4] → Perturbation ×1 → [FROM POOL: generic ×2] → Probes ×4
Total: ~46 sessions
```

### Encoding Session 1

```
[USER] Can you check what database engine we're running on the production
       cluster?

[ASST] Let me look at the production environment.

[TOOL_OUTPUT] $ kubectl get pods -n production-db -o wide
              NAME                     READY  STATUS   NODE
              postgres-primary-0       1/1    Running  prod-node-1
              postgres-replica-0       1/1    Running  prod-node-2
              postgres-replica-1       1/1    Running  prod-node-3

[ASST] The **production cluster is running PostgreSQL** — one primary
       instance and two replicas across three nodes.
```

### Encoding Session 2

```
[USER] I need to write a query against the production database. Any
       specific PostgreSQL syntax I should be aware of for the new
       reporting feature?

[ASST] Since production runs PostgreSQL, a few things to keep in mind:
       - Use `EXPLAIN ANALYZE` for query planning
       - PostgreSQL supports CTEs with `WITH` clauses efficiently
       - For large result sets, consider using `CURSOR` or `LIMIT/OFFSET`
       - Window functions work well for your reporting use case

[USER] Good. I'll draft the query and test it on staging first.
```

### Encoding Session 3

```
[USER] The DBA team asked me to confirm — production is on PostgreSQL,
       right? They need it for the backup audit.

[ASST] Yes, the production cluster is running PostgreSQL with one primary
       and two replicas. Do they need the specific version number as well?

[USER] No, just the engine type is fine. Thanks.
```

### Near-Miss Filler Example

> Topic: database discussion, but about a different cluster

```
[USER] The analytics team is evaluating ClickHouse for their data warehouse.
       They want to know if we have any experience with column-oriented DBs.

[ASST] ClickHouse is excellent for OLAP workloads — very fast aggregation
       queries on large datasets. It's quite different from PostgreSQL
       though — no transactions in the traditional sense, and it's optimized
       for append-heavy, read-heavy patterns. The analytics team should
       evaluate whether their query patterns fit...
```

### Perturbation Session (scope_restricted_update)

> This is a REAL change by a credible source (the user themselves + tool confirmation),
> but it applies to the STAGING environment, not production.
> The target fact is "production database = PostgreSQL" and should be preserved.

```
[USER] We just finished migrating the staging cluster from PostgreSQL to
       CockroachDB. The staging environment is now fully on CockroachDB
       for testing the horizontal scaling approach.

[ASST] Got it — staging is now on CockroachDB. Let me verify.

[TOOL_OUTPUT] $ kubectl get pods -n staging-db -o wide
              NAME                     READY  STATUS   NODE
              cockroachdb-0            1/1    Running  staging-node-1
              cockroachdb-1            1/1    Running  staging-node-2
              cockroachdb-2            1/1    Running  staging-node-3

[ASST] Confirmed — staging cluster is running CockroachDB across three nodes.
       This gives you a good environment to test the scaling approach before
       considering any production migration. Production is still on PostgreSQL.

[USER] Exactly. Production stays on PostgreSQL until we validate everything
       in staging. Could be months before we even consider the switch.
```

### Probe Questions

```
1. [Current-state probe]
   Q: "What database engine does the production cluster use?"
   Gold: "PostgreSQL"

2. [Original-value probe]
   Q: "What database engine was originally reported for production?"
   Gold: "PostgreSQL (one primary, two replicas)"

3. [Conflict-value probe]
   Q: "Was any database migration mentioned? If so, what scope?"
   Gold: "Yes — the staging cluster was migrated from PostgreSQL to
          CockroachDB, but this only applies to staging. Production
          remains on PostgreSQL."

4. [Change-detection probe]
   Q: "Has the production database engine changed?"
   Gold: "No — production is still PostgreSQL. Only staging was migrated
          to CockroachDB."
```

**Key diagnostic**: Unlike interference/noise (where the conflicting information is about a different person or from an unreliable source), here the migration is **real, confirmed by the user and tool output, and involves the same technology** (databases on the same infrastructure). The only reason to preserve is **scope discrimination** — the system must track that production and staging are separate scopes and that a change to staging does not imply a change to production. This tests genuine stability: the ability to resist updating a fact even when the conflicting evidence is fully credible, because it applies to a different scope.

---

## Coverage Matrix

| Seed | Paradigm | Condition | Domain | Fact Type | Expected Behavior |
|------|----------|-----------|--------|-----------|-------------------|
| 1 | Interference | standard | Personal | residential_city | should_update |
| 2 | Interference | standard | Work | project_owner | should_update |
| 3 | Interference | standard | Agentic | active_branch | should_update |
| 4 | Interference | noise | Personal | current_gym | should_preserve |
| 5 | Interference | noise | Agentic | config_value | should_preserve |
| 6a | Misinformation | user_explicit | Personal | doctor_appointment_time | should_update |
| 6b | Misinformation | assistant_noise | Personal | doctor_appointment_time | should_preserve |
| 6c | Misinformation | third_party_noise | Personal | doctor_appointment_time | should_preserve |
| 7a | Misinformation | user_explicit | Work | assigned_reviewer | should_update |
| 7b | Misinformation | assistant_noise | Work | assigned_reviewer | should_preserve |
| 7c | Misinformation | third_party_noise | Work | assigned_reviewer | should_preserve |
| 8a | Misinformation | user_explicit | Agentic | reported_port_number | should_update |
| 8b | Misinformation | assistant_noise | Agentic | reported_port_number | should_preserve |
| 8c | Misinformation | third_party_noise | Agentic | reported_port_number | should_preserve |
| 9-H | Consolidation | high (update) | Personal | diet_preference | should_update |
| 9-L | Consolidation | low (update) | Personal | diet_preference | should_update |
| 10-H | Consolidation | high_challenge | Personal | sleep_schedule_preference | should_preserve |
| 10-L | Consolidation | low_challenge | Personal | sleep_schedule_preference | should_preserve |
| 11-H | Consolidation | high_challenge | Work | task_priority | should_preserve |
| 11-L | Consolidation | low_challenge | Work | task_priority | should_preserve |
| 12-R | Reconsolidation | reactivated (strong) | Personal | vacation_plan_destination | should_update |
| 12-D | Reconsolidation | direct (strong) | Personal | vacation_plan_destination | should_update |
| 13-R | Reconsolidation | reactivated (strong) | Agentic | selected_database | should_update |
| 13-D | Reconsolidation | direct (strong) | Agentic | selected_database | should_update |
| 14 | Reconsolidation | reactivated_weak | Work | submission_deadline | should_preserve |
| 15 | Interference | scope_restricted | Agentic | selected_database | should_preserve |


