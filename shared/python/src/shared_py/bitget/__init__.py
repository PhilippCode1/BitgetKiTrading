from .catalog import (
    BitgetInstrumentCatalog,
    InstrumentCatalogUnavailableError,
    UnknownInstrumentError,
)
from .config import BitgetSettings, ProductType
from .ws_canonical import BitgetWsCanonicalEvent, infer_ws_domain
from .discovery import BitgetMarketDiscoveryClient
from .http import (
    build_private_rest_headers,
    build_query_string,
    build_rest_headers,
    build_signature_payload,
    canonical_json_body,
    sign_hmac_sha256_base64,
)
from .instruments import (
    BitgetInstrumentCatalogEntry,
    BitgetInstrumentCatalogSnapshot,
    BitgetEndpointProfile,
    BitgetInstrumentIdentity,
    BitgetMarketCapabilityMatrixRow,
    CatalogSnapshotStatus,
    MarginAccountMode,
    MARKET_UNIVERSE_SCHEMA_VERSION,
    MarketFamily,
    build_capability_matrix,
    endpoint_profile_for,
    market_category_key,
    trading_status_allows_subscription,
    trading_status_allows_trading,
)
from .metadata import (
    BitgetInstrumentMetadataService,
    BitgetInstrumentResolvedMetadata,
    InstrumentSessionState,
    MetadataHealthStatus,
    OrderPreflightResult,
)

__all__ = [
    "BitgetInstrumentCatalog",
    "BitgetInstrumentCatalogEntry",
    "BitgetInstrumentCatalogSnapshot",
    "BitgetInstrumentMetadataService",
    "BitgetInstrumentResolvedMetadata",
    "BitgetMarketCapabilityMatrixRow",
    "BitgetSettings",
    "BitgetWsCanonicalEvent",
    "BitgetMarketDiscoveryClient",
    "BitgetEndpointProfile",
    "BitgetInstrumentIdentity",
    "CatalogSnapshotStatus",
    "MARKET_UNIVERSE_SCHEMA_VERSION",
    "InstrumentCatalogUnavailableError",
    "InstrumentSessionState",
    "MarketFamily",
    "MarginAccountMode",
    "MetadataHealthStatus",
    "OrderPreflightResult",
    "ProductType",
    "UnknownInstrumentError",
    "build_private_rest_headers",
    "build_query_string",
    "build_rest_headers",
    "build_signature_payload",
    "build_capability_matrix",
    "canonical_json_body",
    "endpoint_profile_for",
    "market_category_key",
    "sign_hmac_sha256_base64",
    "trading_status_allows_subscription",
    "trading_status_allows_trading",
]
