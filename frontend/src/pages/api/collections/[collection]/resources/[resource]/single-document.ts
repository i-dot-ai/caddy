import { updateSingleResource } from '@logic/data.ts';

interface EndpointParams {
  request: Request,
  params: Record<string, string | undefined>,
  session?: {
    get: (key: string) => Promise<string | undefined>,
  },
}

export async function PUT({ request, params, session }: EndpointParams) {
  try {
    const { collection: collectionId, resource: resourceId } = params;

    if (!collectionId || !resourceId) {
      return new Response(JSON.stringify({ error: 'Collection ID and Resource ID are required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const body = await request.json();
    const { page_content } = body;

    if (!page_content) {
      return new Response(JSON.stringify({ error: 'page_content is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const authToken = await session?.get('accessToken');
    const { json, error } = await updateSingleResource(collectionId, resourceId, page_content, authToken);

    if (error) {
      return new Response(JSON.stringify({ error }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify(json), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

  } catch(err) {
    console.error('Error updating single resource:', err);
    return new Response(JSON.stringify({ error: 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
