export function GET () {
  return new Response(
    JSON.stringify({
      status: 'ok',
      sha: process.env.GIT_SHA || null,
    }),
  );
}
