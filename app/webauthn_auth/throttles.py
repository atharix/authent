from rest_framework.throttling import AnonRateThrottle


class WebAuthnAuthOptionsThrottle(AnonRateThrottle):
    """Throttle for the unauthenticated passkey challenge endpoint."""

    rate = "30/hour"
    scope = "webauthn_auth_options"


class WebAuthnAuthVerifyThrottle(AnonRateThrottle):
    """Throttle for the unauthenticated passkey login endpoint."""

    rate = "20/hour"
    scope = "webauthn_auth_verify"
