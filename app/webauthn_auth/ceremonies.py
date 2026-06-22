"""Thin wrappers over py_webauthn for the four passkey ceremonies.

Each ``build_*`` returns ``(options_dict, challenge_b64url)`` — the options go
to the client, the challenge is persisted and checked back on ``verify_*``.
"""

import json

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .rp import get_rp_config


def build_registration_options(user, exclude_credential_ids):
    rp = get_rp_config()
    options = generate_registration_options(
        rp_id=rp.rp_id,
        rp_name=rp.rp_name,
        user_id=str(user.id).encode(),
        user_name=user.email,
        user_display_name=user.get_full_name() or user.email,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(cid))
            for cid in exclude_credential_ids
        ],
    )
    return json.loads(options_to_json(options)), bytes_to_base64url(options.challenge)


def verify_registration(credential, challenge_b64url):
    rp = get_rp_config()
    return verify_registration_response(
        credential=json.dumps(credential),
        expected_challenge=base64url_to_bytes(challenge_b64url),
        expected_rp_id=rp.rp_id,
        expected_origin=rp.origins,
        require_user_verification=True,
    )


def build_authentication_options():
    rp = get_rp_config()
    options = generate_authentication_options(
        rp_id=rp.rp_id,
        allow_credentials=[],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(options)), bytes_to_base64url(options.challenge)


def verify_authentication(
    credential, challenge_b64url, public_key_b64url, current_sign_count
):
    rp = get_rp_config()
    return verify_authentication_response(
        credential=json.dumps(credential),
        expected_challenge=base64url_to_bytes(challenge_b64url),
        expected_rp_id=rp.rp_id,
        expected_origin=rp.origins,
        credential_public_key=base64url_to_bytes(public_key_b64url),
        credential_current_sign_count=current_sign_count,
        require_user_verification=True,
    )
