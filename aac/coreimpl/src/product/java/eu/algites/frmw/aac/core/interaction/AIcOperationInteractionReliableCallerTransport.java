package eu.algites.frmw.aac.core.interaction;

import eu.algites.frmw.aac.core.invocation.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/** Receives every new contiguous publication in one batch; suppresses replayed revisions. */
public final class AIcOperationInteractionReliableCallerTransport<S> {
    private final AIiOperationInteractionProviderToCallerOnCaller<AIcOperationInteractionProviderToCallerMessage<S>> receiver;
    private final ReentrantLock lock = new ReentrantLock();
    private long lastReceived;
    public AIcOperationInteractionReliableCallerTransport(
            AIiOperationInteractionProviderToCallerOnCaller<AIcOperationInteractionProviderToCallerMessage<S>> aReceiver) {
        receiver = Objects.requireNonNull(aReceiver);
    }
    public void receiveMessages(List<AIcOperationInteractionProviderToCallerMessage<S>> aMessages) {
        lock.lock();
        try {
            List<AIcOperationInteractionProviderToCallerMessage<S>> fresh = new ArrayList<>();
            long expected = lastReceived + 1;
            for (var message : aMessages) {
                if (message.interactionRevision() < expected) continue;
                if (message.interactionRevision() != expected) throw new IllegalArgumentException("gap in P2C revisions");
                fresh.add(message);
                expected++;
            }
            if (!fresh.isEmpty()) {
                receiver.receiveMessages(List.copyOf(fresh));
                lastReceived = expected - 1;
            }
        } finally { lock.unlock(); }
    }
    public long lastReceivedRevision() { lock.lock(); try {return lastReceived;} finally {lock.unlock();} }
}
