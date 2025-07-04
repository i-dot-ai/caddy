import { addUser } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const emailAddress = data.get('emailAddress') || '';
  const role = data.get('role') || 'member';

  await addUser(collectionId, { email: emailAddress, role: role }, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect(`/collections/${collectionId}/users`, 307);

}
