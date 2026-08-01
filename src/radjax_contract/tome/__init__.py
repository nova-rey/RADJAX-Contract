"""Tome-centered public contract surface."""

from radjax_contract.tome.compression import (
    TomeCompression,
    TomeCompressionFamily,
    valid_compression_for_payload,
)
from radjax_contract.tome.cover_page import (
    TomeBehavioralSummary,
    TomeContentsSummary,
    TomeCorpusSource,
    TomeCorpusSummary,
    TomeCoverPage,
    TomeCoverPageLoadResult,
    TomeExemplarSummary,
    TomeSplitSummary,
    TomeStudentConsumptionSummary,
    TomeTeacherSummary,
    load_tome_cover_page,
)
from radjax_contract.tome.inspection import (
    TomeConsumptionPlan,
    inspect_tome_for_consumption,
)
from radjax_contract.tome.manifest import TomeManifest, TomeRole
from radjax_contract.tome.payloads import TomePayloadFormat
from radjax_contract.tome.production import (
    ArtifactLocalFingerprintId,
    ArtifactLocalModeId,
    ProductionTomeArtifact,
    ProductionTomeInspection,
    ProductionTomeValidationResult,
    inspect_production_tome,
    load_production_tome,
    validate_production_tome,
)
from radjax_contract.tome.records import (
    TomeRecord,
    TomeRecordLoadResult,
    load_tome_records,
)
from radjax_contract.tome.shards import TomeShard
from radjax_contract.tome.student_consumption import (
    CONSUMPTION_CONTRACT_VERSION,
    PROFILE_ID,
    StudentTomeConsumptionResult,
    student_consumption_contract_root,
    student_consumption_profile_path,
    validate_student_tome_consumption,
)
from radjax_contract.tome.validation import (
    TomeValidationResult,
    validate_tome,
    validate_tome_split_disjointness,
)

__all__ = [
    "CONSUMPTION_CONTRACT_VERSION",
    "PROFILE_ID",
    "ArtifactLocalFingerprintId",
    "ArtifactLocalModeId",
    "ProductionTomeArtifact",
    "ProductionTomeInspection",
    "ProductionTomeValidationResult",
    "StudentTomeConsumptionResult",
    "TomeBehavioralSummary",
    "TomeCompression",
    "TomeCompressionFamily",
    "TomeConsumptionPlan",
    "TomeContentsSummary",
    "TomeCorpusSource",
    "TomeCorpusSummary",
    "TomeCoverPage",
    "TomeCoverPageLoadResult",
    "TomeExemplarSummary",
    "TomeManifest",
    "TomePayloadFormat",
    "TomeRecord",
    "TomeRecordLoadResult",
    "TomeRole",
    "TomeShard",
    "TomeSplitSummary",
    "TomeStudentConsumptionSummary",
    "TomeTeacherSummary",
    "TomeValidationResult",
    "inspect_tome_for_consumption",
    "inspect_production_tome",
    "load_tome_cover_page",
    "load_tome_records",
    "load_production_tome",
    "student_consumption_contract_root",
    "student_consumption_profile_path",
    "valid_compression_for_payload",
    "validate_tome",
    "validate_tome_split_disjointness",
    "validate_production_tome",
    "validate_student_tome_consumption",
]
