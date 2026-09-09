"""Expose typed adapters for externally maintained data sources."""

from veritycx.data_sources.tau3 import (
    BankingDataState,
    DatabaseCollectionShape,
    GitCheckoutState,
    InspectionSummary,
    ResolvedTau3Paths,
    SetupResult,
    Tau3Config,
    Tau3OperationError,
    Tau3PathConfig,
    Tau3UpstreamConfig,
    format_tau3_diagnostic,
    inspect_tau3_data,
    load_tau3_config,
    resolve_tau3_paths,
    setup_tau3_data,
)

__all__ = [
    "BankingDataState",
    "DatabaseCollectionShape",
    "GitCheckoutState",
    "InspectionSummary",
    "ResolvedTau3Paths",
    "SetupResult",
    "Tau3Config",
    "Tau3OperationError",
    "Tau3PathConfig",
    "Tau3UpstreamConfig",
    "format_tau3_diagnostic",
    "inspect_tau3_data",
    "load_tau3_config",
    "resolve_tau3_paths",
    "setup_tau3_data",
]
