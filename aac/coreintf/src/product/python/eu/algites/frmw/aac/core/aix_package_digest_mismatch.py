from .aix_package_management_error import AIxPackageManagementError

class AIxPackageDigestMismatch(AIxPackageManagementError):
    """Downloaded or copied package bytes do not match the expected digest."""
