import 'dotenv/config';

const backendHost = process.env['BACKEND_HOST'];
if (!backendHost) {
  throw new Error('BACKEND_HOST env var not set');
}


const makeRequest = async(endPoint: string, authToken: string | null, options?: { method?: 'GET' | 'POST' | 'DELETE' | 'PUT'; body?: string | FormData; contentType?: string }) => {

  let response;
  let error = '';
  const headers: { [key: string]: string } = {
    'x-external-access-token': process.env['BACKEND_TOKEN'] || '',
    Authorization: authToken || '',
  };
  if (options?.contentType) {
    headers['Content-Type'] = options?.contentType;
  }

  try {
    response = await fetch(`${backendHost}${endPoint}`, {
      method: options?.method || 'GET',
      headers: headers,
      body: options?.body,
    });
    if (!response.ok) {
      error = 'Error connecting to the backend: ';
      error += response.status === 403 ? 'You do not have sufficient permissions.' : `HTTP ${response.status}.`;
    }
  } catch(err) {
    error = `Error connecting to the backend: ${err}`;
  }

  let json: { [key: string]: unknown } = {};
  if (response) {
    try {
      json = await response.json();
    } catch(err) {
      console.log(error, err);
    }
  }
  return { json, error };
};

export enum CollectionPermission {
  VIEW = 'VIEW',
  EDIT = 'EDIT',
  DELETE = 'DELETE',
  MANAGE_USERS = 'MANAGE_USERS',
  MANAGE_RESOURCES = 'MANAGE_RESOURCES',
}

interface Collection {
  id: string,
  name: string,
  description: string,
  created_at: Date,
  permissions: CollectionPermission[],
}

interface Collections {
  collections: Collection[],
  is_admin: boolean,
}

export const getCollections = async(authToken: string | null) => {
  const { json, error } = await makeRequest('/collections', authToken);
  const collectionsData = (json as unknown as Collections) || { collections: [], is_admin: false };

  return { collectionsData, error };
};


export const getCollection = async(collectionId: string, authToken: string | null) => {
  let { collectionsData, error } = await getCollections(authToken); /* eslint prefer-const: "off" */
  const collection = collectionsData.collections.find((item: Collection) => item.id === collectionId) as Collection;
  if (typeof collection === 'undefined') {
    error = 'Collection not found';
  }
  return { collection, error };
};


export const updateCollection = async(collectionId: string, name: string, description: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}`, authToken, {
    method: 'PUT',
    body: JSON.stringify({
      name: name,
      description: description,
    }),
    contentType: 'application/json',
  });
  return json;
};


export const addCollection = async(name: string, description: string, authToken: string | null) => {
  const { json } = await makeRequest('/collections', authToken, {
    method: 'POST',
    body: JSON.stringify({
      name: name,
      description: description,
    }),
    contentType: 'application/json',
  });
  return json;
};


export const deleteCollection = async(collectionId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}`, authToken, {
    method: 'DELETE',
  });
  return json;
};

export enum ResourcePermission {
  VIEW = 'VIEW',
  READ_CONTENTS = 'READ_CONTENTS',
  DELETE = 'DELETE',
}

export interface ResourceDetail {
  id: string,
  url?: string,
  filename?: string,
  content_type: string,
  created_at?: string,
  process_error?: string,
  permissions: ResourcePermission[],
}

interface ResourceList {
  total: number,
  page_size: number,
  page: number,
  resources: ResourceDetail[],
}
export const getResources = async(collectionId: string, page: number, itemsPerPage: number, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources?page=${page}&page_size=${itemsPerPage}`, authToken);
  return json as unknown as ResourceList;
};


export const getResourceDetails = async(collectionId: string, resourceId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources/${resourceId}`, authToken);
  return json as unknown as ResourceDetail;
};


interface ResourceFragment {
  documents?: {
    page_content: string,
  }[],
}
export const getResourceFragments = async(collectionId: string, resourceId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources/${resourceId}/documents`, authToken);
  return (json as ResourceFragment).documents;
};


export const uploadFile = async(collectionId: string, body: FormData, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources`, authToken, {
    method: 'POST',
    body: body,
  });
  return json;
};


export const addUrls = async(collectionId: string, urls: string[], authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources/urls`, authToken, {
    method: 'POST',
    body: JSON.stringify(urls),
    contentType: 'application/json',
  });
  return json;
};


export const deleteFile = async(collectionId: string, resourceId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/resources/${resourceId}`, authToken, {
    method: 'DELETE',
  });
  return json;
};


interface User {
  created_at: string,
  user_id: string,
  collection_id: string,
  user_email: string,
  role: 'member' | 'manager',
}
export const getUsers = async(collectionId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/users?page_size=1000`, authToken);
  return json.user_roles as User[];
};


export const addUser = async(collectionId: string, body: FormData, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/users`, authToken, {
    method: 'POST',
    body: JSON.stringify(body),
    contentType: 'application/json',
  });
  return json;
};


export const removeUser = async(collectionId: string, userId: string, authToken: string | null) => {
  const { json } = await makeRequest(`/collections/${collectionId}/users/${userId}`, authToken, {
    method: 'DELETE',
  });
  return json;
};
