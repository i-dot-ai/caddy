export function GET() {
  return new Response(
    JSON.stringify({
      status: "ok",
    }),
  );
}
