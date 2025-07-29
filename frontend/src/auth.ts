import 'dotenv/config';
import { jwtVerify, decodeJwt, errors, importSPKI } from 'jose';


export async function parseAuthToken(header: string) {
  if (!header) {
    console.error('No auth token provided to parse');
    return null;
  }

  const tokenContent = await getDecodedJwt(header, false);
  if (!tokenContent) {
    return null;
  }

  const email = tokenContent.email;
  if (!email) {
    console.error('No email found in token');
    return null;
  }

  const realmAccess = tokenContent.realm_access;
  if (!realmAccess) {
    console.error('No realm access information found in token');
    return null;
  }

  const roles = tokenContent.realm_access.roles || [];

  return {
    email,
    roles,
  };
}

async function getDecodedJwt(header: string, verifyJwtSource: boolean) {
  let decodedToken = null;

  try {
    if (verifyJwtSource) {
      const publicKeyEncoded = process.env.AUTH_PROVIDER_PUBLIC_KEY!; // This is passed into the environment by ECS
      const pemPublicKey = convertToPemPublicKey(publicKeyEncoded);
      const publicKey = await importSPKI(pemPublicKey, 'RS256');

      try {
        // Verify with signature
        const { payload } = await jwtVerify(header, publicKey, {
          algorithms: ['RS256'],
          audience: 'account',
        });

        decodedToken = payload;
      } catch(error) {
        if (error instanceof errors.JWTExpired) {
          console.error('JWT has expired:', error.message);
          return null;
        } else if (error instanceof errors.JWTInvalid) {
          console.error('Malformed JWT:', error.message);
          return null;
        }
        console.error('Unexpected JWT verification error:', error);
        return null;
      }
    } else {
      // Decode without verification
      try {
        decodedToken = decodeJwt(header);
      } catch(error) {
        console.error('Malformed JWT during decoding:', error);
        return null;
      }
    }
    return decodedToken;
  } catch(error) {
    console.error('Unexpected error in getDecodedJwt:', error);
    return null;
  }
}

function convertToPemPublicKey(keyBase64: string): string {
  return `-----BEGIN PUBLIC KEY-----\n${keyBase64}\n-----END PUBLIC KEY-----`;
}

/*
 *export async function getServerSideDecodedToken() {
 *  if (process.env.ENVIRONMENT === "local" || process.env.ENVIRONMENT === "test") {
 *    return null;
 *  }
 *
 *  const sessionHeaders = await headers();
 *  const token = sessionHeaders.get("x-amzn-oidc-accesstoken");
 *
 *  if (!token) {
 *    return null;
 *  }
 *
 *  const tokenContent = getDecodedJwt(token, true);
 *  return tokenContent || null;
 *}
 */
