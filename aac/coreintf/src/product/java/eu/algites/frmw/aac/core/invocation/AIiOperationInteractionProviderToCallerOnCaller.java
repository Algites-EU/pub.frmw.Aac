package eu.algites.frmw.aac.core.invocation;

import java.util.List;

public interface AIiOperationInteractionProviderToCallerOnCaller<
        P2CM extends AIiOperationInteractionProviderToCallerMessage> {
    /** Process EVERY publication in order before dispatching external reactions. */
    void receiveMessages(List<P2CM> aMessages);
}
