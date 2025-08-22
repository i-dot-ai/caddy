import { addUrls } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const urlsString = data.get('addUrls')?.toString() || '';

  const urls = urlsString
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line); // remove empty lines

  await addUrls(collectionId, urls, await session?.get('accessToken'));

  const notification = `<strong>${urls.length}</strong> URL${urls.length === 1 ? '' : 's'} added to collection`;

  return redirect(`/collections/${collectionId}/resources?notification=${encodeURI(notification)}`, 303);

}
