# JobTalk core MVP

## Goal

Build and validate one hiring loop:

> Recruiter defines an ideal candidate -> candidate applies through chat ->
> JobTalk scores the match -> recruiter compares the best candidates.

The release question is: **can one recruiter create a job, can one candidate
apply through chat, and can the recruiter compare candidates clearly?**

## Current usability target (2026-10-03)

The conversation fills a shared structure; it does not remove that structure.
The user has not completed final usability sign-off. The planned production URL
is `https://jobtalk.roventics.com`; live DNS/TLS/SMTP checks and VM deployment are
pending. JT-070 prepared and locally verified production HTTPS. JT-069 keeps
published chats editable, preserves submitted scores and shows immediate job
examples. Passing scripted tests does not replace manual acceptance.
The behavior below describes the implemented loop. JT-057 supplies the template picker and
persisted draft structure. JT-058 implements validated template updates,
not-required handling, the live summary and publication gate.
JT-059 adds explicit candidate selection, structured updates and a live application
summary. JT-072 uses one editable label/value answer per criterion, matching the
recruiter form. Requirements appear as input hints; clearing an answer keeps the
criterion. Chat and form edits share the same profile. Contact review, consent
and explicit Submit sit at the bottom of the form, with no second review panel
inside chat. Submitted answers remain frozen. JT-064 passed one developer hiring loop and discovery extraction with
actual Gemini responses; broader live scenarios and user acceptance remain open.
OpenAI attempts were blocked by exhausted API credit. JT-061 implements owner access; JT-062 adds manually entered,
source-labelled vacancies and operator-only submission consent.

The local UI currently uses a separate seeded Gemini test database after an
assistant test-isolation error dropped the earlier development tables. Prior
records are not recovered; see the [incident record](usability-checklist.md#local-test-data-incident-2026-10-03)
before changing local database settings or removing volumes.

## One shared criteria contract

The same stable criterion keys must be used from job creation through candidate
comparison. AI can interpret and polish text, while the backend validates the
stored shape and calculates scores.

```json
{
  "job_title": "Plumber",
  "location": "Cape Town",
  "criteria": [
    {
      "key": "plumbing_experience",
      "label": "Plumbing experience",
      "type": "number",
      "target": 3,
      "unit": "years",
      "weight": 0.9,
      "description": "At least three years of practical plumbing work"
    },
    {
      "key": "geyser_installation",
      "label": "Geyser installation",
      "type": "skill",
      "target": true,
      "weight": 0.8,
      "description": "Can install and replace domestic geysers"
    }
  ]
}
```

Candidate evidence uses the same key:

```json
{
  "criterion_key": "plumbing_experience",
  "value": 4,
  "evidence": "Four years doing residential plumbing repairs"
}
```

A match result remains inspectable:

```json
{
  "criterion_key": "plumbing_experience",
  "candidate_value": 4,
  "target_value": 3,
  "score": 1,
  "weight": 0.9,
  "evidence": "Four years doing residential plumbing repairs",
  "reason": "Meets the three-year target"
}
```

## Recruiter flow

1. A manually approved recruiter signs in using an emailed code.
2. They start a separate draft using Junior Software Developer, Plumber, or
   Generic Role, then describe the role or paste a description.
3. JobTalk fills every field supported by the message, even when that field's
   question has not yet been asked. It updates existing keys for corrections and
   asks only about missing or unclear fields.
4. A live **Who you're looking for** summary shows the saved labels, values, and
   unresolved fields beside the chat (stacked on phone). The recruiter can correct
   it in conversation, review the final requirements, and explicitly publish.
5. Chat and form remain editable after publishing. Save changes in the same draft
   and use **Publish changes** to update the live job. Closing the role stops new
   applications and unfinished candidate drafts; recruiter chat remains available.
   Submitted applications preserve their requirements, evidence and scores.

### Template and field rules

Use one small shared JSON structure with three fixed starter templates. Include
title, short description, work arrangement/location, skills, tools, experience,
qualifications, working hours, and start availability. Keep the existing database
model and JSON fields where practical; each job owns a separate draft. No template
editor or generalized form engine is needed.

The implemented catalogue is `backend/app/job_templates.json`: shared fields
plus three sets of suggestions, served through the authenticated
`GET /api/job-templates` endpoint. `POST /api/chats` accepts `template_id` and
creates an independent draft. A nullable JSON `job_posts.draft` field keeps
suggestions and field states outside `target_profile`, so neither suggestions
nor metadata enter scoring. Private recruiter chat responses expose it as
`job_draft`; public job responses do not include it. Existing no-template chats
remain supported.

Drafts start unanswered. The model sees the complete authorized chat and saved
draft. It proposes changed fields with exact source quotes from the current
user message, or earlier user messages for unanswered fields. Older statements
cannot overwrite saved corrections. Spelling repairs and natural wording can
map to known fields without literal field labels; source quotes stay verbatim.
The backend validates quotes, types, keys, explicit exclusions and quantities;
owns weights and readiness; and rebuilds scoring criteria from confirmed fields.
It asks the next unresolved question after saving, so rejected proposals cannot
be announced as accepted. Polished descriptions still need recruiter review.
Choosing a starter never confirms its title, criteria, or other suggestions.

JT-066 removes the 12-message/800-character history truncation. The provider
input has a 128,000-character ceiling; exceeding it triggers guided fallback
instead of silently dropping earlier messages. Output and call caps remain.

If the provider is unavailable, a small guided parser accepts explicit labelled
answers and exclusions. This fallback is not a substitute for live LLM acceptance.
Older no-template jobs keep their existing flow and publication checks.

Template suggestions are kept separate from confirmed answers. Existing criterion
keys and types are reused, including `education` for qualifications. Years are a
numeric target only when requested; skills and text requirements also remain
valid targets. Draft fields use these states:

| State | Meaning | Follow-up and scoring |
| --- | --- | --- |
| `unanswered` | No supported answer yet; may display a suggestion | Ask; exclude from scoring |
| `needs_clarification` | Ambiguous or conflicting answer | Clarify; exclude from scoring |
| `confirmed` | Supported and validated requirement | Do not repeat; score only assessment criteria |
| `not_required` | Employer explicitly says it does not apply | Do not repeat; exclude from scoring and plot |

"No degree needed" resolves qualifications as not required. "That's fine" alone
cannot remove an unclear requirement. Preferred requirements remain confirmed
criteria with backend-owned importance, distinct from not-required fields.
Title, description, company details and source metadata do not become scoring criteria.

JT-082 starts new recruiter drafts with company name and company location. Both
must be confirmed before publication. The company base is separate from where
the candidate will work. Store both in existing draft JSON, snapshot them on
Publish, and show the published values on job cards and the application form.
Include them in the candidate's authorized model context. Older jobs without
company details remain readable; do not invent their employer information.

Publication requires a clear title and role description, arrangement/location
rules (including any remote location restriction or explicit lack of one), at
least one meaningful confirmed assessment criterion, and all remaining fields
confirmed or explicitly not required. The **Publish** action stays final.

JT-067 lets recruiters edit, add and remove fields directly in the same summary.
Save sends the current chat and one explicit form edit to AI for polishing, then
validates it before updating the saved draft and scoring profile. Form edits are
recorded in the conversation, so later replies see the recruiter's corrections.
If polishing is unavailable, a notice says the original wording was saved.
Numeric targets retain their quantity/unit; weights are never client-controlled.

**Done**, including "ready for publication" in chat, removes unanswered optional
suggestions. It preserves company details, title, duties, work arrangement, location rules and any
partially answered requirement needing clarification. Removed keys stay in the
draft JSON so historical quotes cannot reintroduce them; a new explicit request
can restore them. An explicit chat request to remove a field also removes it.
Unanswered/unclear fields have red borders; confirmed/not-required fields have green borders.
Age and other personal characteristics are informational notes only and are
excluded from the candidate application structure, scores and matching filters.
No new table, migration or template-management system is introduced.

JT-068 simplifies the summary and editor to one label and one editable value.
State badges, duplicate descriptions and type/importance/unit controls are hidden.
The backend keeps the typed contract, including numeric units and preferred weights.
Save still requests AI wording polish; a failed provider call keeps the entered value.
Add/Edit/Remove/Save/Cancel/Done use labelled icons.

Closing date is optional metadata in the existing draft JSON. Chat accepts an
explicit calendar date with a year; the form offers a date input. An unanswered
closing date neither triggers follow-ups nor blocks publishing. The date is never
part of candidate criteria or scores. Public jobs expose it; requests after that
day in UTC exclude the job from discovery and reject candidate starts, messages
and submissions. Recruiters retain their job and submitted applicants. No scheduler
or database migration is needed. Deadline edits go live with **Publish changes**.

### Published changes (JT-069)

The existing job draft is the editable version; the job title, description and
target profile stay live until explicit publication. Store the live closing date
in draft JSON separately from the edited field. No new job or chat is created.
Submitted match-result JSON includes a requirements snapshot and criteria
fingerprint. Earlier applications retain their original scores and have an
**Earlier requirements** label, excluded from the current plot and ranking.
The candidate UI submits the fingerprint it reviewed; a changed role requires
refresh and review before submission. Closed jobs cannot be republished.

## Candidate flow

1. Accountless seekers can open a direct job link, choose one of two **available
   jobs**, or use **Find a different job** to describe their background. The two
   initial cards are not personalized matches.
2. Discovery compares their evidence with every published, open job in the
   database, including jobs absent from the two cards. Its guidance and up to two
   available-job examples appear immediately, without scores or personalised
   claims. Suggestions change as evidence arrives. When no useful match exists,
   keep examples labelled clearly; when no jobs are open, say so. Never invent vacancies.
   Matching uses confirmed text targets and the selected work arrangement, not
   generic starter descriptions. Related discovery evidence can support a
   suggestion without creating a direct answer to that job's criterion.
   JT-074 uses a separate 0.15 exploratory cutoff and a work-related term in common
   with the real role. Shared location/hours alone do not justify a suggestion.
   Search every open job before limiting the results to two; recalculate on each
   message. Number cards and refer to the same ordered vacancies in the reply.
   Show entry guidance once, hide raw profile chips and discovery percentages,
   and retain the score on the selected application. The recruiter recommendation
   threshold and submitted scores are unchanged. Full-stack search can relate to
   software roles without inventing a job-specific skill or application answer.
3. On explicit job selection, the application binds to its confirmed criteria.
   Carry forward only evidence from that guest's own discovery chat. Keep opaque,
   expiring tokens and one application per scope; do not expose other chats.
4. AI proposes grounded values and readable evidence for all relevant fields in
   an answer; the backend validates and saves them under the job's stable keys.
   A live **Your application** summary shows answers and remaining gaps. Ask only
   focused questions about missing or unclear evidence.
5. A reported lack of a skill is a resolved gap. It remains visible and can lower
   the match score without changing the job or blocking an honest application.
   Corrections replace the affected value, and polishing never adds a credential,
   tool, skill, duration, or accomplishment that the candidate did not state.
6. The candidate reviews the structured application, adds name, location, and
   email or phone, gives clear consent, and explicitly submits a frozen snapshot.

JT-059 uses `POST /api/chats/{chat_id}/select-job` with a real public job ID.
Ownership is checked and the chat can bind only once. Earlier user statements in
that guest's chat are replayed against the selected criteria; other conversations
are never read. `application_fields` in the private chat response derives the
summary from the same job criteria and saved profile used for scoring.

Candidate model responses propose typed values, states, evidence and source
quotes. Extraction cannot return jobs or modify criteria or weights; a separate
bounded Gemini batch rates only validated saved answers. Validation
limits updates to actual criterion keys after selection and prevents an older
statement from overwriting a later saved correction. If polished wording adds
unsupported terms, the source wording is retained. The deterministic fallback
keeps separate clauses' durations and gaps together and identifies guided mode
once per conversation, without repeating the notice in every reply.
Both paths reject an explicitly different known trade/tool as evidence for a
scoped experience requirement: Python years must not satisfy plumbing years.
Keep the original experience wording so the recruiter can see its scope. This
small guard uses the existing skill vocabulary; bare duration follow-ups and
general work-experience requirements remain supported.
These checks do not establish semantic accuracy; actual LLM acceptance remains open.

Discovery suggestions are filtered at the existing useful-match threshold.
Common linking words do not count as evidence for an unrelated role. Text
location comparisons use saved targets, and unclear numeric answers score zero.
Submission contact review preserves a separately captured job-location answer.

## Matching and comparison

- With Gemini configured, a single bounded rating request compares validated
  candidate answers with all relevant published job criteria, using the complete
  authorized chat to interpret context. It returns 0–100 per criterion and a short
  reason. The backend rejects invalid keys, scores and evidence references.
- Missing/unclear application answers, cleared fields and explicit gaps score zero.
  No model call is made on refresh: ratings are stored in existing chat JSON and
  tied to the exact evidence and criteria. Changes invalidate the old ratings.
  Submission freezes the score the candidate reviewed; contact details do not add
  evidence. All recruiter cards and plot axes use that same saved assessment.
- Gemini failures, limits and mock/OpenAI modes use the existing rule estimate.
  Both sides label the estimate source; scores remain unverified claims for human review.
- Criterion ratings remain 0–100. For fully met numeric requirements with direct
  evidence, `comparison_score` may exceed 1 (four years against two gives 2).
  Partial ratings, gaps and missing evidence earn no excess credit.
- `ranking_score` is the uncapped weighted mean of comparison scores. Candidate
  order uses that value; new overall matches are capped at 100% for display.
  Existing submissions keep their frozen overall match; the API derives their
  comparison values from saved evidence without rewriting stored snapshots.
- Recommendations include at most five jobs above the minimum useful threshold.
- A recruiter sees at most five leading candidates with contact details, score,
  evidence, and gaps. Current candidate cards are numbered in ranking order.
- The parallel-axis view plots the ideal profile and those candidates using the
  same criteria. The ideal stays at 100 and the axis expands for excess numeric
  evidence. Evidence cards remain the readable explanation.
- Not-required and unresolved job fields never contribute to the weighted mean
  or plot. Missing candidate evidence remains missing; reported gaps remain gaps.
- Initial available-job cards and below-threshold roles are not recommendations.
  Candidate-card summaries must reflect the saved evidence without overstating
  strengths or hiding gaps.

## Persistence and manual vacancy entry

Jobs already live in PostgreSQL `job_posts` with title, description, owner,
publication state, and a JSON criteria profile. Chats, messages, and submitted
application snapshots are also persisted, using the existing local named volume.
No additional storage service is needed.

JT-062 adds an owner workflow to paste a manually checked vacancy into the same
draft/review/publish flow. Keep source URL, employer name, date checked, and source
text with the job. The owner resolves unclear fields before publication and can
close stale or filled listings. Verify persistence across a normal local restart.
No scraping or automatic job feeds are planned.

Implemented using optional `source` metadata inside the existing `JobDraft` JSON:
`url`, `employer`, `checked_on` and `original_text`. Only an approved configured
owner can supply it when creating a template chat. The saved source is immutable;
template interpretation preserves it and scoring excludes it. Public responses
expose only URL, employer and date checked. Original text remains in the private
draft and is sent through the existing message flow when the owner chooses
**Fill draft from pasted text**. URLs are validated and deduplicated, never fetched.

Candidate entry, discovery cards, chat, review and submission show who receives
curated-job interest. Its saved consent grants operator access and explicitly
records that employer sharing is not authorized. `GET /api/admin/jobs/{id}/interest`
returns only aggregate application/match counts and counts of strong evidence per
criterion (score at least 0.75 with direct evidence). It contains no applicant
identifiers, individual values, contact details or evidence text. Existing scores
are reused; no new scoring system or database migration is introduced.

Clearly label jobs curated by Job Talk and identify who receives a submission.
An external advert does not establish that its employer is participating. The
owner can use non-identifying match summaries/counts to demonstrate interest to
prospective recruiters. Sharing contact details with them requires candidate
authorization; automated outreach, exports, and job transfers remain deferred.

## Owner and recruiter access

JT-061 implements one optional, backend-only `ADMIN_EMAIL`, set by the owner in ignored
`.env`. No address is assumed. The configured owner still needs approval and
the existing emailed-code login. After verifying the single-use code, protected
API requests use the existing unguessable, expiring bearer session token.

The backend derives privileges from that verified identity on every request.
JT-065 gives the owner the same recruiter workspace with every job-creation
chat. The normal `GET /api/chats` list includes owner email labels for admin.
Admin can read and continue any recruiter draft, publish and close jobs, and
review submitted applications through the existing controls. Original ownership
is retained. Ordinary recruiters see only their own chats and applicants;
candidate guest sessions retain access only to their own conversations.

The separate All jobs dashboard and its list endpoint are removed. The existing
`GET /api/applications?job_id=...` still checks ownership or admin identity, and
curated-job interest counts appear in the shared chat. Backend scores, explicit
publication of edits and login approval follow the same flow as ordinary recruiters.
No new account type, storage, or permission-management system is introduced.

## Usability acceptance

JT-060 tests messy descriptions, multiple answers in one message, short replies,
corrections, unrelated answers, explicit gaps, and persisted state on desktop and
phone. Record actual LLM behavior separately from mocked/fallback tests, including
when live calls were not run or silently fell back. Use fictional test data.
The existing provider and guided fallback stay within `services/ai.py`; the backend
owns validation, weights, publication readiness, and weighted score totals.

The [manual checklist](usability-checklist.md) is the user's acceptance gate.
Automated success does not mark the app usable or resume deployment. Deployment
waits for user acceptance and an explicit request to resume it.

## Included scope

Recruiter login and manual approval; conversational job creation; structured
criteria; publishing; accountless job applications; contact details;
conversational evidence collection; explainable criterion scoring; top job
recommendations; top candidate comparison; parallel-axis comparison.

The current requested additions are the three fixed templates, live structured
summaries, one configured owner view, and manually entered source-labelled jobs.

Everything else waits for evidence from real use.
