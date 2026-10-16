package eu.algites.frmw.aac.core.invocation;

import java.util.Map;

public record AIcOperationInteractionEvent(
        AInOperationInteractionEventType eventType, String progressId,
        String parentProgressId, String phaseId, String name, String description,
        Double current, Double total, String unit, AInOperationInteractionSeverity severity,
        String code, Map<String, Object> details) {
    public AIcOperationInteractionEvent {
        details = details == null ? Map.of() : Map.copyOf(details);
        if (eventType == AInOperationInteractionEventType.PROGRESS && (progressId == null || progressId.isBlank()))
            throw new IllegalArgumentException("progress requires progressId");
        if (progressId != null && progressId.equals(parentProgressId))
            throw new IllegalArgumentException("progress cannot be its own parent");
        if (current != null && current < 0 || total != null && total < 0)
            throw new IllegalArgumentException("progress values must be non-negative");
    }
}
