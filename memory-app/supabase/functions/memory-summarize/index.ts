import { corsHeaders, openAi } from "../_shared/openai.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const { messages } = await request.json();
    const result = await openAi("chat/completions", { model: "gpt-4o-mini", temperature: 0.1, messages: [{ role: "system", content: "Write a compact, factual conversation summary for future context. Preserve goals, constraints, decisions, unresolved questions, and user preferences. Do not invent details." }, { role: "user", content: JSON.stringify(messages) }] });
    return new Response(JSON.stringify({ summary: result.choices[0].message.content }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Summary failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }); }
});