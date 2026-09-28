# Job Talk tickets

## Product aim

> Help people explain what they can do and help small employers describe what
> they need, then turn both conversations into transparent job matches.

The local hackathon demo is the current priority. Deployment follows in stages:
private VM demo, authenticated limited test, then public availability.

## Completed foundation

### JT-001 - Local conversation and matching flow

- [x] Save users, chats, messages, candidate profiles, job posts, and applications.
- [x] Support candidate and employer conversations.
- [x] Publish sufficiently described jobs and rank up to five matches.
- [x] Return criterion scores, weights, reasons, and the weighted overall score.

### JT-002 - Deterministic mock response generator

- [x] Put response generation behind one `generate_reply` function.
- [x] Remove the external AI dependency from the local demo path.
- [x] Echo a ten-character current-message preview in every mock reply.
- [x] Include current-chat history count and previous-user-message context.
- [x] Cover message and context behavior with backend tests.

### JT-003 - Stable send-message UI

- [x] Keep API response handling consistent after a message is sent.
- [x] Preserve the active chat and reload its list entry without blanking the UI.
- [x] Verify first and later messages in the browser.

### JT-004 - Clear chat participants and light company credit

- [x] Show the Roventics robot face for assistant messages and typing state.
- [x] Show a distinct person icon for user messages.
- [x] Keep the company credit small so Job Talk remains the product identity.

## P0 - Make the private VM demo safe and repeatable

### JT-005 - Real authentication and resource ownership

- [x] Replace email-only account opening with a bounded authentication flow.
- [x] Require an authenticated identity on every user, chat, job, recommendation,
  and application endpoint.
- [x] Enforce user ownership of chats and candidate applications in backend queries.
- [x] Let only the account that owns a job list its applicants.
- [x] Add tests proving one account cannot read or change another account's data.

**Done when:** knowing another person's email or record ID cannot expose or alter
their data.

**Status:** Complete. Accounts use Argon2 password hashes and opaque, expiring
database sessions. Thirteen backend tests and a live PostgreSQL smoke test verify
session lifecycle and cross-account boundaries (2026-09-28).

### JT-006 - Mark the current Compose stack as development

- [ ] Rename `docker-compose.yml` to `dev.docker-compose.yaml`.
- [ ] Keep development host ports bound to `127.0.0.1` by default.
- [ ] Update README commands and any scripts to use `docker compose -f
  dev.docker-compose.yaml ...` explicitly.
- [ ] Confirm the clean development stack starts, becomes healthy, and retains data.

### JT-007 - Production environment and secret contract

- [ ] Add a documented production environment template with placeholder values.
- [ ] Require strong database and authentication secrets at startup.
- [ ] Keep environment files, certificates, private keys, and backups out of Git.
- [ ] Validate the public origin, trusted hosts, and subdomain configuration.
- [ ] Document secret rotation without rebuilding frontend assets.

### JT-008 - Database migrations, backups, and recovery

- [ ] Replace startup-only table creation with versioned migrations.
- [ ] Add a VM backup command and retention policy for PostgreSQL data.
- [ ] Test restoring the database into a clean stack.
- [ ] Document rollback for both application image and database migration.

### JT-009 - Production Compose package

- [ ] Add an explicit production Compose file with pinned image versions.
- [ ] Keep PostgreSQL and FastAPI on the internal Compose network with `expose` only.
- [ ] Publish only reverse-proxy ports 80 and 443 on the VM.
- [ ] Add database-aware readiness checks, restart policies, resource limits, and
  persistent named volumes.
- [ ] Document build, start, health check, logs, upgrade, rollback, and shutdown.

### JT-010 - HTTPS ingress and private demo access

- [ ] Add a root `nginx/` directory for the public reverse proxy.
- [ ] Redirect HTTP to HTTPS and terminate TLS for the selected subdomain.
- [ ] Serve the frontend at `/` and proxy `/api/` to the private backend service.
- [ ] Forward trusted proxy headers, set conservative security headers, limit API
  requests, and cap request body size.
- [ ] Keep the first VM release behind proxy authentication or an IP allowlist
  until `JT-005` passes.
- [ ] Automate certificate issue and renewal, then test renewal without downtime.

### JT-011 - VM and subdomain deployment

- [ ] Choose the final subdomain and create its DNS record.
- [ ] Configure the VM firewall to allow SSH, HTTP, and HTTPS only as required.
- [ ] Deploy the production package and confirm only the reverse proxy is public.
- [ ] Verify TLS, private-demo access control, health checks, restart after reboot,
  logs, backups, and rollback from outside the VM network.

## P1 - Make the demo useful for invited testers

### JT-012 - Safety, privacy, and abuse controls

- [ ] Publish plain-language privacy, acceptable-use, and data-deletion information.
- [ ] Add rate limits for login, chat, publish, and apply operations.
- [ ] Limit field lengths and reject unsafe or malformed input consistently.
- [ ] Remove sensitive values from logs and define a short demo-data retention period.
- [ ] Disable or protect API documentation in the deployed environment.
- [ ] Add reporting and administrative removal paths before accepting unknown users.

### JT-013 - Replaceable real AI provider

- [ ] Define a typed provider interface around the existing response function.
- [ ] Add one explicitly configured provider, either an API or a local model.
- [ ] Keep the deterministic mock selectable for development and tests.
- [ ] Bound chat context by message count or tokens and keep it scoped to one chat.
- [ ] Handle timeouts, provider errors, unsafe output, and cost limits without losing
  the user's message.
- [ ] Add evaluation examples for candidate and employer conversations.

### JT-014 - Match-score visualization

- [ ] Confirm the criterion names and weights used in the hackathon story.
- [ ] Add an accessible multidimensional plot with a readable text equivalent.
- [ ] Show why a criterion scored high or low without overstating certainty.
- [ ] Test empty, partial, and perfect-match profiles on mobile and desktop.

### JT-015 - Usability and accessibility pass

- [ ] Verify keyboard navigation, visible focus, labels, contrast, and screen-reader names.
- [ ] Add a recoverable error state around the chat view.
- [ ] Test the full employer-to-candidate demo on a small phone and desktop browser.
- [ ] Add a short in-product note that matching is guidance and skills are unverified.

## P2 - Launch material

### JT-016 - Demo video and social launch kit

- [ ] Write a 60-to-90-second script: problem, employer flow, candidate flow,
  explainable match, application, and invitation to try the demo.
- [ ] Record a clean demo using fictional people and data.
- [ ] Generate a QR code from the live HTTPS URL and verify it on a second phone.
- [ ] End the video with the QR code, Job Talk URL, creator name, and chosen contact.
- [ ] Draft concise LinkedIn and Reddit posts with the hackathon context and a clear
  request for feedback.
- [ ] Avoid claims about verified skills, guaranteed work, or production readiness.

### JT-017 - Public pilot decision

- [ ] Review `JT-005`, `JT-006`, `JT-007`, `JT-008`, `JT-009`, `JT-010`,
  and `JT-012` evidence.
- [ ] Run a backup-and-restore drill and a cross-account authorization test.
- [ ] Decide whether to remain a private demo or open a small monitored pilot.
- [ ] Document monitoring, incident response, support contact, and shutdown criteria.
