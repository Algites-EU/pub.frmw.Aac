package eu.algites.frmw.aac.core.invocation;

import java.util.List;
import java.util.Set;

public interface AIiOperationInteractionProviderActions<S> {
    void declareFeatures(AIcOperationInteractionFeatures aFeatures);
    void reportEvents(List<AIcOperationInteractionEvent> aEvents);
    long stateResultChanged();
    long updateStateResult(S aStateResult);
    void deliverStateResult(S aStateResult, long aExistingRevision);
    AIcOperationInteractionCallerToProviderMessage callerSnapshot();
    AIcOperationCancellationAcceptance acceptCancellation(Set<String> aReasons);
}
