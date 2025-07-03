import { removeUser } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const userId = data.get('user')?.toString() || '';

  await removeUser(collectionId, userId, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect(`/collections/${collectionId}/users`, 307);

}
