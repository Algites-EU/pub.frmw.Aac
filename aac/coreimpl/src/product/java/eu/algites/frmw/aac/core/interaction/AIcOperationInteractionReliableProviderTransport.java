package eu.algites.frmw.aac.core.interaction;

import eu.algites.frmw.aac.core.invocation.*;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

/** In-memory reference transport: ordered, lossless while alive, cumulative ACK, C2P request deduplication. */
public final class AIcOperationInteractionReliableProviderTransport<S>
        implements AIiOperationInteractionProviderToCallerOnProvider<AIcOperationInteractionProviderToCallerMessage<S>> {
    private final AIiOperationInteractionCallerToProviderOnProvider<AIcOperationInteractionCallerToProviderMessage, AIcOperationInteractionProviderToCallerMessage<S>> provider;
    private final ReentrantLock lock = new ReentrantLock();
    private final NavigableMap<Long, AIcOperationInteractionProviderToCallerMessage<S>> pending = new TreeMap<>();
    private long nextSequence = 1;
    private long lastSent = 0;
    private long lastAck = 0;
    private long lastCallerRevision = -1;

    public AIcOperationInteractionReliableProviderTransport(
            AIiOperationInteractionCallerToProviderOnProvider<AIcOperationInteractionCallerToProviderMessage, AIcOperationInteractionProviderToCallerMessage<S>> aProvider) {
        provider = Objects.requireNonNull(aProvider);
    }
    @Override public void sendMessage(AIcOperationInteractionProviderToCallerMessage<S> aMessage) {
        lock.lock();
        try { pending.put(nextSequence, Objects.requireNonNull(aMessage).withTransportSequence(nextSequence)); nextSequence++; }
        finally { lock.unlock(); }
    }
    public List<AIcOperationInteractionProviderToCallerMessage<S>> exchange(long aAcknowledgedRevision,
            AIcOperationInteractionCallerToProviderMessage aCallerMessage) {
        lock.lock();
        try {
            if (aAcknowledgedRevision < lastAck || aAcknowledgedRevision > lastSent)
                throw new IllegalArgumentException("invalid cumulative acknowledgment");
            if (aAcknowledgedRevision > lastAck) {
                pending.headMap(aAcknowledgedRevision, true).clear();
                lastAck = aAcknowledgedRevision;
            }
            if (aCallerMessage != null && aCallerMessage.callerInteractionRevision() > lastCallerRevision) {
                var response = provider.receiveMessage(aCallerMessage);
                lastCallerRevision = aCallerMessage.callerInteractionRevision();
                if (response != null) sendMessage(response);
            }
            List<AIcOperationInteractionProviderToCallerMessage<S>> messages = List.copyOf(pending.values());
            if (!messages.isEmpty()) lastSent = Math.max(lastSent, messages.get(messages.size()-1).interactionRevision());
            return messages;
        } finally { lock.unlock(); }
    }
    public int pendingCount() { lock.lock(); try {return pending.size();} finally {lock.unlock();} }
    public long lastAck() { lock.lock(); try {return lastAck;} finally {lock.unlock();} }
}
