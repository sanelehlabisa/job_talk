# Privacy and safety operations

The public `/privacy` page is the user-facing summary. The operator must replace
`SUPPORT_EMAIL` with a monitored address before building the production frontend.
Use that inbox for privacy, abuse, access, and deletion reports.

## API access boundary

Production is planned for `https://jobtalk.roventics.com`. Only Nginx exposes
host ports 80/443. FastAPI and PostgreSQL have no public host ports; `/api/`
still reaches the backend through HTTPS and enforces application authentication.

The production proxy also rejects foreign browser origins and Fetch Metadata
sites, including sibling subdomains. This prevents other websites using normal
browser requests against the app. Outside programs can copy browser headers, so
this is not proof that a request came from our frontend. Public APIs remain
public, and every private operation still requires an authorized session.

Private routes require an expiring `Authorization: Bearer <token>` session.
The backend stores a token hash, rejects unknown/expired tokens, and revokes the
session immediately on successful logout. Tokens otherwise expire after the
configured `AUTH_SESSION_HOURS` (24 by default). Other active sessions are separate.
If the logout request fails, the UI keeps the session and asks the user to retry;
an already expired/revoked token is safely cleared locally. A login code is
short-lived and single-use, not an API token. Code consumption and new session
creation share one transaction; simultaneous requests cannot redeem it twice,
and wrong guesses increment the attempt count atomically.
Approved recruiters access their own hiring chats/jobs and submitted applicants;
the approved configured admin can manage all hiring chats and applications.
Guest sessions access only their own candidate chat and application. Recruiter
and admin applicant views expose submitted snapshots, not full candidate chats.

Job listings, guest-session creation, code requests/verification, health and
anonymous visit counting are intentionally public endpoints. They do not list
candidate chats or contact details. The staging HTTP Basic password applies to
the webpage; API authorization remains the backend's responsibility.

**Verified 2026-10-04 (JT-076):** Every private route was exercised with missing,
forged, expired and logged-out tokens and returned 401. Approval revocation,
guest posting rejection, ownership, concurrent code redemption and wrong guesses
passed in disposable SQLite. The frontend build and real local email-code login
plus browser offline logout, retry and token replay passed. These checks are part
of 84 focused checks passing across runs, including production settings.
JT-070 also checked anonymous rejection and valid Bearer access through the
production proxy locally. This is scoped engineering verification; the live VM
configuration and real-domain access still need testing before inviting users.

Repeat the browser logout check locally with an approved test recruiter:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/local-signoff.ps1 -LogoutOnly -RecruiterEmail recruiter@example.com
```

## Operator application review

The approved recruiter whose email matches backend `ADMIN_EMAIL` uses the shared
recruiter workspace to view all job-creation chats, edit drafts, publish and close
jobs, and review submitted applications across recruiters. Submitted snapshots
include approved contact details, evidence and scores. Ordinary recruiters see
only their own chats and applicants. Full candidate chats remain private to
their scoped guest session. Admin edits do not transfer job ownership.
Submission consent and the public privacy page explain operator access. New
snapshots record `operator_access_disclosed`; earlier snapshots are not rewritten.
Keep the actual admin address in ignored `.env`, never in source or frontend
settings. See the README for approval, local login and disabling this access.

For vacancies marked **Added by Job Talk**, consent records operator access and
`external_employer_sharing_authorized: false`. An employer named in a public
advert has no access to the submitted application. Before sharing identifying
details, request separate candidate permission and manually approve the recruiter.
There is no automated transfer, outreach or export. Until then, use only the
aggregate interest summary, avoiding screenshots of private candidate cards.
Original pasted vacancy text remains private in the owner's draft; public
responses contain only its source URL, advertised employer and date checked.

## Data retention

The candidate guest-data retention period is at most 30 days. Run the cleanup at
least daily on the VM to enforce it; `DEMO_DATA_RETENTION_DAYS` defaults to 30 and
cannot exceed 30:

```bash
docker compose --env-file .env.production -f prod.docker-compose.yaml exec backend python -m app.data_retention purge-guests --confirm
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
docker compose --env-file .env.production -f prod.docker-compose.yaml exec backend python -m app.data_retention delete-application APPLICATION_ID --confirm
```

An unused recruiter access request can be removed with:

```bash
docker compose --env-file .env.production -f prod.docker-compose.yaml exec backend python -m app.recruiters delete recruiter@company.com
```

That command refuses to delete a recruiter who has hiring records. Review and
export any records that must be retained, then handle the deletion as an operator
case rather than bypassing the guard.

## Abuse and logging

Nginx limits all API traffic to five requests per second per address (burst 15),
writes to 30 requests per minute (burst 10), and guest/login requests to ten per
minute (burst 5). It also caps concurrent API requests at 20 per address and text
bodies at 128 KiB, rejects unexpected hosts/unused methods, and bounds inactive
requests. The backend also limits recruiter email codes per approved address.
HTTPS includes a Content Security Policy, HSTS and framing restrictions; API
responses are not cached. Proxy access logs exclude query strings and credentials.
See [production request policies and their isolated check](production-operations.md#proxy-request-policies-jt-077).
Keep the staging webpage password enabled until the operator is ready to monitor
the support inbox.

Application logs must contain operation names, record IDs when needed, status,
and exception types only. Do not add message text, names, contact details,
recruiter email addresses, session tokens, login codes, API keys, or request
bodies to logs. The current email and AI failure logs follow this rule.

Production disables FastAPI's OpenAPI document and schema routes. The backend
and database remain private behind Nginx.
