# AAC Development Tools

AAC repository build/test/version/convention tooling is a first-class artifact under `devtools/aacbuilding`. Its Python product sources live under `src/product/python`, preparing the repository for artifacts that can carry multiple technology source trees under `src/product/<technology>`.

The artifact contains repository version synchronization, convention checking, bounded test execution, and artifact building.


Derived build/test/package output is repository-central under `build/run/<artifact-relative-path>/run/`; these tools do not use artifact-local `run/` directories. Public binding/code generation lives separately in `devtools/generators/aaccodegen`.
