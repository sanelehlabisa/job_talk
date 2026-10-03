# Recruiter draft checks — 2026-10-03

Deployment remains paused. These are engineering checks, not user sign-off.

## JT-066: complete history and repeated questions

Actual Gemini / `gemini-3.5-flash-lite`, 2026-10-03: replaying the user's misspelled
Durban graduate-electronics paragraph showed that the model already found the
title, arrangement, degree/60% requirement and skills. The old validator rejected
them because the wording did not literally match field labels or spelling.
Recruiter updates were also restricted to quotes from the current message.

The fix passes the entire authorized transcript, validates exact quotes while
allowing natural mapping to known fields, accepts minor title/exclusion spelling
errors, and permits old user evidence only for unanswered fields. Later saved
corrections take precedence. Source quotes must be contiguous, not stitched from
separate phrases; an initial recovery run exposed that issue and the prompt was
corrected without relaxing the quote check.

All 103 isolated backend tests passed. Real Gemini checks saved the initial
paragraph, a later change to two years of experience, and recovered no-experience,
qualifications and circuit knowledge in a reproduction of the older incomplete
chat. Working hours was the next question. Availability and tools were not
invented. These calls used disposable SQLite; existing user chats were untouched.

To check the existing UI, refresh and continue the same draft with: "Use everything
I already told you and ask only for missing details." Check the saved summary:
Graduate Electronic Engineer, Durban, on-site, BSc/BEng with 60%+, experience not
required, and circuit knowledge. Confirm only the genuinely unanswered fields
remain. The original JT-058 checks below are retained as historical evidence.

## Implementation

- Current-chat context includes saved template fields and states. Template
  suggestions are omitted from provider input. Updates reuse existing keys.
- Model output uses the existing Responses API with a strict JSON schema, following
  [OpenAI's structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
  The backend validates proposed sources, shapes, quantities and exclusions,
  owns weights, and asks the next unresolved question from the saved result.
- Confirmed criteria alone enter the job profile and comparison contract.
  Explicit exclusions remain in the draft summary. Preferred criteria have a
  lower backend-owned weight. Metadata never becomes a score axis.
- Publish requires resolved fields, a clear role and work arrangement/location,
  plus a meaningful assessment criterion. Published criteria stay locked.

## Deterministic and browser evidence

- The full backend regression run passed 66 tests. Seven focused draft tests
  were then run after the final short-answer/correction changes (including two
  added cases). They cover multi-field updates, corrections, explicit exclusions,
  ambiguous answers, unsupported quantities, current-chat context, persistence,
  public/private boundaries, remote-location rules and publication locking.
- The frontend production build passed.
- `scripts/local-signoff.ps1 -RecruiterEmail templates-check@example.com
  -RecruiterDraftOnly` passed using fictional data and an approved local account.
  The desktop and phone screenshots were reviewed. The browser used the guided
  fallback: it captured a labelled role, changed experience to three years,
  preserved it after “That's fine” and refresh, and explicitly published/locked it.
- Plumber and Generic Role completion with labelled answers was checked through
  the deterministic parser. A mocked provider checks a multi-field developer
  description and a later correction. These are not live language results.

## Actual LLM attempt

Provider/model: OpenAI / `gpt-4o-mini`, 2026-10-03.

One fictional messy junior-developer paragraph was sent through the configured
provider. OpenAI returned HTTP 429, `credit_balance_exhausted`; no model updates
were produced and the guided fallback was used. Live interpretation, polishing,
and varied follow-up conversations remain **unverified**. JT-058 acceptance stays
open until those checks can run. No credentials or real candidate data were used
in the test text or recorded here.

The current local response limit was 1000 tokens. The backend/development example
now defaults to 3000 for whole-template updates; existing ignored `.env` values
are retained and should be updated before repeating a long live conversation.

## Short manual check

1. Choose Junior Software Developer. Describe duties, skills, hybrid/location,
   hours and availability in one messy paragraph. Check every captured field.
2. Change one experience requirement; say “No degree needed,” then “That's fine.”
   Check that only the intended fields change and no resolved question repeats.
3. Create separate Plumber and Generic Role drafts. Resolve or exclude remaining
   fields; review the summary on phone and desktop, refresh, then explicitly
   publish. Confirm suggestions were not assumed and editing is locked afterward.

Repeat with actual LLM responses once API credit is available. Candidate-side
improvements and the complete hiring-loop sign-off remain JT-059/JT-060.
