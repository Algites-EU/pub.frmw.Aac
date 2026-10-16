package eu.algites.frmw.aac.core.invocation;

import java.util.Set;

public record AIcOperationInteractionFeatures(
        boolean progressReporting, boolean cancellation, boolean detailLevel,
        boolean reportingInterval, Set<AInStateResultDeliveryMode> supportedStateResultDeliveryModes) {
    public AIcOperationInteractionFeatures {
        supportedStateResultDeliveryModes = Set.copyOf(supportedStateResultDeliveryModes);
        if (!supportedStateResultDeliveryModes.contains(AInStateResultDeliveryMode.ON_DEMAND_COMPLETE))
            throw new IllegalArgumentException("ON_DEMAND_COMPLETE support is required");
    }
    public static AIcOperationInteractionFeatures defaults() {
        return new AIcOperationInteractionFeatures(false, false, false, false,
                Set.of(AInStateResultDeliveryMode.ON_DEMAND_COMPLETE));
    }
}
