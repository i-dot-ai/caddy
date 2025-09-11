import { updateCollection, addCollection } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const id = data.get('collection')?.toString() || '';
  const name = data.get('name')?.toString();
  const description = data.get('description')?.toString() || '';
  const prompt = data.get('prompt')?.toString() || '';

  let notification = '';
  if (name) {
    notification = `Collection <strong>${name}</strong> `;
    if (id) {
      await updateCollection(id, name, description, prompt, request.headers.get('x-amzn-oidc-accesstoken'));
      notification += 'updated';
    } else {
      await addCollection(name, description, prompt, request.headers.get('x-amzn-oidc-accesstoken'));
      notification += 'created';
    }
  }

  return redirect(`/?notification=${encodeURI(notification)}`, 303);

}
