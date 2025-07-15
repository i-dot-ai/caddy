import { deleteCollection } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collectionId')?.toString() || '';
  const collectionName = data.get('collectionName')?.toString() || '';

  await deleteCollection(collectionId, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = `Collection <strong>${collectionName}</strong> deleted`;

  return redirect(`/?notification=${encodeURI(notification)}`, 303);

}
