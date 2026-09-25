from eu.algites.frmw.aac.core.errors import AIxAACError

from .aix_binding_resolution_error import AIxBindingResolutionError

class AIxBindingCycleError(AIxBindingResolutionError):
    def __init__(self, cycle: tuple[str, ...]):
        self.cycle = cycle
        super().__init__("provider-instance binding cycle detected: " + " -> ".join(cycle))
