# Algites Python Source Conventions

## Repository and artifact layout

Repository versioning is owned by root `algites-source-repository.yml`. Artifact `algites-artifact.yml` may define its own `versionContext` only when an explicit override is required. Directly dependent artifacts normally share the repository version.

For repository version `1.0-SNAPSHOT`, Python package metadata uses the PEP 440 representation `1.0.dev0`. Files whose naming is controlled by Algites use an underscore before a schema/version suffix, for example `component-descriptor_1.json`. Externally standardized Python wheel/sdist filenames follow the Python packaging standard instead.

## Python type prefixes

Production type names use the same Algites conventions as Java:

- `AIi...` — interface / Python ABC
- `AIc...` — class
- `AIn...` — enum
- `AIx...` — exception
- `AIig..._N` — generated interface
- `AIcg..._N` — generated non-data class
- `AIigd..._N` — generated data-object/DTO interface when such an interface is explicitly needed
- `AIcgd..._N` — generated data-object/DTO class

`g` marks a generated type. The optional `d` is a semantic data-object/DTO marker and MUST NOT be added to generated behavioral classes merely because they are generated. Generated types derived from versioned canonical definitions MUST carry the source-definition version suffix `_N` so multiple versions can coexist in one runtime. Generated source MUST expose canonical source ID and source version as machine-readable metadata and in its docstring/Javadoc. It SHOULD additionally expose the canonical resource path. The resource path is provenance/location, not part of canonical identity.
- `AIr...` — resource bundle

Python modules/packages retain normal lowercase Python naming. Generated prefixes are reserved even when a repository currently contains no generated types.
