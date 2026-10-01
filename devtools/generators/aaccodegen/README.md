# AAC Code Generation

Public AAC generator artifact shared by repositories that need canonical technology bindings.

It generates Python capability provider/caller bindings from canonical capability contracts and versioned Data Entity view/codec bindings from canonical JSON Schemas. Canonical JSON-definition parsing and normalization, generated DTO projection, naming, schema documentation, field documentation, and canonical source provenance are delegated to the general `pub.tool.General_generators.code.defscodegen` implementation. AAC-specific generation is limited to capability/provider/caller/failure bindings and Data Entity view/codec semantics layered on that normalized canonical-definition model.

Generated DTOs therefore expose the general `__canonical_source_id__`, `__canonical_source_version__`, and `__canonical_source_resource__` provenance attributes. AAC-specific generated capability interfaces continue to expose AAC capability provenance.

## Python CLI

Capability bindings:

```bash
aaccodegen capability path/to/capability.yml --schema-dir path/to/schemas --output generated.py
```

Data Entity bindings:

```bash
aaccodegen dataentity path/to/entity_1.json --schema-id example.entity --schema-version 1 --output generated.py
```
