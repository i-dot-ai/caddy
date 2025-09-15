import type { APIContext } from 'astro';
import { uploadFile } from '@logic/data.ts';


export async function POST({ request, redirect }: APIContext) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const files = data.getAll('fileUpload1') as File[];

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    await uploadFile(collectionId, formData, request.headers.get('x-amzn-oidc-accesstoken'));
  }

  const notification = files.length === 1 ? `File <strong>${files[0].name}</strong> uploaded` : `<strong>${files.length}</strong> files uploaded`;

  return redirect(`/collections/${collectionId}?notification=${encodeURI(notification)}`, 303);

}
