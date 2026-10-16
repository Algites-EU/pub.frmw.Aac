package eu.algites.frmw.aac.core.invocation;

public interface AIiOperationInteractionProviderToCallerOnProvider<
        P2CM extends AIiOperationInteractionProviderToCallerMessage> {
    void sendMessage(P2CM aMessage);
}
