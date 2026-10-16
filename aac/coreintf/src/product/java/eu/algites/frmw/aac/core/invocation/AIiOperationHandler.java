package eu.algites.frmw.aac.core.invocation;

@FunctionalInterface
public interface AIiOperationHandler {
    Object execute(AIcInvocationInput aInput) throws Exception;
}
