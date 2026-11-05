# SpendWise security remediation — 5 November 2026

## Verified findings and local fixes

`.env` and `db.sqlite3` are ignored and absent from the current Git index, but both occur in historical commits. `.envy` was still tracked with a local database URL containing a password; its removal from the index is now staged and it is ignored. Local files and user data have been preserved.

The local `.env` now has DEBUG=False, a new random Django key and no SMTP password. File permissions are 0600. The old credentials remain compromised until revoked at their providers. Local SMTP sending is disabled until a replacement is supplied. Production secrets have not been changed.

OTP issuance uses the secrets module and Django password hashing. The schema migration invalidates all preexisting verification/reset codes; users must request new codes. Four-digit inputs are retained for compatibility, with database-backed limits shared across sessions and application workers: five verification attempts per account and fifty per connecting IP per 15-minute window; three sends per account and ten per connecting IP per window. Resending does not clear attempt limits. Fixed windows can permit two adjacent windows' limits near a boundary. IP limits use REMOTE_ADDR, never an untrusted forwarded header; configure the trusted ingress to preserve client IPs, otherwise proxy clients share an IP limit.

Reset requests use identical redirects and visible messages for existing and nonexistent accounts, including email delivery failures. Delivery is still synchronous for existing accounts: response timing can still reveal account existence. Move reset delivery into a durable background queue before claiming timing-resistant enumeration protection.

Reset codes are consumed after successful verification; reset authorization expires after ten minutes and is cleared on a new request or verification attempt. API exception responses are generic, with exceptions logged server-side. Production email configuration no longer falls back to printing OTP email bodies to stdout when SMTP credentials are missing; delivery will fail until valid SMTP settings are supplied.

Avatars are restricted to verified JPEG/PNG/WebP images up to 2 MB and 16 million pixels. Profile uploads are re-encoded as JPEG, resized to 1024 pixels, stripped of supplied metadata/trailing content, and randomly named. Model validators also cover admin forms. Existing uploaded files have not been audited.

Django no longer serves production media by default. Configure `/media/` through a web server/CDN or configure Django's STORAGES with an object storage backend before deploying. Existing avatars will be unavailable until this is done. SERVE_MEDIA_WITH_DJANGO=True is an explicit temporary compatibility option, not a recommended production setting. Use a separate origin, correct image content types, and X-Content-Type-Options: nosniff on the media service.

## Required external actions before deployment

1. Revoke the exposed Gmail app password in Google Account security settings, create a replacement if SMTP remains needed, and install it in the deployment secret manager. Review sent mail/account activity. Removing a local value does not revoke access.
2. Generate a fresh production SECRET_KEY in the secret manager, restart all application workers and remove the exposed key from any fallback list. The local replacement is not a production rotation. Account for session/logout and token invalidation. Production now refuses short or known development-prefixed keys.
3. Review and replace any reused database credential from `.envy`; its URL targets localhost, so no production database compromise has been verified.
4. Confirm DEBUG=False on each deployed service. Apply migration 0040 (`python manage.py migrate`); active OTPs will be invalidated. Configure production media and exercise signup, reset, upload, SMTP and HTTPS on staging.
5. Treat historical database contents as exposed: assess affected records, password resets, session revocation and any incident notifications with the responsible owner. A historical database was confirmed in Git; current user counts/emails were deliberately not printed or exported.

## Coordinated history cleanup (not executed)

Revocation comes first. Rewriting shared history changes commit IDs and requires collaborator coordination, branch-protection handling and cleanup of old clones. Preserve uncommitted work, including these fixes, before any rewrite.

After committing the fixes, freeze writes and use a fresh isolated clone with git-filter-repo >=2.47. Fetch all affected refs, record remote heads and audit renamed/copied files and other credential-bearing files. The core local filtering command is:

```sh
git filter-repo --sensitive-data-removal --invert-paths --path .env --path .envy --path db.sqlite3
```

Inspect changed refs and verify that all intended branches/tags are clean. Review any additional secret occurrences with redacted output. Publishing requires a coordinated, reviewed force update of the affected remote refs; this change set does not perform it. After publishing, collaborators must re-clone or clean their histories to avoid reintroducing exposed commits. Forks, cached commit views and pull-request references may also need owner/GitHub Support cleanup.

Reference: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
