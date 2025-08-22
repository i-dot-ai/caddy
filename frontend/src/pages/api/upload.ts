import { uploadFile } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect, session }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const files = data.getAll('fileUpload1') as File[];

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    await uploadFile(collectionId, formData, await session?.get('accessToken'));
  }

  const notification = files.length === 1 ? `File <strong>${files[0].name}</strong> uploaded` : `<strong>${files.length}</strong> files uploaded`;

  return redirect(`/collections/${collectionId}/resources?notification=${encodeURI(notification)}`, 303);

}
