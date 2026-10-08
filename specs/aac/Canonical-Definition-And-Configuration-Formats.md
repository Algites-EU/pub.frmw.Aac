# AAC canonical definition and configuration formats

## Canonical definition roots

The AAC source repository retains 56 canonical schema contracts: 54 in `aac/coreintf`
and two owned by the `yamlfsdes` and `simpleaudit` components. Every contract is
represented at an equivalent artifact-local logical path in three source roots:

- `src/product/jsondefs/<path>/<name>_N.jsondef.schema.json` — original JSON Schema.
- `src/product/yamldefs/<path>/<name>_N.yamldef.schema.json` — JSON Schema for YAML documents;
  the same JSON Schema constraints, logical schema identifier/version, names, descriptions,
  references, and field semantics as `jsondefs`. `$id` and file references point to the
  corresponding `yamldefs` resources.
- `src/product/xmldefs/<path>/<name>_N.xsd` — XSD 1.0 projection of the same named data
  objects, fields, primitive types, nested objects, arrays, optionality and documentation.

**Important:** JSON Schema and XSD 1.0 are not expressively equivalent. The generated XSD
preserves the entire original JSON Schema in its `xs:annotation/xs:appinfo` as
`aac:canonicalJsonSchema`. Conditions (`if`/`then`), `oneOf`, `anyOf`, some regexes,
`uniqueItems`, nullable unions, and maps with arbitrary keys cannot all be enforced
by plain XSD 1.0. XSD structural validation is useful but does **not** establish full
JSON Schema semantic validation. A full three-way semantic validator or a governed
XSD 1.1 model would require separate design and implementation. No claim of identical
validation strength is made.

There are deliberately **no `.meta.yml` sidecars in the newly created `yamldefs`
and `xmldefs` roots**. This is intentional for testing the public Modustro Builder
sidecar generator. Existing `jsondefs` sidecars are unchanged.

## Configuration documents

Concrete examples are stored exclusively under `src/product/config/`, not any
canonical `*defs` root. All 19 source documents have these forms:

| Document | Schema reference | Representation |
|---|---|---|
| `*.yml` | `https://defs.dev.algites.eu/api/yamldefs/...yamldef.schema.json` | YAML mapping/list/scalars |
| `*.json` | `https://defs.dev.algites.eu/api/jsondefs/...jsondef.schema.json` | Equivalent JSON mapping/list/scalars |
| `*.xml` | `https://defs.dev.algites.eu/api/xmldefs/...xsd` | XML representation valid against its XSD |

YAML source headers (the `yaml-language-server` comment, documentation `$schema`
comment, and actual `$schema` property) point to `yamldefs`; JSON configurations
reference `jsondefs`. In both component descriptors, `ConfigurationSchema.Resource`
points to the definition with the extension appropriate to the serialization.

XML representation rules: document root is the PascalCase schema name and uses
the schema's own namespace; `xsi:schemaLocation` identifies the XSD; a `schemaRef`
attribute represents JSON/YAML `$schema`; each object property is a child element;
an array is represented as the property element with repeated `Item` elements;
unknown-key maps use `MapEntry key="…"` with `Value` containing JSON-encoded data.
These XML-specific conventions matter to any future runtime serializer or loader.

**Runtime limitation:** Creating equivalent files does not automatically make every
existing AAC runtime loader read every serialization. Some current consumers still
expect `component.yml` or use YAML-only parsing. A separate runtime codec/loader
integration is needed before changing those entrypoints or package manifests to
prefer JSON/XML. Do not remove the existing YAML config files.

## Regeneration and validation

From the repository root:

```bash
python3 devtools/generate_schema_format_parity.py
python3 devtools/test_schema_format_parity.py
```

The generator is deterministic and idempotent, and does not generate sidecars.
It requires `PyYAML` and `lxml`; validation tests also require `jsonschema`.
Changes to original JSON schemas should be regenerated before the new definitions
are published. The schema tests verify YAML/JSON data equivalence, all XSDs,
and XML configuration validation against generated XSDs.

To test the new Modustro sidecar generator in AAC:

```bash
./gradlew generateMissingModustroSchemaSidecars --no-configuration-cache

git status --short
```

This populates missing `*.meta.yml` for canonical YAML/XML (and any other missing
canonical definitions) **after** the checkouts are deployed with a `pub.gov.Algites`
revision containing that task. The generated sidecars must be reviewed and committed.

When investigating `Unsupported file '<name>.yml' in canonical yamldefs root`, check
that the workflow built the updated AAC commit: concrete `.yml` files belong under
`src/product/config`. The current source tree contains none under `yamldefs`.
