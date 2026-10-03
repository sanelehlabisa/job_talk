# JobTalk core MVP

## Goal

Build and validate one hiring loop:

> Recruiter defines an ideal candidate -> candidate applies through chat ->
> JobTalk scores the match -> recruiter compares the best candidates.

The release question is: **can one recruiter create a job, can one candidate
apply through chat, and can the recruiter compare candidates clearly?**

## Current usability target (2026-10-03)

The conversation fills a shared structure; it does not remove that structure.
The user has not accepted the current app as usable. Deployment is paused while
the planned tickets JT-057 through JT-062 in [TASKS.md](../TASKS.md) improve the
existing flow. Passing prior scripted tests does not replace manual acceptance.
The behavior below describes the target. JT-057 supplies the template picker and
persisted draft structure. JT-058 implements validated template updates,
not-required handling, the live summary and publication gate.
JT-059 adds explicit candidate selection, structured updates and a live application
summary. JT-064 passed one developer hiring loop and discovery extraction with
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
5. Published criteria remain locked for comparable applications. Closing the role
   stops new applications and unfinished drafts; submitted snapshots remain.

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
Title, description, and source metadata do not become scoring criteria.

Publication requires a clear title and role description, arrangement/location
rules (including any remote location restriction or explicit lack of one), at
least one meaningful confirmed assessment criterion, and all other template
fields confirmed or explicitly not required. The **Publish** action stays final.

## Candidate flow

1. Accountless seekers can open a direct job link, choose one of two **available
   jobs**, or use **Find a different job** to describe their background. The two
   initial cards are not personalized matches.
2. Discovery compares their evidence with every published, open job in the
   database, including jobs absent from the two cards. It shows actual listings
   and an honest no-match state; the AI never invents vacancies.
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
quotes. They cannot return jobs or modify criteria, weights or scores. Validation
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

- Deterministic backend code compares candidate values with criterion targets.
- The overall score is the weighted mean of criterion scores.
- Recommendations include at most five jobs above the minimum useful threshold.
- A recruiter sees at most five leading candidates with contact details, score,
  evidence, and gaps.
- The parallel-axis view plots the ideal profile and those candidates using the
  same criteria. Evidence cards remain the readable explanation.
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
curated-job interest counts appear in the shared chat. Backend scores, published
criteria locks and login approval follow the same flow as ordinary recruiters.
No new account type, storage, or permission-management system is introduced.

## Usability acceptance

JT-060 tests messy descriptions, multiple answers in one message, short replies,
corrections, unrelated answers, explicit gaps, and persisted state on desktop and
phone. Record actual LLM behavior separately from mocked/fallback tests, including
when live calls were not run or silently fell back. Use fictional test data.
The existing provider and guided fallback stay within `services/ai.py`; the backend
owns validation, weights, publication readiness, and deterministic scores.

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
