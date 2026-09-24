# YAML File-System Data Entity Storage (`yamlfsdes`)

`yamlfsdes` is the reference YAML/file-system implementation of the generic AAC Data Entity storage capabilities. It is intended for human-inspectable, VCS-friendly or otherwise file-oriented Data Entity stores such as product configuration repositories.

The component contains one capability-provider definition, `yamlfsdes`. A configured provider instance points at one `root_directory` and implements:

- `_AAC.data-entity.get-record/1`
- `_AAC.data-entity.query-records/1`
- `_AAC.data-entity.apply-direct-record-changes/1`
- `_AAC.data-entity.inspect-storage-support/1`
- `_AAC.data-entity.ensure-storage-support/1`
- `_AAC.data-entity.retire-storage-support/1`
- `_AAC.data-entity.create-storage-backup/1`
- `_AAC.data-entity.inspect-storage-backup/1`
- `_AAC.data-entity.restore-storage-backup/1`

Provider-instance `READ_ONLY` / `READ_WRITE` policy remains Core-owned. The same component/provider definition can therefore back multiple independently configured roots with different access modes. Creating and inspecting a backup are non-mutating operations; restore requires write access.

## Physical layout

The authoritative layout is deliberately transparent:

```text
<root_directory>/
  data/
    <schema-id>/
      <stored-schema-version>/
        .schema.yml
        <entity-uid>.yml
  journal/
    record-changes/
      <transaction-id>/...
    restore/
      <transaction-id>/...
  .yamlfsdes/
    storage.lock
    ...future rebuildable indexes/cache...
```

`data/` is authoritative durable state and is the part that must survive backup, copy and disaster recovery. `journal/` is crash-critical while non-empty. `.yamlfsdes/` contains only rebuildable implementation/runtime state: deleting it while the store is quiescent must not remove authoritative records, schema meaning or committed consistency.

A record is self-describing even though its identity and stored schema version are also encoded in the path:

```yaml
uid: 8b42a7fe-80bc-4c5b-b7f0-c6b714c04921
schema_id: _AO.entity.site
schema_version: 2
record_revision: 7
state: ACTIVE
payload:
  name: Main site
```

The provider verifies that `uid`, `schema_id` and `schema_version` inside the file agree with the physical path. A logical `(schema_id, uid)` may occur in only one stored-version directory at a time. A duplicate UID across versions is treated as storage corruption rather than silently choosing one copy.

`schema_id` and `uid` must use portable filesystem identifier characters `[A-Za-z0-9._-]` and start with an alphanumeric character or underscore. This keeps paths readable while preventing traversal/escaping ambiguities.

## Storage-support metadata

`ensure-storage-support` creates or reconciles the corresponding schema/version directory and its durable metadata file:

```text
<root_directory>/data/<schema-id>/<schema-version>/.schema.yml
```

`.schema.yml` contains the complete canonical JSON Schema, its `canonical_digest`, normalized Data Entity reference definitions and support status (`READY` / `RETIRED`). Keeping this metadata beside the records makes the authoritative data tree self-describing and independent of rebuildable `.yamlfsdes/` state.

Re-ensuring the same canonical definition is idempotent. A different canonical schema under the same `(schema_id, schema_version)` is reported as `INCOMPATIBLE`. If record files already exist but `.schema.yml` is missing, the storage support is also `INCOMPATIBLE`; `ensure-storage-support` must not silently assign a newly supplied schema to pre-existing records.

`retire-storage-support` changes only the status in `.schema.yml`. It never removes record files or the schema/version directory. Existing records remain readable, while new create/replace writes into a retired stored version are refused. A later compatible `ensure-storage-support` may reactivate the version.

## Revisions and changesets

The backend uses positive integer `record_revision` values:

- create starts at revision `1`;
- replace increments the current revision;
- replace/delete enforce `expected_record_revision` before any change is committed.

`APPLY_DIRECT_RECORD_CHANGES` is one provider transaction domain. The provider validates the complete changeset before mutation and rejects duplicate logical record identities inside one changeset.

A replace may change the physical stored schema version. In that case the record is written to the target version directory and the old version file is removed as part of the same provider transaction.

## Locking, atomicity and crash recovery

All operations over one root are serialized with a provider-wide filesystem lock. This favors simple and strong semantics over high write throughput, which is appropriate for configuration-oriented stores.

Multi-record changes use a recoverable journal under:

```text
<root_directory>/journal/record-changes/<transaction-id>/
```

The provider stages complete replacement files, durably marks the transaction `COMMITTING`, and then applies idempotent filesystem operations. A crash during commit leaves enough staged state to complete the commit before the next provider operation. Transactions that never reached `COMMITTING` are discarded during recovery.

Atomicity is defined at the provider API boundary: normal readers/writers through the same YAMLFS DES root never observe a partially committed changeset. Direct out-of-band filesystem access while a provider transaction is in progress is outside the AAC storage contract.

Restore transactions use the same principle under `journal/restore/`. Recovery completes an interrupted committed replacement before normal access resumes.

## Query behavior

The implementation supports the complete portable v1 query surface:

- `schema_id`;
- optional `stored_schema_version_filter`, primarily useful for migration/development/administration tooling;
- `ACTIVE` / `TOMBSTONE` state filters;
- explicit UIDs;
- canonical Data Entity reference selectors using reference metadata recorded by `ensure-storage-support`;
- `ALL` / `ANY` reference matching;
- `UID_ASC` / `UID_DESC` ordering;
- bounded pages with opaque continuation tokens.

No payload-specific query language or provider-private query API is introduced. This first implementation scans the relevant schema/version directories. Provider-private indexes may be added later under `.yamlfsdes/` without changing the capability contract or authoritative physical record layout.

## Backup creation

`create-storage-backup` receives an explicit `backup_file` path and writes a ZIP atomically. The ZIP contains `backup.yml` plus the complete `data/...` hierarchy, including every `.schema.yml` and record file. It deliberately excludes `journal/` and `.yamlfsdes/`.

```text
backup.zip
  backup.yml
  data/
    <schema-id>/
      <schema-version>/
        .schema.yml
        <entity-uid>.yml
```

`backup.yml` records the backup/provider/layout format, creation time, schema-version count, record count and every archived file with its exact size and SHA-256 digest.

The provider holds the storage lock while constructing the ZIP. The result therefore represents one committed provider state even on filesystems without native snapshot support. A future backend may implement the same capability with database/native snapshots while preserving the generic backup semantics.

## Backup inspection

`inspect-storage-backup` is non-mutating and accepts:

```yaml
backup_file: /path/to/backup.zip
validation_level: INTEGRITY   # optional; INTEGRITY is the default
```

Two validation levels are defined:

### `INTEGRITY`

This is the cheaper container/integrity check. It verifies that:

- the ZIP is readable;
- `backup.yml` exists and has a supported backup/provider/layout format;
- every declared entry has a safe `data/...` path;
- every declared entry exists with the declared size and SHA-256;
- the ZIP contains no undeclared payload files.

This necessarily reads the archived bytes to compute hashes, but it does not parse and semantically validate every schema and record.

### `FULL`

`FULL` performs the complete `INTEGRITY` check and additionally verifies that the backup represents a usable YAMLFS DES data tree:

- each `.schema.yml` is valid provider metadata and its identity matches its path;
- each canonical schema matches its `canonical_digest` and is a valid JSON Schema Draft 2020-12 schema;
- support status and reference metadata are structurally valid;
- every record has the exact expected record envelope fields;
- record `schema_id`, `schema_version` and `uid` match the archive path;
- `record_revision` and state are valid;
- every record has matching `.schema.yml` metadata;
- every record payload validates against its stored canonical schema;
- one logical `(schema_id, uid)` does not occur in several stored-version directories;
- manifest record/schema counts match the actual backup contents.

`FULL` validation is intentionally more expensive. For large backups it is an O(total backup content) operation with additional YAML parsing and JSON Schema validation CPU cost. It is intended for high-confidence validation rather than cheap UI probing.

Both levels can publish generic AAC Operation Interaction progress events, and callers may adjust the reporting interval or request cooperative cancellation through the invocation interaction channel.

## Restore

`restore-storage-backup` always performs `FULL` validation before making the backup authoritative. A checksum-correct ZIP containing semantically invalid schemas or records is therefore not restorable merely because its container integrity is intact.

Restore supports:

- `EMPTY_ONLY` (default): refuse restore when the target `data/` tree already contains persistent files;
- `REPLACE_ALL`: replace the complete target `data/` tree with the backup.

Restore is journaled under `journal/restore/`. `REPLACE_ALL` never merges old and restored records: the old `data/` tree is moved aside inside the restore journal, the staged backup tree becomes the new `data/`, and crash recovery finishes the swap before normal access resumes.

Backup/restore is physical provider disaster recovery, not logical cross-provider Data Entity export/import. A `yamlfsdes` ZIP is intentionally provider-format-specific and may be restored into another compatible `yamlfsdes` provider instance; it is not bound to the source provider-instance identity.

## Operation Interaction

Longer YAMLFS DES operations use the generic AAC Operation Interaction channel rather than provider-specific UI callbacks. Backup creation, backup inspection, restore and direct changes may emit structured progress phases and cooperate with cancellation. The provider also honors the caller-selected reporting interval for progress event throttling.

`FOREGROUND` versus `BACKGROUND` is a host/user interaction mode, not a different provider execution mode. Moving an operation to background does not stop progress reporting or detach the execution; the host may continue showing it in a task/status area and may later bring the same running operation back to foreground presentation.
