package eu.algites.frmw.aac.core.invocation;

import java.util.Map;

public record AIcOperationFailure(String errorCode, String exceptionType,
        String systemMessage, String userMessage, String stackTrace, Map<String,Object> details) {
    public AIcOperationFailure {details=details==null?Map.of():Map.copyOf(details);}
}
