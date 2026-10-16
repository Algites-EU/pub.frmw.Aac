package eu.algites.frmw.aac.core.interaction;

import eu.algites.frmw.aac.core.invocation.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Consumer;

/** Java operation-interaction controller. Framework publishes terminal lifecycle. */
public final class AIcOperationInteractionController<S>
        implements AIiOperationInteractionCallerToProviderOnCaller<AIcOperationInteractionCallerToProviderMessage>,
                   AIiOperationInteractionCallerToProviderOnProvider<AIcOperationInteractionCallerToProviderMessage, AIcOperationInteractionProviderToCallerMessage<S>>,
                   AIiOperationInteractionProviderToCallerOnProvider<AIcOperationInteractionProviderToCallerMessage<S>>,
                   AIiOperationInteractionProviderToCallerOnCaller<AIcOperationInteractionProviderToCallerMessage<S>>,
                   AIiOperationInteractionProviderActions<S> {
    private final ReentrantLock lock = new ReentrantLock();
    private final Consumer<List<AIcOperationInteractionProviderToCallerMessage<S>>> listener;
    private AIcOperationInteractionCallerToProviderMessage caller = new AIcOperationInteractionCallerToProviderMessage();
    private AIcOperationInteractionProviderToCallerMessage<S> last = new AIcOperationInteractionProviderToCallerMessage<>();
    private AIcOperationInteractionFeatures features = AIcOperationInteractionFeatures.defaults();
    private boolean featuresDeclared;
    private AInOperationExecutionState execution = AInOperationExecutionState.PENDING;
    private AIcOperationCancellationAcceptance accepted;
    private long interactionRevision;
    private long stateResultRevision;
    private S completeResult;
    private Long completeRevision;
    private final List<AIcOperationInteractionProviderToCallerMessage<S>> history = new ArrayList<>();

    public AIcOperationInteractionController() {this(null);}
    public AIcOperationInteractionController(Consumer<List<AIcOperationInteractionProviderToCallerMessage<S>>> aListener) {listener=aListener;}
    private void mutate(java.util.function.UnaryOperator<AIcOperationInteractionCallerToProviderMessage> aMutation) {
        lock.lock();
        try {caller = aMutation.apply(caller);} finally {lock.unlock();}
    }
    @Override public void scheduleCancel(String aCancelMessage, Instant aDeadline) {
        Objects.requireNonNull(aDeadline);
        mutate(old -> {
            if (accepted != null) return old;
            if (featuresDeclared && !features.cancellation()) throw new IllegalStateException("cancellation not supported");
            Instant now=Instant.now(); String reason=AInOperationCancellationReason.CALLER_REQUEST.name().toLowerCase(Locale.ROOT);
            var schedule=new HashMap<>(old.cancellationSchedule());
            var prev=schedule.get(reason);
            schedule.put(reason,new AIcOperationCancellationReasonRecord(reason,aDeadline,
                prev == null ? now : prev.firstRequestedAt(), now,
                prev == null ? 1 : prev.requestCount()+1,aCancelMessage,null));
            return old.withCancellationSchedule(old.callerInteractionRevision()+1,schedule);
        });
    }
    @Override public void cancelNow(String aMessage) {scheduleCancel(aMessage, Instant.now());}
    @Override public void withdrawCancel() {
        mutate(old -> {
            if (accepted != null) return old;
            var schedule=new HashMap<>(old.cancellationSchedule());
            if (schedule.remove(AInOperationCancellationReason.CALLER_REQUEST.name().toLowerCase(Locale.ROOT))==null) return old;
            return old.withCancellationSchedule(old.callerInteractionRevision()+1,schedule);
        });
    }
    @Override public void sendMessage(AIcOperationInteractionCallerToProviderMessage aMessage) {receiveMessage(aMessage);}
    @Override public AIcOperationInteractionProviderToCallerMessage<S> receiveMessage(AIcOperationInteractionCallerToProviderMessage aMessage) {
        lock.lock();
        try {
            if (aMessage.callerInteractionRevision() > caller.callerInteractionRevision())
                caller = accepted == null ? aMessage : aMessage.withCancellationSchedule(aMessage.callerInteractionRevision(),caller.cancellationSchedule());
            return null; // A provider is allowed to return one direct response, but is not required to.
        } finally {lock.unlock();}
    }
    @Override public void setInteractionMode(AInOperationInteractionMode aMode) {preferences(aMode,null,null,null,null,-1,-1);}
    @Override public void setDetailLevel(AInOperationInteractionDetailLevel aLevel) {preferences(null,aLevel,null,null,null,-1,-1);}
    @Override public void setReportingIntervalMs(Integer aInterval) {if(aInterval!=null&&aInterval<0)throw new IllegalArgumentException(); preferences(null,null,aInterval,null,null,-1,-1);}
    @Override public void setFailureDetailLevel(AInOperationInteractionFailureDetailLevel aLevel) {preferences(null,null,null,aLevel,null,-1,-1);}
    @Override public void setStateResultDeliveryMode(AInStateResultDeliveryMode aMode) {preferences(null,null,null,null,aMode,-1,-1);}
    @Override public void requestStateResult() {preferences(null,null,null,null,null,caller.stateResultRequestId()+1,-1);}
    @Override public void acceptStateResultRevision(long aRevision) {preferences(null,null,null,null,null,-1,aRevision);}
    private void preferences(AInOperationInteractionMode mode,AInOperationInteractionDetailLevel detail,Integer interval,
            AInOperationInteractionFailureDetailLevel failure,AInStateResultDeliveryMode delivery,long requestId,long acceptedRev) {
        mutate(old -> {
            var newDelivery = delivery==null?old.stateResultDeliveryMode():delivery;
            if (featuresDeclared && !features.supportedStateResultDeliveryModes().contains(newDelivery)) throw new IllegalArgumentException("unsupported delivery mode");
            if(detail!=null && !features.detailLevel())throw new IllegalArgumentException("unsupported detail level");
            if(interval!=null && !features.reportingInterval())throw new IllegalArgumentException("unsupported reporting interval");
            if(acceptedRev>stateResultRevision)throw new IllegalArgumentException("future result revision");
            return old.withPreferences(mode==null?old.interactionMode():mode,detail==null?old.detailLevel():detail,
                interval==null?old.reportingIntervalMs():interval,failure==null?old.failureDetailLevel():failure,
                newDelivery,requestId<0?old.stateResultRequestId():requestId,
                acceptedRev<0?old.lastAcceptedStateResultRevision():acceptedRev);
        });
    }
    @Override public void sendMessage(AIcOperationInteractionProviderToCallerMessage<S> aMessage) {
        lock.lock();
        try { publish(aMessage.stateResultPayloadRevision(),aMessage.stateResult(),aMessage.events()); }
        finally {lock.unlock();}
    }
    @Override public void receiveMessages(List<AIcOperationInteractionProviderToCallerMessage<S>> aMessages) {
        if(aMessages.isEmpty())return;
        lock.lock();
        try {
            long next=last.interactionRevision();
            for(var message:aMessages) {
                if(message.interactionRevision()<=next)throw new IllegalArgumentException("out-of-order received message");
                next=message.interactionRevision();
            }
            var previous = last;
            var previousRevision = interactionRevision;
            var previousAcceptance = accepted;
            last=aMessages.get(aMessages.size()-1);
            interactionRevision=next;
            if(last.cancellationAcceptance()!=null)accepted=last.cancellationAcceptance();
            try {
                if(listener!=null)listener.accept(List.copyOf(aMessages));
            } catch(RuntimeException | Error failure) {
                last=previous;
                interactionRevision=previousRevision;
                accepted=previousAcceptance;
                throw failure;
            }
        } finally {lock.unlock();}
    }
    @Override public void declareFeatures(AIcOperationInteractionFeatures aFeatures) {
        lock.lock();try{features=Objects.requireNonNull(aFeatures);featuresDeclared=true;publish(null,null,List.of());}finally{lock.unlock();}
    }
    @Override public void reportEvents(List<AIcOperationInteractionEvent> aEvents) {
        if(aEvents.isEmpty())return;
        lock.lock();try{publish(null,null,aEvents);}finally{lock.unlock();}
    }
    @Override public long stateResultChanged() {
        lock.lock();try {
            if(caller.stateResultDeliveryMode()==AInStateResultDeliveryMode.ALWAYS_COMPLETE
                    || caller.stateResultDeliveryMode()==AInStateResultDeliveryMode.ON_CHANGE_COMPLETE
                    || caller.stateResultDeliveryMode()==AInStateResultDeliveryMode.ON_CHANGE_DELTA)
                throw new IllegalStateException("selected mode requires a payload");
            stateResultRevision++;publish(null,null,List.of());return stateResultRevision;
        }finally{lock.unlock();}
    }
    @Override public long updateStateResult(S aResult) {
        lock.lock();try {
            stateResultRevision++;
            var mode=caller.stateResultDeliveryMode();
            boolean include=mode==AInStateResultDeliveryMode.ALWAYS_COMPLETE||mode==AInStateResultDeliveryMode.ON_CHANGE_COMPLETE||mode==AInStateResultDeliveryMode.ON_CHANGE_DELTA;
            if(mode==AInStateResultDeliveryMode.ALWAYS_COMPLETE){completeResult=aResult;completeRevision=stateResultRevision;}
            publish(include?stateResultRevision:null,include?aResult:null,List.of());return stateResultRevision;
        }finally{lock.unlock();}
    }
    @Override public void deliverStateResult(S aResult,long aRevision) {
        lock.lock();try {
            if(aRevision<1||aRevision>stateResultRevision)throw new IllegalArgumentException("unknown result revision");
            publish(aRevision,aResult,List.of());
        }finally{lock.unlock();}
    }
    @Override public AIcOperationInteractionCallerToProviderMessage callerSnapshot(){lock.lock();try{return caller;}finally{lock.unlock();}}
    @Override public AIcOperationCancellationAcceptance acceptCancellation(Set<String> aReasons){
        lock.lock();try {
            if(accepted!=null)return accepted;
            accepted=new AIcOperationCancellationAcceptance(caller,aReasons,Instant.now());
            publish(null,null,List.of());return accepted;
        }finally{lock.unlock();}
    }
    public void coreTransition(AInOperationExecutionState aState,S aResult,boolean aHasResult) {
        lock.lock();try {
            boolean valid=execution==AInOperationExecutionState.PENDING&&aState==AInOperationExecutionState.RUNNING
                    ||execution==AInOperationExecutionState.RUNNING&&(aState==AInOperationExecutionState.COMPLETED
                    ||aState==AInOperationExecutionState.CANCELLED||aState==AInOperationExecutionState.FAILED);
            if(!valid)throw new IllegalStateException("invalid framework-owned lifecycle transition");
            execution=aState;
            if(aHasResult) {
                stateResultRevision++;
                var mode=caller.stateResultDeliveryMode();
                boolean include=mode==AInStateResultDeliveryMode.ALWAYS_COMPLETE
                        ||mode==AInStateResultDeliveryMode.ON_CHANGE_COMPLETE
                        ||mode==AInStateResultDeliveryMode.ON_CHANGE_DELTA;
                publish(include?stateResultRevision:null,include?aResult:null,List.of());
            } else { publish(null,null,List.of()); }
        }finally{lock.unlock();}
    }
    private void publish(Long payloadRevision,S payload,List<AIcOperationInteractionEvent> events){
        interactionRevision++;
        var message=new AIcOperationInteractionProviderToCallerMessage<S>(interactionRevision,execution,stateResultRevision,
            payloadRevision,payload,events,features,Instant.now(),accepted);
        last=message;history.add(message);
    }
    public List<AIcOperationInteractionProviderToCallerMessage<S>> publications(){
        lock.lock();try{return List.copyOf(history);}finally{lock.unlock();}
    }
    public AIcOperationInteractionProviderToCallerMessage<S> providerSnapshot(){lock.lock();try{return last;}finally{lock.unlock();}}
}
