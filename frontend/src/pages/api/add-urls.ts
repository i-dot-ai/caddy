import { addUrls } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {
  
  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const urls = data.get('addUrls')?.toString() || '';

  const formData = new FormData();
  formData.append('urls', urls);

  await addUrls(collectionId, formData, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect(`/collections/${collectionId}/resources`, 307);

}
