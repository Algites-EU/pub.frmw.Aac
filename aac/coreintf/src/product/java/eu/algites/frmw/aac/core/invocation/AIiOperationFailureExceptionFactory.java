package eu.algites.frmw.aac.core.invocation;

@FunctionalInterface
public interface AIiOperationFailureExceptionFactory<X extends AIxCapabilityOperationFailed> {
    X create(AIcOperationFailure aFailure);
}
