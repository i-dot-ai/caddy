import { updateCollection, addCollection } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const id = data.get('collection')?.toString() || '';
  const name = data.get('name')?.toString();
  const description = data.get('description')?.toString() || '';

  // Get auth token from ALB header (production) or session (local)
  const authToken = await session?.get('accessToken');

  let notification = '';
  if (name) {
    notification = `Collection <strong>${name}</strong> `;
    if (id) {
      await updateCollection(id, name, description, authToken);
      notification += 'updated';
    } else {
      await addCollection(name, description, authToken);
      notification += 'created';
    }
  }

  return redirect(`/?notification=${encodeURI(notification)}`, 303);

}
