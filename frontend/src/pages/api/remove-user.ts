import { removeUser } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const userId = data.get('user')?.toString() || '';
  const emailAddress = data.get('emailAddress')?.toString() || '';

  await removeUser(collectionId, userId, await session?.get('accessToken'));

  const notification = `User <strong>${emailAddress}</strong> removed from collection`;

  return redirect(`/collections/${collectionId}/users?notification=${encodeURI(notification)}`, 303);

}
