package eu.algites.frmw.aac.core.interaction;

import eu.algites.frmw.aac.core.invocation.*;
import java.time.Instant;
import java.util.*;

/** Standalone conformance smoke test (java -ea); no third-party JUnit dependency. */
public final class AItcOperationInteractionTest {
    public static void main(String[] aArguments) {
        List<List<Long>> delivered = new ArrayList<>();
        var caller = new AIcOperationInteractionReliableCallerTransport<String>(messages ->
                delivered.add(messages.stream().map(AIcOperationInteractionProviderToCallerMessage::interactionRevision).toList()));
        List<Long> requests = new ArrayList<>();
        AIiOperationInteractionCallerToProviderOnProvider<AIcOperationInteractionCallerToProviderMessage,
                AIcOperationInteractionProviderToCallerMessage<String>> provider = message -> {
                    requests.add(message.callerInteractionRevision());
                    return message("reply", 7, 1L);
                };
        var transport = new AIcOperationInteractionReliableProviderTransport<>(provider);
        transport.sendMessage(message("delta1", 1, 1L));
        transport.sendMessage(message("delta2", 2, 2L));
        transport.sendMessage(message("delta3", 3, 3L));
        var state = new AIcOperationInteractionCallerToProviderMessage().withCancellationSchedule(1, Map.of());
        var batch = transport.exchange(0, state);
        assert batch.size() == 4;
        assert batch.get(0).stateResult().equals("delta1");
        assert batch.get(3).stateResult().equals("reply");
        caller.receiveMessages(batch);
        assert caller.lastReceivedRevision() == 4;
        assert delivered.equals(List.of(List.of(1L,2L,3L,4L)));
        caller.receiveMessages(transport.exchange(0, state));
        assert delivered.size() == 1;
        assert requests.equals(List.of(1L));
        assert transport.exchange(caller.lastReceivedRevision(), null).isEmpty();
        assert transport.pendingCount() == 0;
        try { caller.receiveMessages(List.of(message("gap", 9, null).withTransportSequence(6))); throw new AssertionError("gap accepted"); }
        catch(IllegalArgumentException expected) {}
        var flaky = new AIcOperationInteractionReliableCallerTransport<String>(messages -> {
            throw new IllegalStateException("subscriber failure");
        });
        try { flaky.receiveMessages(List.of(message("retry", 1, 1L).withTransportSequence(1))); throw new AssertionError("expected failure"); }
        catch(IllegalStateException expected) {}
        assert flaky.lastReceivedRevision() == 0;
        var invocation = new AIcInvocationInput("invoke-1", null, "capability", 1, "operation", "provider",
                Map.of("name", "example"), Map.of(), Map.of(), List.of(), null, null, "cs-CZ");
        var endpoint = new eu.algites.frmw.aac.core.invocation.AIcInProcessCapabilityEndpoint(
                Map.of("operation", input -> input.arguments().get("name")));
        var output = endpoint.invoke(invocation);
        assert output.success() && output.result().equals("example");
        var controller = new AIcOperationInteractionController<String>();
        controller.scheduleCancel("stop", Instant.now().minusSeconds(1));
        assert controller.callerSnapshot().cancellationSchedule().size() == 1;
        var accepted = controller.acceptCancellation(Set.of("caller_request"));
        assert accepted.acceptedInteractionSnapshot().callerInteractionRevision() == 1;
        controller.withdrawCancel();
        assert controller.callerSnapshot().cancellationSchedule().size() == 1;
        controller.coreTransition(AInOperationExecutionState.RUNNING, null, false);
        controller.coreTransition(AInOperationExecutionState.CANCELLED, "cancelled", true);
        assert controller.providerSnapshot().executionState() == AInOperationExecutionState.CANCELLED;
        assert controller.providerSnapshot().stateResultRevision() == 1;
        assert controller.publications().size() == 3;
        System.out.println("Java AAC interaction transport and controller conformance passed");
    }
    private static AIcOperationInteractionProviderToCallerMessage<String> message(String value,long revision,Long payloadRevision) {
        return new AIcOperationInteractionProviderToCallerMessage<>(0,AInOperationExecutionState.RUNNING,
                revision,payloadRevision,value,List.of(),AIcOperationInteractionFeatures.defaults(),null,null);
    }
}