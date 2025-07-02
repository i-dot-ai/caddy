import logging

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import EmailStr

from api.environment import config

logger = logging.getLogger(__name__)


def __convert_to_pem_public_key(key_base64: str) -> RSAPublicKey:
    """
    Convert Base64 public key to PEM format.
    """
    public_key_pem = (
        f"-----BEGIN PUBLIC KEY-----\n{key_base64}\n-----END PUBLIC KEY-----"
    )

    public_key = load_pem_public_key(public_key_pem.encode(), backend=default_backend())
    return public_key


def __get_decoded_jwt(jwt_token: str, verify_signature: bool) -> dict:
    """
    Get JWT payload, optionally validating the JWT signature against a known public key.
    """
    try:
        if verify_signature:
            public_key_encoded = (
                config.auth_provider_public_key
            )  # This is passed into the environment by ECS
            pem_public_key = __convert_to_pem_public_key(public_key_encoded)
        else:
            pem_public_key = None
        return jwt.decode(
            jwt_token,
            pem_public_key,
            algorithms=["RS256"],
            audience="account",
            options={
                "verify_signature": verify_signature,
                "verify_exp": verify_signature,
            },
        )
    except jwt.ExpiredSignatureError:
        logger.info("User's authentication token has expired.")
        raise
    except jwt.InvalidTokenError as e:
        logger.exception(f"Invalid JWT: {e}")
        raise jwt.InvalidTokenError(f"Invalid authentication token: {e}")
    except Exception as e:
        logger.exception(f"Unhanded decoding error: {e}")
        raise Exception(f"Unhanded decoding error: {e}")


def get_authorised_user(auth_header: str) -> EmailStr | None:
    """
    Takes a Keycloak JWT (auth token) as input and returns the user's email address and associated roles.
    Use this function to identify the logged-in user, and which roles they are assigned by Keycloak.
    Also validates that the token has come from Keycloak for security reasons. Validation should always be true unless running locally.
    """

    if auth_header is None:
        raise Exception("No auth token provided to parse.")

    if auth_header.startswith("Bearer "):
        auth_header = auth_header.replace("Bearer ", "")

    verify_jwt_source = not config.disable_auth_signature_verification
    token_content = __get_decoded_jwt(auth_header, verify_jwt_source)

    email = token_content.get("email")
    if not email:
        error_msg = "No email found in token"
        logger.error(error_msg)
        raise ValueError(error_msg)

    realm_access = token_content.get("realm_access")
    if not realm_access:
        error_msg = "Realm access not found in token"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # We have decided not to check Keycloak roles (any Keycloak role is allowed)

    return email
