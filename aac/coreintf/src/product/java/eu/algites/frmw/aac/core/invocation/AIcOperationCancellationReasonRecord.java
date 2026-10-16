package eu.algites.frmw.aac.core.invocation;

import java.time.Instant;
import java.util.Objects;

public record AIcOperationCancellationReasonRecord(
        String reason, Instant currentDeadline, Instant firstRequestedAt,
        Instant lastRequestedAt, long requestCount, String lastMessage, String lastOrigin) {
    public AIcOperationCancellationReasonRecord {
        if (reason == null || reason.isBlank()) throw new IllegalArgumentException("reason is required");
        Objects.requireNonNull(currentDeadline);
        Objects.requireNonNull(firstRequestedAt);
        Objects.requireNonNull(lastRequestedAt);
        if (lastRequestedAt.isBefore(firstRequestedAt) || requestCount < 1) throw new IllegalArgumentException("invalid cancellation record chronology");
    }
}
