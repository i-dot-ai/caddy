import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from i_dot_ai_utilities.logging.structured_logger import StructuredLogger
from pydantic import EmailStr

from api.environment import config


def __convert_to_pem_public_key(key_base64: str) -> RSAPublicKey:
    """
    Convert Base64 public key to PEM format.
    """
    public_key_pem = (
        f"-----BEGIN PUBLIC KEY-----\n{key_base64}\n-----END PUBLIC KEY-----"
    )

    public_key = load_pem_public_key(public_key_pem.encode(), backend=default_backend())
    return public_key


def __get_decoded_jwt(
    jwt_token: str, verify_signature: bool, logger: StructuredLogger
) -> dict:
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
            audience=config.oidc_audience,
            issuer=config.oidc_issuer if verify_signature else None,
            options={
                "verify_signature": verify_signature,
                "verify_exp": verify_signature,
                "verify_iss": verify_signature and config.oidc_issuer is not None,
            },
        )
    except jwt.ExpiredSignatureError:
        logger.info("User's authentication token has expired.")
        raise
    except jwt.InvalidTokenError:
        logger.exception("Invalid JWT")
        raise
    except Exception:
        logger.exception("Unhanded decoding error")
        raise


def get_authorised_user(auth_header: str, logger: StructuredLogger) -> EmailStr | None:
    """
    Takes an OIDC JWT (auth token) as input and returns the user's email address.
    Use this function to identify the logged-in user from any OIDC provider (Keycloak, Dex, Auth0, etc.).
    Also validates that the token has come from the configured OIDC provider for security reasons. 
    Validation should always be true unless running locally.
    """

    if auth_header is None:
        raise Exception("No auth token provided to parse.")

    if auth_header.startswith("Bearer "):
        auth_header = auth_header.replace("Bearer ", "")

    # Only disable JWT verification for local development and testing
    verify_jwt_source = config.env not in ("LOCAL", "TEST")
    token_content = __get_decoded_jwt(auth_header, verify_jwt_source, logger)

    email = token_content.get("email")
    if not email:
        error_msg = "No email found in token"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return email
