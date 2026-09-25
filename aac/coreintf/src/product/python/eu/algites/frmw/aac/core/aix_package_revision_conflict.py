from .aix_package_management_error import AIxPackageManagementError

class AIxPackageRevisionConflict(AIxPackageManagementError):
    """Requested package selection/lock cannot be reconciled deterministically."""
