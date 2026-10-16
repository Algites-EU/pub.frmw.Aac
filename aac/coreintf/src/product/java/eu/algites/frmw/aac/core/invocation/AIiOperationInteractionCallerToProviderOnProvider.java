package eu.algites.frmw.aac.core.invocation;

public interface AIiOperationInteractionCallerToProviderOnProvider<
        C2PM extends AIiOperationInteractionCallerToProviderMessage,
        P2CM extends AIiOperationInteractionProviderToCallerMessage> {
    /** Receive one versioned caller state; optionally return one independent P2C publication. */
    P2CM receiveMessage(C2PM aMessage);
}
