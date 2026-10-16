package eu.algites.frmw.aac.core.invocation;

import java.util.Map;

/** Normalized invocation outcome; effects may be unknown even when success=false. */
public record AIcInvocationOutput(boolean success, Object result, Map<String,Object> error) {
    public AIcInvocationOutput { error = error == null ? null : Map.copyOf(error); }
    public static AIcInvocationOutput successful(Object value) {return new AIcInvocationOutput(true,value,null);}
    public static AIcInvocationOutput failed(Map<String,Object> error) {return new AIcInvocationOutput(false,null,error);}
}
