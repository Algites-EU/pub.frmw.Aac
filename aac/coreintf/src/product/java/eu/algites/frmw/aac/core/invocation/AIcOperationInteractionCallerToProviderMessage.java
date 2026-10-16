package eu.algites.frmw.aac.core.invocation;

import java.util.Map;

public record AIcOperationInteractionCallerToProviderMessage(
        long callerInteractionRevision,
        Map<String, AIcOperationCancellationReasonRecord> cancellationSchedule,
        long lastAcceptedStateResultRevision, AInOperationInteractionMode interactionMode,
        AInOperationInteractionDetailLevel detailLevel, Integer reportingIntervalMs,
        AInOperationInteractionFailureDetailLevel failureDetailLevel,
        AInStateResultDeliveryMode stateResultDeliveryMode, long stateResultRequestId)
        implements AIiOperationInteractionCallerToProviderMessage {

    public AIcOperationInteractionCallerToProviderMessage {
        if (callerInteractionRevision < 0 || lastAcceptedStateResultRevision < 0 || stateResultRequestId < 0)
            throw new IllegalArgumentException("negative interaction revision");
        if (reportingIntervalMs != null && reportingIntervalMs < 0) throw new IllegalArgumentException("negative reporting interval");
        cancellationSchedule = Map.copyOf(cancellationSchedule);
        for (var entry : cancellationSchedule.entrySet()) {
            if (!entry.getKey().equals(entry.getValue().reason())) throw new IllegalArgumentException("inconsistent cancellation reason");
        }
    }
    public AIcOperationInteractionCallerToProviderMessage() {
        this(0, Map.of(), 0, AInOperationInteractionMode.FOREGROUND,
                AInOperationInteractionDetailLevel.SUMMARY, null,
                AInOperationInteractionFailureDetailLevel.BASIC,
                AInStateResultDeliveryMode.ON_DEMAND_COMPLETE, 0);
    }
    public long getCallerInteractionRevision() { return callerInteractionRevision; }
    public Map<String, AIcOperationCancellationReasonRecord> getCancellationSchedule() { return cancellationSchedule; }
    public AIcOperationInteractionCallerToProviderMessage withCancellationSchedule(long revision, Map<String, AIcOperationCancellationReasonRecord> schedule) {
        return new AIcOperationInteractionCallerToProviderMessage(revision, schedule, lastAcceptedStateResultRevision,
                interactionMode, detailLevel, reportingIntervalMs, failureDetailLevel, stateResultDeliveryMode, stateResultRequestId);
    }
    public AIcOperationInteractionCallerToProviderMessage withPreferences(
            AInOperationInteractionMode mode, AInOperationInteractionDetailLevel detail,
            Integer interval, AInOperationInteractionFailureDetailLevel failure,
            AInStateResultDeliveryMode delivery, long requestId, long acceptedResultRevision) {
        return new AIcOperationInteractionCallerToProviderMessage(callerInteractionRevision + 1, cancellationSchedule,
                acceptedResultRevision, mode, detail, interval, failure, delivery, requestId);
    }
}
