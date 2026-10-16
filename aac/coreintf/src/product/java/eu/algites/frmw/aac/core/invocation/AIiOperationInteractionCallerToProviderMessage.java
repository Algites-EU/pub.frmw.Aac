package eu.algites.frmw.aac.core.invocation;

public interface AIiOperationInteractionCallerToProviderMessage {
    long getCallerInteractionRevision();
    java.util.Map<String, AIcOperationCancellationReasonRecord> getCancellationSchedule();
}
