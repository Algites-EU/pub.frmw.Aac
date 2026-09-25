import pytest

from algites.frmw.aac.coreimpl.errors import AIxSubinterpreterUnavailableError
from algites.frmw.aac.coreimpl.subinterpreter import AIcSubinterpreterCapabilityEndpoint, subinterpreter_available


def test_profile_feature_detection_matches_runtime():
    if subinterpreter_available():
        endpoint = AIcSubinterpreterCapabilityEndpoint("builtins:repr")
        endpoint.close()
    else:
        with pytest.raises(AIxSubinterpreterUnavailableError):
            AIcSubinterpreterCapabilityEndpoint("builtins:repr")
