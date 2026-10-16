package eu.algites.frmw.aac.core.invocation;

import eu.algites.frmw.aac.core.invocation.*;
import java.util.Objects;

/** Java invocation handle forwards normalized input to its bound endpoint. */
public final class AIcCapabilityHandle implements AIiCapabilityHandle {
    private final AIiCapabilityEndpoint endpoint;
    public AIcCapabilityHandle(AIiCapabilityEndpoint aEndpoint){endpoint=Objects.requireNonNull(aEndpoint);}
    @Override public AIcInvocationOutput invoke(AIcInvocationInput aInput){return endpoint.invoke(aInput);}
}
