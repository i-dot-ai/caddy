import 'dotenv/config';
import { parseAuthToken } from './auth.ts';

// Define paths that should be public (no authorisation required)
const PUBLIC_PATHS = [
  '/assets/fonts/',
  '/unauthorised',
  '/api/health',
  '/auth/login',
  '/auth/callback',
  '/auth/logout',
];

export async function onRequest(context, next) {

  const pathname = new URL(context.request.url).pathname;

  // Check if the requested path is public
  if (PUBLIC_PATHS.some((path) => pathname.startsWith(path))) {
    return next();
  }

  try {

    // In production, ALB injects the token. Locally, get from session
    let token = context.request.headers.get('x-amzn-oidc-accesstoken') || await context.session?.get('accessToken');

    if (!token) {
      console.error(`No auth token found in headers when accessing ${pathname}`);
      return context.redirect('/auth/login');
    }

    const parsedToken = await parseAuthToken(token);
    if (!parsedToken?.email) {
      return redirectToUnauthorised(context);
    }

    // Is this user an admin user? Used to determine whether to add analytics. Permissions are handled through the API.
    const adminUsers = process.env.ADMIN_USERS?.split(',') || [];
    await context.session?.set('isAdmin', adminUsers.includes(parsedToken.email));
    
    // Store the validated token for API calls
    await context.session?.set('authToken', token);

    return next();
  } catch(error) {
    console.error('Error authorising token:', error);
    return redirectToUnauthorised(context);
  }
}

function redirectToUnauthorised(context) {
  return context.redirect('/unauthorised');
}
