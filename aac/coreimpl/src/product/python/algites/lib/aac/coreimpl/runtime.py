from __future__ import annotations

from algites.lib.aac.coreintf.descriptor import AIcProviderDefinitionDescriptor, AInProviderRuntimeProfile
from algites.lib.aac.coreintf.instances import AIcProviderInstance
from algites.lib.aac.coreintf.entitlement import AIcEntitlementContext
from algites.lib.aac.coreintf.configuration import AIcEffectiveConfiguration
from algites.lib.aac.coreintf.runtime import AIiProviderRuntime, AIcProviderRuntimeContext, AIiProviderRuntimeFactory

from .loading import load_class


def instantiate_provider(
    application_scope_id: str,
    instance: AIcProviderInstance,
    provider_definition: AIcProviderDefinitionDescriptor,
    entitlement: AIcEntitlementContext,
    *,
    component_configuration: AIcEffectiveConfiguration,
    provider_instance_configuration: AIcEffectiveConfiguration,
) -> AIiProviderRuntime:
    """Instantiate one provider runtime for one Core-managed provider instance."""
    context = AIcProviderRuntimeContext(
        application_scope_id, instance, entitlement, component_configuration, provider_instance_configuration
    )
    if provider_definition.runtime.profile is AInProviderRuntimeProfile.PROCESS:
        from .process import AIcProcessProviderRuntime
        return AIcProcessProviderRuntime(
            application_scope_id, instance, provider_definition, entitlement,
            component_configuration=component_configuration,
            provider_instance_configuration=provider_instance_configuration,
        )
    if provider_definition.runtime.profile is AInProviderRuntimeProfile.SUBINTERPRETER:
        raise RuntimeError(
            "SUBINTERPRETER provider lifecycle profile requires CPython 3.14+ integration and is not selected by the baseline process/in-process runtime factory"
        )
    if provider_definition.runtime_factory_class:
        factory_class = load_class(provider_definition.runtime_factory_class, AIiProviderRuntimeFactory)
        runtime = factory_class().create(context)
        if not isinstance(runtime, AIiProviderRuntime):
            raise TypeError("provider runtime factory returned a non-AIiProviderRuntime value")
        return runtime

    provider_class = load_class(instance.implementation_class, AIiProviderRuntime)
    effective_instance = provider_instance_configuration.plain_values()
    runtime = provider_class(effective_instance if effective_instance else dict(instance.configuration))
    if not isinstance(runtime, AIiProviderRuntime):
        raise TypeError("provider implementation is not a AIiProviderRuntime")
    return runtime
