# Privacy and safety operations

The public `/privacy` page is the user-facing summary. The operator must replace
`SUPPORT_EMAIL` with a monitored address before building the production frontend.
Use that inbox for privacy, abuse, access, and deletion reports.

## Operator application review

The approved recruiter whose email matches backend `ADMIN_EMAIL` can use
**All jobs** to review submitted application snapshots across recruiters. This
includes approved contact details, evidence and scores. Ordinary recruiters
retain access only to their own jobs' applicants; these views expose no full
candidate or recruiter chats. Job editing remains restricted to the job owner.
Submission consent and the public privacy page explain operator access. New
snapshots record `operator_access_disclosed`; earlier snapshots are not rewritten.
Keep the actual admin address in ignored `.env`, never in source or frontend
settings. See the README for approval, local login and disabling this access.

## Data retention

The candidate guest-data retention period is at most 30 days. Run the cleanup at
least daily on the VM to enforce it; `DEMO_DATA_RETENTION_DAYS` defaults to 30 and
cannot exceed 30:

```bash
docker compose --env-file .env.production -f production.docker-compose.yaml exec backend python -m app.data_retention purge-guests --confirm
```

The command removes the guest user, session, conversation, messages, application,
contact details, and structured evidence in one transaction. Backups expire under
the separate retention schedule in `docs/database-operations.md`.

## Individual deletion requests

A candidate with an active guest session can delete the submitted application
and all associated guest data from the submitted screen. The screen shows the
application reference.

After the session is gone, verify a request using the application reference and
the contact detail already stored on that application. Then run:

```bash
docker compose --env-file .env.production -f production.docker-compose.yaml exec backend python -m app.data_retention delete-application APPLICATION_ID --confirm
```

An unused recruiter access request can be removed with:

```bash
docker compose --env-file .env.production -f production.docker-compose.yaml exec backend python -m app.recruiters delete recruiter@company.com
```

That command refuses to delete a recruiter who has hiring records. Review and
export any records that must be retained, then handle the deletion as an operator
case rather than bypassing the guard.

## Abuse and logging

Nginx limits all API traffic to five requests per second per address and limits
POST and DELETE operations to 30 requests per minute with a small burst. The
backend also limits recruiter email codes per approved address. Keep the private
staging password enabled until the operator is ready to monitor the support inbox.

Application logs must contain operation names, record IDs when needed, status,
and exception types only. Do not add message text, names, contact details,
recruiter email addresses, session tokens, login codes, API keys, or request
bodies to logs. The current email and AI failure logs follow this rule.

Production disables FastAPI's OpenAPI document and schema routes. The backend
and database remain private behind Nginx.
