package eu.algites.frmw.aac.core.invocation;

import java.util.*;

/** Immutable transport-independent input corresponding to Python AIcInvocationInput. */
public record AIcInvocationInput(
        String invocationId, String parentInvocationId, String capabilityId,
        int capabilityVersion, String operationId, String providerInstanceId,
        Map<String, Object> arguments, Map<String, Object> operationParameterOverrides,
        Map<String, Object> effectiveOperationParameters,
        List<Map<String, Object>> bindingQualifierProfiles,
        String consumerInstanceId, String requirementId, String locale) {
    public AIcInvocationInput {
        Objects.requireNonNull(invocationId);Objects.requireNonNull(capabilityId);
        Objects.requireNonNull(operationId);Objects.requireNonNull(providerInstanceId);
        arguments=Map.copyOf(arguments);
        operationParameterOverrides=Map.copyOf(operationParameterOverrides);
        effectiveOperationParameters=Map.copyOf(effectiveOperationParameters);
        bindingQualifierProfiles=bindingQualifierProfiles.stream().map(Map::copyOf).toList();
        if(capabilityVersion<0)throw new IllegalArgumentException("invalid capability version");
    }
}
