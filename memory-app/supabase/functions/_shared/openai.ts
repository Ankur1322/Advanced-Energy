const OPENAI_URL = "https://api.openai.com/v1";

export async function openAi(path: string, body: unknown) {
  const response = await fetch(`${OPENAI_URL}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${Deno.env.get("OPENAI_API_KEY")}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`OpenAI request failed (${response.status})`);
  return response.json();
}

export const corsHeaders = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type" };