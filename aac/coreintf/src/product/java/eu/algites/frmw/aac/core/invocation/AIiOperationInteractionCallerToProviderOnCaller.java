package eu.algites.frmw.aac.core.invocation;

import java.time.Instant;

public interface AIiOperationInteractionCallerToProviderOnCaller<
        C2PM extends AIiOperationInteractionCallerToProviderMessage> {
    void scheduleCancel(String aCancelMessage, Instant aDeadline);
    void cancelNow(String aCancelMessage);
    void withdrawCancel();
    void sendMessage(C2PM aMessage);
    void setInteractionMode(AInOperationInteractionMode aMode);
    void setDetailLevel(AInOperationInteractionDetailLevel aLevel);
    void setReportingIntervalMs(Integer aIntervalMs);
    void setFailureDetailLevel(AInOperationInteractionFailureDetailLevel aLevel);
    void setStateResultDeliveryMode(AInStateResultDeliveryMode aMode);
    void requestStateResult();
    void acceptStateResultRevision(long aRevision);
}
