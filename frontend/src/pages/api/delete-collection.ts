import { deleteCollection } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collectionId')?.toString() || '';
  const collectionName = data.get('collectionName')?.toString() || '';

  await deleteCollection(collectionId, await session?.get('accessToken'));

  const notification = `Collection <strong>${collectionName}</strong> deleted`;

  return redirect(`/?notification=${encodeURI(notification)}`, 303);

}
