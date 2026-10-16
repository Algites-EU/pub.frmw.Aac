package eu.algites.frmw.aac.core.invocation;

public class AIxOperationCancelled extends RuntimeException {
    private final Object stateResult;
    private final boolean hasStateResult;
    public AIxOperationCancelled(String aMessage){this(aMessage,null,false);}
    public AIxOperationCancelled(String aMessage,Object aStateResult,boolean aHasStateResult){
        super(aMessage);stateResult=aStateResult;hasStateResult=aHasStateResult;
    }
    public boolean hasStateResult(){return hasStateResult;}
    public Object getStateResult(){return stateResult;}
}
