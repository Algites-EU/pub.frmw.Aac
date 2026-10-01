from __future__ import annotations

from typing import Mapping, Sequence

from eu.algites.frmw.aac.core.bindings.api import AIiCapabilityProfileMatcher
from eu.algites.frmw.aac.core.descriptor.api import AIcConsumerRequirementDescriptor


class AIcTestCapabilityProfileMatcher(AIiCapabilityProfileMatcher):
    """Test matcher selecting provider build-output profiles requested by consumer configuration."""

    def match_profile_indexes(
        self,
        requirement: AIcConsumerRequirementDescriptor,
        capability_version: int,
        provider_instance_id: str,
        provider_profiles: Sequence[Mapping[str, object]],
        consumer_configuration: Mapping[str, object],
    ) -> Sequence[int]:
        wanted_outputs = set(consumer_configuration.get("WantedOutputs", ()))
        return tuple(
            index
            for index, profile in enumerate(provider_profiles)
            if profile.get("BuildOutputType") in wanted_outputs
        )
