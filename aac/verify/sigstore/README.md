# AAC Sigstore Verifier

Optional Sigstore implementation of AAC verification SPIs. AAC Core does not depend on this artifact.

The package verifier validates the exact package artifact and detached Sigstore bundle against an explicit product-supplied trust policy. Trust may constrain identities, OIDC issuers, repositories or workflows.

The artifact also provides entitlement-evidence verification for signed entitlement documents. Cryptographic validity does not by itself grant entitlement authority; Core separately applies trusted-issuer policy.
