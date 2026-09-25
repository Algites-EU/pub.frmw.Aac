from algites.frmw.aac.coreintf.errors import AIxAACError


class AIxCoreImplementationError(AIxAACError):
    pass


class AIxDescriptorValidationError(AIxCoreImplementationError):
    pass


class AIxContractAdmissionError(AIxCoreImplementationError):
    pass


class AIxContractConflictError(AIxContractAdmissionError):
    pass


class AIxContractNegotiationError(AIxCoreImplementationError):
    pass


class AIxSchemaValidationError(AIxCoreImplementationError):
    def __init__(self, schema_name: str, diagnostics: tuple[str, ...]):
        self.schema_name = schema_name
        self.diagnostics = diagnostics
        super().__init__(f"schema validation failed for {schema_name!r}: " + "; ".join(diagnostics))


class AIxBindingResolutionError(AIxCoreImplementationError):
    pass


class AIxBindingCycleError(AIxBindingResolutionError):
    def __init__(self, cycle: tuple[str, ...]):
        self.cycle = cycle
        super().__init__("provider-instance binding cycle detected: " + " -> ".join(cycle))


class AIxPluginLoadError(AIxCoreImplementationError):
    pass


class AIxProvisioningError(AIxCoreImplementationError):
    pass


class AIxEntitlementError(AIxCoreImplementationError):
    pass


class AIxLifecycleError(AIxCoreImplementationError):
    pass


class AIxPersistenceError(AIxCoreImplementationError):
    pass


class AIxPersistenceRevisionConflict(AIxPersistenceError):
    def __init__(self, record_id: str, expected, actual):
        self.record_id = record_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"persistence revision conflict for {record_id!r}: expected {expected!r}, actual {actual!r}"
        )


class AIxProcessEndpointError(AIxCoreImplementationError):
    pass


class AIxUpgradeError(AIxCoreImplementationError):
    pass


class AIxVerificationError(AIxCoreImplementationError):
    pass


class AIxSubinterpreterUnavailableError(AIxCoreImplementationError):
    pass


class AIxConfigurationError(AIxCoreImplementationError):
    pass


class AIxConfigurationConflictError(AIxConfigurationError):
    pass


class AIxConfigurationPolicyError(AIxConfigurationError):
    pass


class AIxPersistedPayloadMigrationError(AIxCoreImplementationError):
    pass

class AIxConfigurationRevisionConflict(AIxConfigurationConflictError):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
        super().__init__(f"configuration revision conflict: expected {expected!r}, actual {actual!r}")


class AIxAuthenticationError(AIxCoreImplementationError):
    pass
