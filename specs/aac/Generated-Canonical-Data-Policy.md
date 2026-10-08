# AAC canonical data implementation policy

Canonical data contracts are owned by the `jsondefs`, `yamldefs` and `xmldefs`
definition sources. For each logical type, the Modustro definition generator
owns its generated contract (`AIig…_N`), DTO (`AIcgd…_N`) and schema-defined
enums (`AIng…_N`). Consumers must use these generated types for data that
is defined by a canonical schema. `SCHEMA_FIELD_NAME__*` constants are the
source of wire field names; enum members/IDs supply wire enum values.

Handwritten source must implement behavior, adapters, policies, providers,
processing, or intentionally ephemeral data *without* a governing canonical
schema. Avoid maintaining alternate handwritten dataclasses, mapping codecs,
or enum value lists for schema-defined data. Keep generated `.gen` sources
out of source control; generate them through the standard Gradle/Modustro
Codegen tasks. CoreIntf may depend on generated interfaces, while CoreImpl
and components with a declared CoreImpl dependency may instantiate generated
DTOs.

## Migration tracking (2026-10-08)

`ObservationInput` and `ObservationOutput` have been migrated to generated
contracts and DTOs. The latter migration is exercised using the actual
`AIcSchemaObjectBindingsGenerator`, not a manually maintained generated file.

A source inventory also found **21 further handwritten Python classes** whose
names match canonical JSON definitions. These still require semantic review
before replacement: some carry domain behavior, legacy default values,
non-schema attributes, or existing public APIs. Matching file names alone
is not sufficient justification for mechanical replacement.

Remaining candidates:

- `capability-contract`, `capability-group`, `catalog-bootstrap`
- `component-descriptor`, `configuration-bootstrap`, `configuration-persisted-payload`, `configuration-profile`
- `data-entity-envelope`, `display-content`, `entitlement-bootstrap`, `entitlement-document`, `entitlement-issuing-request`
- `operation-failure`, `operation-interaction-caller-to-provider-message`, `operation-interaction-event`, `operation-interaction-provider-to-caller-message`
- `package-bootstrap`, `provider-instance`, `security-bootstrap`
- `workspace-component-lock`, `workspace-component-requirements`

These candidates are not yet migrated. A repository-wide equivalence test
must be introduced before claiming full removal of handwritten schema DTOs.
