import { uploadFile } from '@logic/data.ts';
import type { EndpointParams } from './types';


export async function POST({ request, redirect }: EndpointParams) {

  const data = await request.formData();
  const collectionId = data.get('collection')?.toString() || '';
  const files = data.getAll('fileUpload1') as File[];

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file, file.name);
    await uploadFile(collectionId, formData, request.headers.get('x-amzn-oidc-accesstoken'));
  }

  return redirect(`/collections/${collectionId}/resources`, 307);

}
