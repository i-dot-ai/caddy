import { updateCollection, addCollection } from '@logic/data.ts'
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {
  
  const data = await request.formData();
  const id = data.get('collection')?.toString() || '';
  const name = data.get('name')?.toString().replaceAll(' ', '-');
  const description = data.get('description')?.toString() || '';

  if (name) {
    if (id) {
      await updateCollection(id, name, description, request.headers.get('x-amzn-oidc-accesstoken'));
    } else {
      await addCollection(name, description, request.headers.get('x-amzn-oidc-accesstoken'));
    }
  }

  return redirect('/', 307);

}
