# Persistent Data Model

Status: complete-product logical model. The current normalized foundation schema is implemented in dayframe/data/schema.sql and dayframe/data/store.py, migration version 4. Entity families listed here include future features; CURRENT_STATUS.md identifies what is delivered. The hub stores validated canonical entity revisions separately from client projections.

## Global conventions

Use stable globally unique IDs suitable for offline creation. Human ticket keys are display identifiers, not primary keys. Prefer a device-safe project key scheme until a hub can allocate canonical numbers; never derive identity from a mutable title.

Every synchronized entity carries workspace ID, creation/update metadata, revision information, originating device, and recoverable deletion metadata. Network ordering uses authoritative revisions/change sequences rather than trusting wall-clock timestamps.

Store instants in UTC with timezone context where relevant; date-only fields remain calendar dates. Durations use integer units. Money/billing is outside current scope.

## Entity families

| Entity | Important fields / relationships |
|---|---|
| Account | Stable ID, login identifier, display name, auth version, disabled state |
| Credential verifier | Password algorithm, salt, parameters, verifier; held only at intended authentication boundary |
| Device | ID, account, display name, registered/revoked times, last seen, credential/key reference |
| Workspace | ID, kind personal/team, owner, name |
| Membership | Account, workspace, role, active state; owner only initially if appropriate |
| Project | Workspace, name, key, description, archive state, defaults |
| Workflow status | Project/default workflow, stable internal code, display label, ordering |
| Ticket | Project, parent ticket, title/body, status, priority, component, milestone, due date, estimate, ordering |
| Label / TicketLabel | Scoped label definitions and many-to-many membership |
| ChecklistItem | Ticket, body, complete flag, ordering |
| TicketDependency | Prerequisite ticket, dependent ticket, relationship metadata |
| TicketRelation | Non-blocking related link |
| Goal / Milestone | Project, title, dates, hierarchy/relationships |
| MapSection | Project, name, rule expression, rule priority, display metadata |
| MapPlacement | Ticket, primary section, position, manual/automatic flag, layout revision |
| MapReference | Ticket, target section, display position; no copied ticket workflow |
| Event | Workspace, title, start/end or date, timezone, major flag, reminder preference |
| Recurrence / Exception | Rule, applicable timezone, occurrence overrides/completions |
| WorkBlock | Ticket, start/end, timezone, planning state; independent of due date |
| PriorityPin | Account/day or persistent focus policy, ticket, rank |
| CountdownPin | Account, major event/occurrence, rank |
| TimeEntry | Account, device, ticket optional, start/end, manual/session origin, correction metadata |
| TimerSession / Segment | Active/pause state, association, persisted segment timestamps |
| Note | Workspace, optional project/ticket link, title, Markdown body |
| Attachment | Workspace/object association, content hash, size, media type, managed file reference |
| RepoConnection | Project, provider/repo identity, credential reference; checkout paths device-local |
| RepoSnapshot | Branch, commit, release/check summary, observation time, remote/local source |
| Preference | Scope account/workspace/device, key, typed value |
| Activity | Actor/device, affected object, action, redacted field changes |
| OutboxOperation | Unique operation ID, entity, base revision, changed fields, pending/ack state |
| ChangeLog | Authoritative sequence, accepted operation, entity revision, tombstone/data reference |
| Conflict | Entity/field, base/local/remote versions, resolution state |
| SyncCursor | Device/workspace, last committed pull sequence |
| SchemaMigration | Applied version, timestamp, application compatibility |
| BackupManifest | Schema/app version, account/workspace IDs, attachments/checksums, creation time |

## Integrity and ownership

Enforce foreign keys and workspace consistency in the data layer. A ticket cannot refer to an unauthorized project's private data. Parent-ticket and dependency cycles are rejected. Map primary placement is unique per ticket/project; references have explicit separate identity.

Time entries require nonnegative durations and valid time intervals. Manual corrections preserve history. Handle deleted/archived ticket display without orphaning time totals.

Use join tables for sets and normalized relations. Do not make comma-separated label strings the authoritative model. JSON is suitable for validated optional settings/rule expressions, not a substitute for all relationships.

## Transactions

Ticket creation + default map placement/Unsorted + activity + outbox is one transaction. Status move + ordering + activity + outbox is one transaction. Section drag + field classification + placement + undo record is one transaction. Applying a sync batch and advancing its cursor is one transaction.

## Migrations

Version migrations sequentially, verify preconditions, back up before irreversible schema changes, and fail without partially updated state. Define compatible client/server protocol and schema ranges. A newer schema should produce an actionable message rather than silently opening with old code.

## Backup and restore

Use a supported database snapshot/backup facility, not a casual copy of a live database and missing WAL files. SQLite's [Backup API](https://www.sqlite.org/backup.html) is the reference for consistent snapshots.

Bundle a manifest and attachment inventory. A restore is a deliberate operation with a pre-restore backup, integrity checks, explicit account/device handling, and a sync-reconciliation policy. Restore must not casually replay stale data as new writes or erase newer hub data.

## Retention

Deletion uses tombstones for synchronization and recovery. Garbage collection waits for an explicit retention policy and safe device/cursor conditions. Removing a long-offline device from the supported sync set requires user action before pruning history it may need.


## Implemented work blocks in schema2

work_blocks stores account_id, id, ticket_id, date, start_time and end_time. Ticket ownership is validated locally and at the hub; blocks synchronize independently and cannot rewrite deadlines. Existing v1 databases migrate transactionally. The device-local .local-session.json is outside SQLite and backups; it contains account/device IDs only.


## Implemented 0.4 fields

Events add end_date, description, location, color, recurrence and archived. Empty end_date means start date; all-day end dates are inclusive. Recurrence currently accepts empty/yearly.
Tickets add parent_id; sections add parent_id and JSON predecessor_ids. Parent/dependency/sequence cycles and scope are checked locally/on hub. Classification and placement commit atomically. Notes remain stored with no current UI. Versions 1–3 migrate to 4. Roadmap activity/revision/attachment fields are not all implemented.
