import { deleteFile } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const resourceId = data.get('resourceId')?.toString() || '';
  const resourceName = data.get('resourceName')?.toString() || '';

  await deleteFile(collectionId, resourceId, request.headers.get('x-amzn-oidc-accesstoken'));

  const notification = `Resource <strong>${resourceName}</strong> deleted`;

  return redirect(`/collections/${collectionId}/resources?notification=${encodeURI(notification)}`, 303);

}
