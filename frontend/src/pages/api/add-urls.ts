import type { APIContext } from 'astro';
import { addUrls } from '@logic/data.ts';


export async function POST({ request, redirect, url }: APIContext) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const urlsString = data.get('addUrls')?.toString() || '';

  const urls = urlsString
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line); // remove empty lines

  await addUrls(collectionId, urls, request.headers.get('x-amzn-oidc-accesstoken'));

  const isRefresh = url.searchParams.get('refresh') === 'true';
  const notification = `<strong>${urls.length}</strong> URL${urls.length === 1 ? '' : 's'} ${isRefresh ? 'refreshed' : 'added to collection'}`;

  return redirect(`/collections/${collectionId}?notification=${encodeURI(notification)}`, 303);

}
