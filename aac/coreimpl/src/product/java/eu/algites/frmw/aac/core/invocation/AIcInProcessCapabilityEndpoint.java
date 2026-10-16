package eu.algites.frmw.aac.core.invocation;

import eu.algites.frmw.aac.core.invocation.*;
import java.util.*;

/** Minimal Java in-process dispatch, independent of Spring or Gradle. */
public final class AIcInProcessCapabilityEndpoint implements AIiCapabilityEndpoint {
    private final Map<String,AIiOperationHandler> handlers;
    public AIcInProcessCapabilityEndpoint(Map<String,AIiOperationHandler> aHandlers){handlers=Map.copyOf(aHandlers);}
    @Override public AIcInvocationOutput invoke(AIcInvocationInput aInput){
        AIiOperationHandler handler=handlers.get(aInput.operationId());
        if(handler==null)return AIcInvocationOutput.failed(Map.of("Type","UNKNOWN_OPERATION","Message",aInput.operationId()));
        try {return AIcInvocationOutput.successful(handler.execute(aInput));}
        catch(AIxOperationCancelled ex){return AIcInvocationOutput.failed(Map.of("Type","OPERATION_CANCELLED","Message",ex.getMessage()));}
        catch(Exception ex){return AIcInvocationOutput.failed(Map.of("Type",ex.getClass().getName(),"Message",Objects.toString(ex.getMessage(),"")));}
    }
}
