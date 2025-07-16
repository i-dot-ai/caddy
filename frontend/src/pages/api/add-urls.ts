import { addUrls } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const urlsString = data.get('addUrls')?.toString() || '';

  const urls = urlsString
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line); // remove empty lines

  await addUrls(collectionId, urls, request.headers.get('x-amzn-oidc-accesstoken'));

  return redirect(`/collections/${collectionId}/resources`, 303);

}
