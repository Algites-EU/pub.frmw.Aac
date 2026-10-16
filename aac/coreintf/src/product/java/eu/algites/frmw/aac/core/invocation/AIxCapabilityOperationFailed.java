package eu.algites.frmw.aac.core.invocation;

public class AIxCapabilityOperationFailed extends RuntimeException {
    private final AIcOperationFailure failure;
    public AIxCapabilityOperationFailed(AIcOperationFailure aFailure) {
        super(aFailure.systemMessage());failure=aFailure;
    }
    public AIcOperationFailure getFailure(){return failure;}
}
