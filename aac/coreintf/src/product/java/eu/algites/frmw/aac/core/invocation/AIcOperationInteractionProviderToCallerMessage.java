package eu.algites.frmw.aac.core.invocation;

import java.time.Instant;
import java.util.List;

public record AIcOperationInteractionProviderToCallerMessage<S>(
        long interactionRevision, AInOperationExecutionState executionState,
        long stateResultRevision, Long stateResultPayloadRevision, S stateResult,
        List<AIcOperationInteractionEvent> events, AIcOperationInteractionFeatures features,
        Instant publishedAt, AIcOperationCancellationAcceptance cancellationAcceptance)
        implements AIiOperationInteractionProviderToCallerMessage {
    public AIcOperationInteractionProviderToCallerMessage {
        events = List.copyOf(events);
        if (interactionRevision < 0 || stateResultRevision < 0) throw new IllegalArgumentException("negative revision");
        if (stateResultPayloadRevision != null && (stateResultPayloadRevision < 1 || stateResultPayloadRevision > stateResultRevision))
            throw new IllegalArgumentException("invalid state result payload revision");
    }
    public AIcOperationInteractionProviderToCallerMessage() {
        this(0, AInOperationExecutionState.PENDING, 0, null, null, List.of(), AIcOperationInteractionFeatures.defaults(), null, null);
    }
    public long getInteractionRevision() { return interactionRevision; }
    public AIcOperationInteractionProviderToCallerMessage<S> withTransportSequence(long sequence) {
        return new AIcOperationInteractionProviderToCallerMessage<>(sequence, executionState, stateResultRevision,
                stateResultPayloadRevision, stateResult, events, features,
                publishedAt == null ? Instant.now() : publishedAt, cancellationAcceptance);
    }
}
