# Generated source conventions

These rules apply to every technology with an interface or abstract-class concept.

* Canonical schema files are authored and versioned in their existing package paths.
* Only the shared generator writes `.gen` or `.extgen` trees. Their contents are
  disposable build outputs, never authored source, never committed to Git, and
  excluded from repository source ZIPs.
* Generate one contract per schema object (including nested objects), and one
  concrete implementation of that contract. Scalar roots and enums retain their
  canonical representation. JSON/YAML representations of the same logical type
  are merged only when their normalized contracts are compatible.
* Every generated type follows its owning schema's package path. Never collect
  unrelated schemas in a `schemafields` package. Nested objects keep their
  owning file's package; their names include the owning schema and object path.
* The interface artifact owns abstract contracts, annotated attributes,
  `SCHEMA_FIELD_NAME__*` constants, canonical documentation and enum declarations.
  It has no dependency on the implementation artifact. The implementation
  artifact owns concrete immutable dataclasses or Java records implementing
  those contracts, and depends on the interface artifact.
* Handwritten source imports generated contracts/constants/enums, rather than
  duplicating their wire names. Generated code is not manually patched.
* A clean checkout generates before compilation, packaging, staging for Python
  imports, or testing. GitHub executes the same Gradle generation dependency.
  Local AAC `test_all.py` and `build_all.py` also invoke that Gradle task first.

The current naming profile uses `AIig...`/`aiig_...` for generated interfaces,
`AIcgd...`/`aicgd_...` for concrete generated data types, and `AIng...` for enums.
Python contracts use `ABC`, annotations and an abstract `to_mapping()` method;
concrete dataclasses implement it. Java records implement native interfaces.
Standalone generation of one DTO remains available for existing callers, such
as AAC inline capability DTO generation.

`devtools/schema-field-bindings.json` identifies the interface/implementation
artifacts and technologies. Objects are discovered automatically. Its optional
`bindings` entries only override logical names or specify a common field
contract for union variants. There is deliberately no package override.
All other documented behavior and wire IDs remain unchanged.

## Clean checkout and GitHub

Publish the updated `pub.tool.General` Defs Codegen artifacts first (the generator
bootstrap script supports self-hosting). Then run in each consumer repository:

```bash
./gradlew --refresh-dependencies generateModustroSchemaBindings
./gradlew testModustroSchemaBindings
```

The generation task uses the generator already resolved on Modustro's JVM
classpath; it does not download code through an ad-hoc Python installer.
`testModustroSchemaBindings` imports both freshly generated Python trees and
checks abstract/concrete separation, annotated fields, schema package paths,
constant ownership and actual wire round trips. The repository `test`/`check`
entry points depend on it; packaging/source-processing tasks depend on generation.
Full existing artifact tests still run through their usual test entry points.

Previously tracked generated files require removal from the Git index even
when `.gitignore` is updated. The supplied migration script handles this with
`git rm --cached` and preserves local generated files. Alternatively:

```bash
git ls-files -z | python3 -c 'import sys; p=sys.stdin.buffer.read().split(b"\0"); sys.stdout.buffer.write(b"\0".join(x for x in p if any(s.endswith((b".gen", b".extgen")) for s in x.split(b"/"))) + b"\0")' | xargs -0 -r git rm --cached --
```

If old outputs exist locally, delete the disposable `.gen` trees once before
regenerating. General records owned outputs under
`build/run/schema-bindings/generated-files.json` and prunes only those files on
later runs, preserving outputs owned by other generators.

These conventions are retained with the source and apply to future generators and migrations.

## Parallel AAC canonical source kinds

AAC's canonical JSON/YAML schemas and XML/XSD projections are described in
[`aac/Canonical-Definition-And-Configuration-Formats.md`](aac/Canonical-Definition-And-Configuration-Formats.md).
YAML/XML schema files are intentionally without publication user-metadata sidecars
until the standalone Modustro generation task is exercised. The XSD is a typed
structural projection; only JSON Schema/YAML Schema carries the complete validation
semantics. Regenerate the three forms using
`python3 devtools/generate_schema_format_parity.py` and verify them using
`python3 devtools/test_schema_format_parity.py`.
