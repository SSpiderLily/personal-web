# Production integration of the personal site redesign

User authorized committing, pushing, merging, and opening the production admin page after completion.
Base: latest origin/main. Preserve the complete existing auth, projects, tools, statistics, uploads, deployment, backup and recovery behavior.

- Port the approved Home / Works / Notes / About visual design; keep database-backed projects and tool visibility and visit collection.
- Add optional about_content to the existing profile API and original admin ProfilePanel. Keep legacy seven-field payloads valid and existing avatars, contacts, and social links intact.
- Append immutable migration 004_about_content, matching the already-applied development migration. Never copy development accounts/passwords into production.
- Run complete project checks and disposable PostgreSQL tests; request independent review before merging.
- Push a feature branch, create PR, await CI, merge with checked SHA, verify production deployment, and open the existing production admin access URL.
