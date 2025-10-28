from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List


@dataclass(frozen=True)
class AppSettings:
    api_key: str | None
    cors_origins: List[str]
    default_tax_rate: float


def _split_origins(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> AppSettings:
    api_key = os.getenv("ESTIMATE_AUTOMATION_API_KEY") or None
    cors_origins = _split_origins(os.getenv("ESTIMATE_AUTOMATION_CORS_ORIGINS"))
    tax_rate = float(os.getenv("ESTIMATE_AUTOMATION_DEFAULT_TAX_RATE", "0.1"))
    return AppSettings(api_key=api_key, cors_origins=cors_origins, default_tax_rate=tax_rate)
