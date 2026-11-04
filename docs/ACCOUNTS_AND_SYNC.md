# Accounts, Local Sync, and Recovery

Status: agreed design with an initial working account/sync implementation. CURRENT_STATUS.md distinguishes implemented protocol features from hardening and UX work that remains.

## Objectives

The same account can work on Windows and Linux, access its own projects and planning data, keep editing while disconnected, and synchronize reliably when a configured local connection is available.

Account identity, local unlock, device trust, workspace access, data encryption, and backups are separate responsibilities.

## Recommended topology

Each device owns a local database. An optional LAN hub accepts authenticated changes and serves an ordered change feed. An always-on Linux machine is a convenient proposed host if the user has one; Windows hosting must remain possible if selected.

No always-on hub means synchronization occurs only when a chosen host is reachable, or a separate peer-to-peer architecture must be selected. Do not describe direct peer discovery/multi-master sync as a trivial toggle.

## Identity and device registration

Proposed starting model: private accounts, no public registration, no email provider dependency. Initial account creation is an explicit local setup or controlled hub action. Offline-first setup needs a documented way to adopt/pair the local identity with the hub without duplicating the account.

Hash passwords using a maintained memory-hard password hashing implementation with unique random salts and recorded parameters. Never store or log plaintext passwords. Do not sync passwords as ordinary ticket-data changes.

Register each device through an authenticated pairing flow with a visible device name and revocation support. Keep refresh/device credentials in OS credential storage. Local app login uses a salted password verifier; database protection relies on OS/disk encryption, as selected by the owner. Revocation prevents further hub access; a disconnected device's existing local copy cannot be remotely erased merely by revoking a token.

## Transport

Use authenticated encrypted transport with explicit pairing/trust of the hub certificate or an equivalent documented secure channel. Do not send reusable passwords across an unencrypted LAN connection. Restrict a first hub to local binding until the user enables LAN access. Do not change system firewall/router rules automatically.

Connection settings include enable/disable sync, hub address, device identity, connection state, last successful sync, pending changes, conflict count, manual Sync, retry, and disconnect/revoke actions.

Automatic discovery can follow manual hub configuration; discovery alone does not establish identity or trust.

## Change protocol

1. A local edit validates domain rules and writes domain data plus an outbox operation atomically.
2. The operation has a globally unique ID, authorized workspace/entity identity, base revision, changed fields, and device identity.
3. The hub authenticates, authorizes, validates schema and domain constraints, and deduplicates the operation ID.
4. Compatible updates commit with an authoritative entity revision and global/workspace change sequence.
5. The client pulls changes after a durable cursor in bounded batches.
6. Applying changes and advancing the cursor occur in one local transaction.
7. Retry duplicate/incomplete network requests safely; acknowledge only committed operations.

Client timestamps are useful history, not the sole conflict winner. Prevent the client's own pulled changes from becoming a fresh endless outbox loop. Bound payloads and use protocol-version negotiation.

## Conflict proposal

Confirmed: merge changes to independent fields. If both sides changed the same scalar field from the same base, preserve base/local/remote and ask for resolution. Notes/descriptions preserve both versions rather than silently concatenating text. Set membership and relationships need explicit add/remove semantics, not array replacement.

Map coordinates and classification fields have different meaning. A layout conflict must not accidentally overwrite ticket labels. Keep preserved manual placement and automatic rule changes explicit.

Delete-versus-edit conflicts require recovery choice. The interface should offer use local, use remote, or manual merged result, with provenance and Undo/recovery where meaningful.

## Timers across devices

Confirmed target: one active timer per account while connected, coordinated through the hub. Offline devices can temporarily diverge; flag overlapping entries on reconnection without silently discarding or double-counting them.

Preserve original timestamps and device IDs. Never rely on local wall-clock ordering alone to prove which timer should win. Starting a timer elsewhere should be a deliberate state transition and visible on connected peers.

## Attachments and preferences

Sync attachment metadata with domain records and transfer bytes through a bounded content-hash protocol. Partial transfers remain incomplete and retryable, not fake-success attachments.

Default to synchronizing project/ticket/event/note data and selected account preferences. Keep window bounds, machine paths, checkout locations, credentials, and display-dependent sizes device-local. Appearance preference scope is configurable.

## Failure and recovery cases

Must cover unreachable hub, wrong credentials, revoked device, expired token, schema mismatch, duplicate operation, interrupted push, interrupted pull, missing attachment, disk full, conflict, clock skew, old restored backup, and a device returning after extended offline use.

Provide readable errors and a safe retry path. Do not turn off the ability to read/edit local work merely because the hub is unavailable.

## Backup relationship

Sync is not a backup: deletion and bad edits can synchronize. Keep versioned local backups and recoverable history separately. A hub backup must include identity/authorization data and managed attachments when attachment support is added. Test restore with two devices before calling the sync feature ready.

## Operational readiness

The owner confirmed a Linux LAN hub, private account/device model, merge/review conflicts, one-account timer target, and OS/disk encryption. The first implementation includes HTTPS with normal trust or explicit certificate fingerprint pinning, account publication through a private setup token, pairing, and conflict review. Password-reset/recovery UX, session expiry/rotation, stronger timer coordination, attachment transfer, and restore reconciliation remain hardening work; do not treat this foundation as a fully hardened multi-user service.


## Owner login correction in0.3

Local passwords have no minimum or complexity rule; short and blank values are permitted. Existing verifiers remain compatible. Account creation/login remembers a trusted account/device marker outside the database and outbox. App startup restores it until Options → Log out removes it. Imports never import another profile's remembered unlock. This preference relies on access to the OS profile.

Changing the local password is an authenticated setting and does not change the hub password. The block entity for actual ticket work sessions requires the updated0.3 hub and clients.

## Native 0.4 compatibility

Update the Python hub/all clients to 0.4 for event/map fields. Versions 1–3 migrate to schema4; imports migrate only the copy. Older apps cannot open the upgraded database; preserve earlier backups. Notes data remains with its UI hidden. No service/firewall/network setup is installed.
