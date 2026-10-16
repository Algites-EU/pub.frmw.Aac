package eu.algites.frmw.aac.core.invocation;

import java.time.Instant;
import java.util.Set;
import java.util.Objects;

public record AIcOperationCancellationAcceptance(
        AIcOperationInteractionCallerToProviderMessage acceptedInteractionSnapshot,
        Set<String> acceptedReasons, Instant acceptedAt) {
    public AIcOperationCancellationAcceptance {
        Objects.requireNonNull(acceptedInteractionSnapshot);
        Objects.requireNonNull(acceptedAt);
        acceptedReasons = Set.copyOf(acceptedReasons);
        if (acceptedReasons.isEmpty()) throw new IllegalArgumentException("acceptance requires reasons");
        for (String reason : acceptedReasons) {
            AIcOperationCancellationReasonRecord entry = acceptedInteractionSnapshot.cancellationSchedule().get(reason);
            if (entry == null || entry.currentDeadline().isAfter(acceptedAt))
                throw new IllegalArgumentException("cancellation reason missing or not effective: " + reason);
        }
    }
}
