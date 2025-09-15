import type { APIContext } from 'astro';
import { addUser } from '@logic/data.ts';


export async function POST({ request, redirect }: APIContext) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const emailAddress = data.get('emailAddress') || '';
  const role = data.get('role') || 'member';

  await addUser(collectionId, { email: emailAddress, role: role }, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = data.get('user') ? `User <strong>${emailAddress}</strong> updated` : `User <strong>${emailAddress}</strong> added to collection`;

  return redirect(`/collections/${collectionId}#sharing?notification=${encodeURI(notification)}`, 303);

}
