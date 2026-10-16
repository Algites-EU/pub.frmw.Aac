package eu.algites.frmw.aac.core.invocation;

@FunctionalInterface
public interface AIiCapabilityEndpoint {
    AIcInvocationOutput invoke(AIcInvocationInput aInput);
}
