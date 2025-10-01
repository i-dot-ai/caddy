import { removeUser } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const userId = data.get('user')?.toString() || '';
  const emailAddress = data.get('emailAddress')?.toString() || '';

  await removeUser(collectionId, userId, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = `User <strong>${emailAddress}</strong> removed from collection`;

  return redirect(`/collections/${collectionId}#sharing?notification=${encodeURI(notification)}`, 303);

}
