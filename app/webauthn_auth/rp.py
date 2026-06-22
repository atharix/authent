from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class RPConfig:
    rp_id: str
    rp_name: str
    origins: list[str]


def get_rp_config() -> RPConfig:
    origins = settings.WEBAUTHN_ORIGINS
    if isinstance(origins, str):
        origins = [origins]
    return RPConfig(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        origins=list(origins),
    )
