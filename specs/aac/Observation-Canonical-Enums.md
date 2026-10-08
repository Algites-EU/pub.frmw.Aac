# Observation phase and outcome canonical enums

`observation-input_1` is the authoritative schema for the observation `Phase` and `Outcome` values.

The `pub.tool.General` schema bindings generator creates the following Python enums in `aac/coreintf/src/product/python.gen/eu/algites/frmw/aac/core/observation`:

- `AIngObservationInputPhase_1`: `PRE = "pre"`, `POST = "post"`.
- `AIngObservationInputOutcome_1`: `SUCCESS = "success"`, `ERROR = "error"`, plus the schema's `null` member (in AAC runtime `None` is represented as `None`).

The generated `.gen` sources are build outputs, not files checked into Git. Handwritten AAC modules import the generated enums and must not maintain independent `AInObservationPhase` or `AInObservationOutcome` definitions. An interface module that uses the enums must be staged with the generated source tree before running tests or packaging. Run `./gradlew generateModustroSchemaBindings` before AAC Python tests.

`AIcgdObservationInput_1.from_mapping` accepts lower-case wire values; `to_mapping` preserves them. The AAC public observation API exposes `AIigObservationInput_1`, and `aac.coreimpl` constructs the generated `AIcgdObservationInput_1` DTO. No handwritten `AIcObservationInput` model is maintained. Generator-owned `python.gen` directories are never committed. UI display labels such as `PRE` / `POST` are visual only.


## Generated observation input contract

The repository manifest `devtools/schema-field-bindings.json` controls generation:
`generateModustroSchemaBindings` emits `AIigObservationInput_1` into `aac/coreintf/src/product/python.gen` and `AIcgdObservationInput_1` into `aac/coreimpl/src/product/python.gen`. AAC exports the interface from its CoreIntf observation API; CoreImpl constructs the DTO. Both are generator outputs and **must not be checked into source control**. The original `AIcObservationInput` dataclass was removed rather than retained as an alias.

The canonical `Phase` and `Outcome` enum identifiers are also generated. DTO scalar properties are serialized using the generator's `to_mapping()` method, not handwritten field-name mapping. The process runtime converts generated interface annotations into generated DTO instances via the conventional module name. The simpleaudit provider accepts only the interface and uses the same serialized mapping.

**Current generator limitation:** its Python DTO handling of explicit JSON `null` for `Outcome` and other unconstrained optional fields is not equivalent to the JSON Schema contract. Until corrected in `pub.tool.General`, AAC omits absent optional observation fields rather than passing explicit `None`. This limitation is not addressed by duplicating the DTO in AAC; it requires a generator fix.

To validate on a working generator publication:

```bash
./gradlew generateModustroSchemaBindings --no-configuration-cache
./gradlew test --no-configuration-cache
```
