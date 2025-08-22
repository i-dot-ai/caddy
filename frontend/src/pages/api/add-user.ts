import { addUser } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const emailAddress = data.get('emailAddress') || '';
  const role = data.get('role') || 'member';

  await addUser(collectionId, { email: emailAddress, role: role }, await session?.get('accessToken'));

  const notification = data.get('user') ? `User <strong>${emailAddress}</strong> updated` : `User <strong>${emailAddress}</strong> added to collection`;

  return redirect(`/collections/${collectionId}/users?notification=${encodeURI(notification)}`, 303);

}
