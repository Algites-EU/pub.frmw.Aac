# AAC Simple Audit

Reference `_AAC.capability.observation/1` provider and AAC conformance fixture.

Public import namespace: `eu.algites.frmw.aac.observation.simpleaudit`.

The provider depends only on `coreintf` and writes normalized observation events to standard output or a configured file. Its descriptor selects the persistent `PROCESS` runtime profile, so every Core-managed provider instance owns a separate child process, configuration and lifecycle.

The component descriptor and configuration schema also demonstrate localization-ready `name` / `description` metadata and schema-driven AAC UI presentation metadata.
