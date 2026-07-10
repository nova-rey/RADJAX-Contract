from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from radjax_contract.tome.production.models import ProductionTomeCoverPage
from radjax_contract.tome.production.validation import validate_production_tome

_KNOWN_SURFACE_KINDS = frozenset({"fingerprint_corridor", "selected_exemplar"})


@dataclass(frozen=True)
class ProductionTomeInspection:
    structurally_valid: bool
    consumable: bool
    known_surfaces: tuple[str, ...]
    unknown_surfaces: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    unsupported_required_capabilities: tuple[str, ...]
    unknown_required_roles: tuple[str, ...]
    recommended_passes: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def inspect_production_tome(
    tome_dir: str | Path,
    *,
    supported_capabilities: Iterable[str] = (),
) -> ProductionTomeInspection:
    validation = validate_production_tome(tome_dir)
    if validation.artifact is None:
        return ProductionTomeInspection(
            structurally_valid=False,
            consumable=False,
            known_surfaces=(),
            unknown_surfaces=(),
            required_capabilities=(),
            unsupported_required_capabilities=(),
            unknown_required_roles=(),
            recommended_passes=(),
            blockers=validation.blockers,
            warnings=validation.warnings,
        )

    cover = validation.artifact.cover_page
    known = tuple(
        surface.surface_id
        for surface in cover.surfaces
        if surface.surface_kind in _KNOWN_SURFACE_KINDS
    )
    unknown = tuple(
        surface.surface_id
        for surface in cover.surfaces
        if surface.surface_kind not in _KNOWN_SURFACE_KINDS
    )
    required_capabilities = _required_capabilities(cover)
    supported = frozenset(str(item) for item in supported_capabilities)
    unsupported = tuple(
        capability
        for capability in required_capabilities
        if capability not in supported
    )
    unknown_required_roles = tuple(
        sorted(
            {
                role
                for surface in cover.surfaces
                for role in surface.required_content_roles
                if any(
                    ref.role == role and not ref.known_role for ref in cover.contents
                )
            }
        )
    )
    structurally_valid = validation.ok
    consumable = structurally_valid and not unsupported and not unknown_required_roles
    return ProductionTomeInspection(
        structurally_valid=structurally_valid,
        consumable=consumable,
        known_surfaces=known,
        unknown_surfaces=unknown,
        required_capabilities=required_capabilities,
        unsupported_required_capabilities=unsupported,
        unknown_required_roles=unknown_required_roles,
        recommended_passes=tuple(
            training_pass.pass_id
            for training_pass in cover.recommended_training_plan.passes
        ),
        blockers=validation.blockers,
        warnings=validation.warnings,
    )


def _required_capabilities(cover: ProductionTomeCoverPage) -> tuple[str, ...]:
    surface_by_id = {surface.surface_id: surface for surface in cover.surfaces}
    required: set[str] = set()
    for training_pass in cover.recommended_training_plan.passes:
        required.update(training_pass.required_capabilities)
        surface = surface_by_id.get(training_pass.surface_id)
        if surface is not None:
            required.update(surface.required_capabilities)
    return tuple(sorted(required))
