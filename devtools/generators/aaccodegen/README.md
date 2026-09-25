# AAC Code Generation

Public AAC generator artifact shared by repositories that need canonical technology bindings.

It generates Python capability provider/caller bindings from canonical capability contracts and versioned Data Entity view/codec bindings from canonical JSON Schemas. Generated types retain canonical schema/contract identity, version, and source-resource provenance.

## Python CLI

Capability bindings:

```bash
aaccodegen capability path/to/capability.yml --schema-dir path/to/schemas --output generated.py
```

Data Entity bindings:

```bash
aaccodegen dataentity path/to/entity_1.json --schema-id example.entity --schema-version 1 --output generated.py
```
