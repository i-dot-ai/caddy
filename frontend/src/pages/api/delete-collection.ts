import { deleteCollection } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';

  await deleteCollection(collectionId, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect('/', 303);

}
