# JobTalk core MVP

## Goal

Build and validate one hiring loop:

> Recruiter defines an ideal candidate -> candidate applies through chat ->
> JobTalk scores the match -> recruiter compares the best candidates.

The release question is: **can one recruiter create a job, can one candidate
apply through chat, and can the recruiter compare candidates clearly?**

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
      "weight": 5,
      "description": "At least three years of practical plumbing work"
    },
    {
      "key": "geyser_installation",
      "label": "Geyser installation",
      "type": "skill",
      "target": true,
      "weight": 4,
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
  "weight": 5,
  "evidence": "Four years doing residential plumbing repairs",
  "reason": "Meets the three-year target"
}
```

## Recruiter flow

1. A manually approved recruiter signs in using an emailed code.
2. They describe a job in natural language.
3. JobTalk extracts measurable criteria, updates clarifications without
   duplicates, and asks only about important missing information.
4. The recruiter reviews each target, weight, and description, then publishes.

## Candidate flow

1. A candidate opens a published job without creating an account.
2. They provide name, email or phone, location, skills, and experience.
3. JobTalk maps each answer to the published criteria and asks only for material
   missing evidence.
4. The candidate reviews the structured application, gives consent, and submits.

## Matching and comparison

- Deterministic backend code compares candidate values with criterion targets.
- The overall score is the weighted mean of criterion scores.
- Recommendations include at most five jobs above the minimum useful threshold.
- A recruiter sees at most five leading candidates with contact details, score,
  evidence, and gaps.
- The parallel-axis view plots the ideal profile and those candidates using the
  same criteria. Evidence cards remain the readable explanation.

## Included scope

Recruiter login and manual approval; conversational job creation; structured
criteria; publishing; accountless job applications; contact details;
conversational evidence collection; explainable criterion scoring; top job
recommendations; top candidate comparison; parallel-axis comparison.

Everything else waits for evidence from real use.
