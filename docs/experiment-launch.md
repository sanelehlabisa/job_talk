# Job Talk recruiter experiment

## Experiment statement

**Question:** Will recruiters find conversational applications and structured
candidate comparison useful?

**Audience:** manually approved recruiters hiring for trade or entry level work,
plus candidates invited through public job links.

**Offer:** free access during the experiment in exchange for direct feedback.

The experiment measures usage and usefulness. It does not test pricing,
automated recruiter verification, broad job discovery, or integrations.

## Narrow product flow

### Recruiter

1. A recruiter is approved manually and signs in.
2. The recruiter opens one of 3-5 realistic seeded jobs.
3. The recruiter sees submitted candidates for that job.
4. Candidate summaries use the same fields, criterion scores, evidence, and gaps.
5. The recruiter compares at least two candidates and answers one usefulness question.

### Candidate

1. The candidate opens a public job URL.
2. The candidate selects **Apply through chat** without creating an account.
3. Job Talk issues a guest token scoped to that job application.
4. The conversation asks for job-relevant skills, experience, location,
   availability, and concrete evidence.
5. The candidate reviews the structured application, provides contact details
   and consent, then submits it.
6. The candidate answers one short feedback question.

## Delivery order

| Order | Tickets | Reviewable result |
| --- | --- | --- |
| 1 | JT-006 to JT-011 | Private HTTPS staging deployment with backup and rollback |
| 2 | JT-018 and JT-019 | Approved recruiter can open seeded jobs; public job URLs render |
| 3 | JT-020 and JT-021 | Accountless candidate completes a securely scoped application |
| 4 | JT-022 | Recruiter compares strong and weak candidates in one format |
| 5 | JT-023 and critical JT-012 controls | Invited-user conversation quality and public safety gate pass |
| 6 | JT-024 | Usage, completion, comparison, return, and feedback can be measured |
| 7 | JT-016 | Slides, video, QR code, and feedback posts are ready |

## One-hour daily loop

Each session should leave one small result that can be reviewed:

1. Spend 5 minutes checking the live health, latest errors, and current metric counts.
2. Spend 45 minutes on the first unchecked acceptance item in TASKS.md.
3. Spend 10 minutes verifying the change, updating its ticket, and recording the
   next concrete step.

Visible candidate and recruiter blockers take priority over internal polish.

## Three-slide pitch

### Slide 1 - Problem

Recruiters still rely on CVs and rigid application forms. Candidates must be
good at presenting themselves on paper, while recruiters manually compare
inconsistent applications.

**What if candidates could simply explain what they can do?**

### Slide 2 - Live demo

A recruiter opens a role. A candidate opens that job without creating an
account and applies through conversation. Job Talk asks relevant follow-up
questions and turns the answers into structured skills, experience, and
evidence. The recruiter sees each candidate in the same format.

**Less form building, less CV screening, and clearer candidate evidence.**

### Slide 3 - Try it

Job Talk is live as an early experiment. Recruiters, hiring managers, and job
seekers are invited to try it and explain where it helps or fails.

- **Try Job Talk:** [APP_URL_AND_QR]
- **Contact:** [CONTACT_NAME_AND_EMAIL]

## End-to-end demo checklist

### Recruiter setup

- [ ] Sign in as the approved recruiter.
- [ ] Open a seeded job and show its requirements.
- [ ] Confirm its candidate list starts in a known state.

### Strong candidate

- [ ] Open the public job link in a fresh browser session.
- [ ] Start without an account.
- [ ] Describe relevant experience and answer follow-up questions.
- [ ] Review the extracted fields, add contact and consent, then submit.
- [ ] Confirm the recruiter sees the new structured candidate card.

### Weaker candidate

- [ ] Open the same job in another fresh browser session.
- [ ] Describe partial or unrelated experience.
- [ ] Submit the application.
- [ ] Confirm the recruiter view explains the lower criterion scores and gaps.

### Recruiter comparison

- [ ] Compare both candidates.
- [ ] Show skill and experience evidence for each score.
- [ ] Confirm contact details appear only after submission.
- [ ] Submit the recruiter usefulness answer.

## 30-to-60-second video

Suggested narration:

> CVs and application forms make candidates difficult to compare. I built
> Job Talk to test a different approach. Candidates open a real job and apply
> by describing their experience. Job Talk asks follow-up questions and turns
> the conversation into structured evidence. The recruiter can then compare
> candidates in the same format and understand each match. If you recruit
> people or are currently job hunting, try it and tell me what breaks.

Show the product for most of the video. Finish with the verified live URL, QR
code, creator name, and contact email.

## Distribution copy

Use the same call to action on LinkedIn and relevant Reddit communities:

> I am testing Job Talk with real users. If you recruit people or are currently
> applying for jobs, try it and tell me what helps, what is confusing, and what
> breaks.

Do not claim verified skills, guaranteed employment, unbiased hiring, or
production readiness.

## Metrics

| Metric | Definition |
| --- | --- |
| Unique visitors | First-party anonymous visitor IDs seen in the selected reporting period |
| Applications started | Guest application sessions successfully created |
| Applications completed | Structured applications explicitly submitted with consent |
| Recruiters trying comparison | Approved recruiters who open a comparison containing submitted candidates |
| Recruiter usefulness | Answer to: “Would this make early candidate review easier?” |
| Candidate feedback | Answer to: “Was this easier than a normal application form?” |
| Return use | The same anonymous visitor or recruiter returns within seven days |
| Direct requests | Manually recorded messages asking to use Job Talk with a real role |

Analytics events must not contain names, contact details, chat text, extracted
skills, or evidence. Direct messages remain a manual count.

## Review decision

Before publishing the launch posts, set a review date and record the evidence
required to continue, change direction, or stop. At review, inspect completion
drop-off, recruiter comparison use, direct feedback, repeat use, support burden,
privacy issues, and failures. Do not treat likes or post impressions as product
validation.
