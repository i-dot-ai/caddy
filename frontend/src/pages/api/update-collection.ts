import type { APIContext } from 'astro';
import { updateCollection, addCollection } from '@logic/data.ts';


export async function POST({ request, redirect }: APIContext) {

  const data = await request.formData();
  const id = data.get('collection')?.toString() || '';
  const name = data.get('name')?.toString();
  const description = data.get('description')?.toString() || '';
  const prompt = data.get('prompt')?.toString() || '';

  if (name) {
    // let notification = `Collection <strong>${name}</strong> `;
    if (id) {
      await updateCollection(id, name, description, prompt, request.headers.get('x-amzn-oidc-accesstoken'));
      // notification += 'updated';
      return redirect(`/collections/${id}#settings`, 303);
    } else {
      const data = await addCollection(name, description, prompt, request.headers.get('x-amzn-oidc-accesstoken'));
      // notification += 'created';
      return redirect(`/collections/${data.id}`, 303);
    }
  }


}
