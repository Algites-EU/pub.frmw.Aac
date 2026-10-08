from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, Sequence

from ..descriptor.api import AIcConsumerRequirementDescriptor


class AIiCapabilityProfileMatcher(ABC):
    """Select compatible provider binding-qualifier profiles for one consumer requirement.

    Implementations are technology-specific resolution helpers instantiated independently of
    provider runtime instances. Returned indexes refer to the normalized provider profile sequence
    supplied for the exact capability-contract version being negotiated.
    """

    @abstractmethod
    def match_profile_indexes(
        self,
        requirement: AIcConsumerRequirementDescriptor,
        capability_version: int,
        provider_instance_id: str,
        provider_profiles: Sequence[Mapping[str, object]],
        consumer_configuration: Mapping[str, object],
    ) -> Sequence[int]:
        """Return indexes of provider profiles accepted by the consumer for this resolution."""
