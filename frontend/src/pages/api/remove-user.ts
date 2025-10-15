import type { APIContext } from 'astro';
import { removeUser } from '@logic/data.ts';


export async function POST({ request, redirect }: APIContext) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const userId = data.get('user')?.toString() || '';
  const emailAddress = data.get('emailAddress')?.toString() || '';

  await removeUser(collectionId, userId, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = `User <strong>${emailAddress}</strong> removed from collection`;

  return redirect(`/collections/${collectionId}?notification=${encodeURI(notification)}#sharing`, 303);

}
