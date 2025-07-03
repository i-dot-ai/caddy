import { deleteFile } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const resourceId = data.get('resource')?.toString() || '';

  await deleteFile(collectionId, resourceId, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect(`/collections/${collectionId}/resources`, 307);

}
