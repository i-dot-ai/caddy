import type { APIContext } from 'astro';
import { deleteCollection } from '@logic/data.ts';


export async function POST({ request, redirect }: APIContext) {

  const data = await request.formData();
  const collectionId = data.get('collectionId')?.toString() || '';
  const collectionName = data.get('collectionName')?.toString() || '';

  await deleteCollection(collectionId, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = `Collection <strong>${collectionName}</strong> deleted`;

  return redirect(`/?notification=${encodeURI(notification)}`, 303);

}
