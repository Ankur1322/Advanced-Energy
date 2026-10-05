import { corsHeaders, openAi } from "../_shared/openai.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const { userMessage, assistantMessage } = await request.json();
    const result = await openAi("chat/completions", { model: "gpt-4o-mini", temperature: 0, response_format: { type: "json_object" }, messages: [{ role: "system", content: "Extract only durable user facts, preferences, entities, or decisions. Ignore greetings, transient requests, and assistant claims. Return JSON: { should_store: boolean, memories: [{ content: string, importance: number, type: fact|preference|entity|decision, metadata?: object }] }. Keep each memory atomic and third-person." }, { role: "user", content: `User: ${userMessage}\nAssistant: ${assistantMessage}` }] });
    return new Response(result.choices[0].message.content, { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Extraction failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }); }
});