export interface EndpointParams {
  request: Request,
  redirect: (url: string, status?: number) => Response,
}
