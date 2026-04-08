from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings
from shared_py.bitget.instruments import (
    BitgetInstrumentIdentity,
    MarginAccountMode,
    MarketFamily,
    endpoint_profile_for,
)

ProductType = Literal["USDT-FUTURES", "USDC-FUTURES", "COIN-FUTURES"]

_OPTIONAL_SECRET_FIELDS = (
    "api_key",
    "api_secret",
    "api_passphrase",
    "demo_api_key",
    "demo_api_secret",
    "demo_api_passphrase",
)


class BitgetSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = ()
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = ()

    bitget_api_base_url: HttpUrl = Field(
        default="https://api.bitget.com",
        alias="BITGET_API_BASE_URL",
    )
    bitget_ws_public_url: str = Field(
        default="wss://ws.bitget.com/v2/ws/public",
        alias="BITGET_WS_PUBLIC_URL",
    )
    bitget_ws_private_url: str = Field(
        default="wss://ws.bitget.com/v2/ws/private",
        alias="BITGET_WS_PRIVATE_URL",
    )

    bitget_demo_enabled: bool = Field(default=False, alias="BITGET_DEMO_ENABLED")
    bitget_demo_rest_base_url: HttpUrl = Field(
        default="https://api.bitget.com",
        alias="BITGET_DEMO_REST_BASE_URL",
    )
    bitget_demo_ws_public_url: str = Field(
        default="wss://wspap.bitget.com/v2/ws/public",
        alias="BITGET_DEMO_WS_PUBLIC_URL",
    )
    bitget_demo_ws_private_url: str = Field(
        default="wss://wspap.bitget.com/v2/ws/private",
        alias="BITGET_DEMO_WS_PRIVATE_URL",
    )
    bitget_demo_paptrading_header: str = Field(
        default="1",
        alias="BITGET_DEMO_PAPTRADING_HEADER",
    )
    bitget_rest_locale: str = Field(default="en-US", alias="BITGET_REST_LOCALE")
    bitget_margin_coin: str | None = Field(default=None, alias="BITGET_MARGIN_COIN")
    market_family: MarketFamily | None = Field(
        default=None,
        alias="BITGET_MARKET_FAMILY",
    )
    margin_account_mode: MarginAccountMode | None = Field(
        default=None,
        alias="BITGET_MARGIN_ACCOUNT_MODE",
    )
    bitget_margin_loan_type: str = Field(
        default="normal",
        alias="BITGET_MARGIN_LOAN_TYPE",
    )
    bitget_discovery_symbols_raw: str = Field(
        default="",
        alias="BITGET_DISCOVERY_SYMBOLS",
    )

    product_type: ProductType | None = Field(
        default=None,
        alias="BITGET_PRODUCT_TYPE",
    )
    symbol: str = Field(default="", alias="BITGET_SYMBOL")

    api_key: str | None = Field(default=None, alias="BITGET_API_KEY")
    api_secret: str | None = Field(default=None, alias="BITGET_API_SECRET")
    api_passphrase: str | None = Field(default=None, alias="BITGET_API_PASSPHRASE")

    demo_api_key: str | None = Field(default=None, alias="BITGET_DEMO_API_KEY")
    demo_api_secret: str | None = Field(
        default=None,
        alias="BITGET_DEMO_API_SECRET",
    )
    demo_api_passphrase: str | None = Field(
        default=None,
        alias="BITGET_DEMO_API_PASSPHRASE",
    )
    bitget_relax_credential_isolation: bool = Field(
        default=False,
        alias="BITGET_RELAX_CREDENTIAL_ISOLATION",
        description=(
            "Nur fuer lokale Notfaelle: Demo- und Live-Credentials duerfen parallel in ENV stehen. "
            "In Produktion strikt false lassen."
        ),
    )

    @field_validator("bitget_api_base_url", "bitget_demo_rest_base_url")
    @classmethod
    def _validate_https_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("REST URL muss mit https:// beginnen")
        return value

    @field_validator(
        "bitget_ws_public_url",
        "bitget_ws_private_url",
        "bitget_demo_ws_public_url",
        "bitget_demo_ws_private_url",
        mode="before",
    )
    @classmethod
    def _normalize_ws_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator(
        "bitget_ws_public_url",
        "bitget_ws_private_url",
        "bitget_demo_ws_public_url",
        "bitget_demo_ws_private_url",
    )
    @classmethod
    def _validate_ws_url(cls, value: str) -> str:
        if not value.startswith("wss://"):
            raise ValueError("WebSocket URL muss mit wss:// beginnen")
        return value

    @field_validator("product_type", mode="before")
    @classmethod
    def _normalize_product_type(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("market_family", mode="before")
    @classmethod
    def _normalize_market_family(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("margin_account_mode", mode="before")
    @classmethod
    def _normalize_margin_account_mode(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("bitget_rest_locale", mode="before")
    @classmethod
    def _normalize_locale(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or "en-US"
        return value

    @field_validator("bitget_margin_coin", mode="before")
    @classmethod
    def _normalize_margin_coin(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @field_validator("bitget_margin_loan_type", mode="before")
    @classmethod
    def _normalize_margin_loan_type(cls, value: object) -> object:
        if value is None:
            return "normal"
        normalized = str(value).strip()
        return normalized or "normal"

    @field_validator("bitget_discovery_symbols_raw", mode="before")
    @classmethod
    def _normalize_discovery_symbols(cls, value: object) -> object:
        if value is None:
            return ""
        parts = [part.strip().upper() for part in str(value).split(",") if part.strip()]
        return ",".join(parts)

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator(*_OPTIONAL_SECRET_FIELDS, mode="before")
    @classmethod
    def _empty_secret_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("bitget_demo_paptrading_header", mode="before")
    @classmethod
    def _normalize_paptrading_header(cls, value: object) -> str:
        if value is None:
            return "1"
        normalized = str(value).strip()
        return normalized or "1"

    @field_validator("bitget_demo_paptrading_header")
    @classmethod
    def _validate_paptrading_header(cls, value: str) -> str:
        if value != "1":
            raise ValueError("BITGET_DEMO_PAPTRADING_HEADER muss '1' sein")
        return value

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        if not value:
            return value
        if "_" in value:
            raise ValueError(
                "BITGET_SYMBOL darf in v2 kein '_' enthalten "
                "(Bitget-v2 Spot-/Mix-Symbol, nicht Legacy-Suffix-Form)"
            )
        if not value.isalnum() or not value.isupper():
            raise ValueError(
                "BITGET_SYMBOL muss alphanumerisch und uppercase sein "
                "(Bitget-v2 Symbolformat)"
            )
        return value

    @field_validator("bitget_rest_locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        if value not in ("en-US", "zh-CN"):
            raise ValueError("BITGET_REST_LOCALE muss en-US oder zh-CN sein")
        return value

    @model_validator(mode="after")
    def _validate_demo_mode(self) -> BitgetSettings:
        if self.bitget_demo_enabled:
            if "wspap.bitget.com" not in self.bitget_demo_ws_public_url:
                raise ValueError(
                    "Bei BITGET_DEMO_ENABLED=true muss "
                    "BITGET_DEMO_WS_PUBLIC_URL auf die wspap-Domain zeigen"
                )
            if "wspap.bitget.com" not in self.bitget_demo_ws_private_url:
                raise ValueError(
                    "Bei BITGET_DEMO_ENABLED=true muss "
                    "BITGET_DEMO_WS_PRIVATE_URL auf die wspap-Domain zeigen"
                )
            for label, val in (
                ("BITGET_DEMO_API_KEY", self.demo_api_key),
                ("BITGET_DEMO_API_SECRET", self.demo_api_secret),
                ("BITGET_DEMO_API_PASSPHRASE", self.demo_api_passphrase),
            ):
                if val is None or not str(val).strip():
                    raise ValueError(
                        f"BITGET_DEMO_ENABLED=true verlangt gesetztes {label} "
                        "(Exchange-Sandbox, keine leeren Demo-Credentials)"
                    )
        if self.market_family is None:
            families = self.bitget_universe_market_families_list()
            object.__setattr__(self, "market_family", families[0] if families else "spot")
        if self.market_family == "futures" and self.product_type is None:
            default_product = self.default_futures_product_type()
            if not default_product:
                raise ValueError(
                    "BITGET_PRODUCT_TYPE oder BITGET_FUTURES_DEFAULT_PRODUCT_TYPE erforderlich fuer futures"
                )
            object.__setattr__(self, "product_type", default_product)
        if self.market_family == "spot":
            object.__setattr__(self, "margin_account_mode", "cash")
        if self.market_family == "margin":
            default_margin_mode = self.bitget_margin_default_account_mode or "isolated"
            if self.margin_account_mode in (None, "cash"):
                object.__setattr__(self, "margin_account_mode", default_margin_mode)
        if self.market_family == "futures" and self.margin_account_mode in (None, "cash"):
            object.__setattr__(self, "margin_account_mode", "isolated")
        if not self.symbol:
            derived_symbol = self.default_operational_symbol()
            if not derived_symbol:
                raise ValueError(
                    "BITGET_SYMBOL fehlt und konnte nicht aus Watchlist/Universe/Allowlist abgeleitet werden"
                )
            object.__setattr__(self, "symbol", derived_symbol)
        return self

    @property
    def effective_rest_base_url(self) -> str:
        url = (
            self.bitget_demo_rest_base_url
            if self.bitget_demo_enabled
            else self.bitget_api_base_url
        )
        return str(url).rstrip("/")

    @property
    def effective_ws_public_url(self) -> str:
        return (
            self.bitget_demo_ws_public_url
            if self.bitget_demo_enabled
            else self.bitget_ws_public_url
        )

    @property
    def effective_ws_private_url(self) -> str:
        return (
            self.bitget_demo_ws_private_url
            if self.bitget_demo_enabled
            else self.bitget_ws_private_url
        )

    @property
    def effective_api_key(self) -> str | None:
        return self.demo_api_key if self.bitget_demo_enabled else self.api_key

    @property
    def effective_api_secret(self) -> str | None:
        return self.demo_api_secret if self.bitget_demo_enabled else self.api_secret

    @property
    def effective_api_passphrase(self) -> str | None:
        return self.demo_api_passphrase if self.bitget_demo_enabled else self.api_passphrase

    @property
    def effective_margin_coin(self) -> str:
        if self.market_family != "futures":
            return self.bitget_margin_coin or ""
        if self.bitget_margin_coin:
            return self.bitget_margin_coin
        default_margin_coin = self.default_futures_margin_coin()
        if default_margin_coin:
            return default_margin_coin
        if self.product_type == "USDT-FUTURES":
            return "USDT"
        if self.product_type == "USDC-FUTURES":
            return "USDC"
        raise ValueError(
            "BITGET_MARGIN_COIN muss fuer COIN-FUTURES explizit gesetzt sein"
        )

    @property
    def rest_product_type_param(self) -> str | None:
        if self.market_family != "futures":
            return None
        return self.product_type.lower()

    @property
    def endpoint_profile(self):
        return endpoint_profile_for(
            self.market_family,
            margin_account_mode=self.margin_account_mode,
        )

    @property
    def public_ws_inst_type(self) -> str:
        if self.market_family == "futures":
            return self.product_type
        return self.endpoint_profile.public_ws_inst_type

    @property
    def private_ws_inst_type(self) -> str:
        if self.market_family == "futures":
            return self.product_type
        return self.endpoint_profile.private_ws_inst_type or self.public_ws_inst_type

    @property
    def uses_spot_public_market_data(self) -> bool:
        return bool(self.endpoint_profile.uses_spot_public_market_data)

    @property
    def discovery_symbols(self) -> list[str]:
        raw = [item for item in self.bitget_discovery_symbols_raw.split(",") if item]
        deduped: list[str] = []
        for symbol in [self.symbol, *raw]:
            normalized = str(symbol).strip().upper()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped

    def candle_granularity(self, timeframe: str) -> str:
        return self.endpoint_profile.rest_candle_granularity(timeframe)

    def instrument_identity(
        self,
        *,
        metadata_source: str = "runtime_config",
        metadata_verified: bool = False,
        status: str | None = None,
        base_coin: str | None = None,
        quote_coin: str | None = None,
        settle_coin: str | None = None,
    ) -> BitgetInstrumentIdentity:
        return BitgetInstrumentIdentity(
            market_family=self.market_family,
            symbol=self.symbol,
            product_type=self.product_type if self.market_family == "futures" else None,
            margin_coin=self.bitget_margin_coin,
            margin_account_mode=self.margin_account_mode,
            base_coin=base_coin,
            quote_coin=quote_coin,
            settle_coin=settle_coin,
            public_ws_inst_type=self.public_ws_inst_type,
            private_ws_inst_type=self.private_ws_inst_type,
            metadata_source=metadata_source,
            metadata_verified=metadata_verified,
            status=status,
            supports_funding=self.endpoint_profile.supports_funding,
            supports_open_interest=self.endpoint_profile.supports_open_interest,
            supports_long_short=self.endpoint_profile.supports_long_short,
            supports_shorting=self.endpoint_profile.supports_shorting,
            supports_reduce_only=self.endpoint_profile.supports_reduce_only,
            supports_leverage=self.endpoint_profile.supports_leverage,
            uses_spot_public_market_data=self.endpoint_profile.uses_spot_public_market_data,
        )

    def demo_headers(self) -> dict[str, str]:
        if self.bitget_demo_enabled:
            return {"paptrading": self.bitget_demo_paptrading_header}
        return {}
