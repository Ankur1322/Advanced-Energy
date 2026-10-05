import { corsHeaders, openAi } from "../_shared/openai.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const { message, context } = await request.json();
    const memoryText = (context?.memories ?? []).map((memory: { content: string }) => `- ${memory.content}`).join("\n");
    const recentText = (context?.recentMessages ?? []).map((item: { role: string; content: string }) => `${item.role}: ${item.content}`).join("\n");
    const result = await openAi("chat/completions", { model: "gpt-4o-mini", messages: [{ role: "system", content: "You are AE Memory, a precise assistant. Use the supplied context when relevant, but never mention internal memory retrieval. Treat memories as potentially stale and ask when uncertain." }, { role: "system", content: `Conversation summary:\n${context?.summary ?? "None"}\nLong-term memories:\n${memoryText || "None"}\nRecent messages:\n${recentText || "None"}` }, { role: "user", content: message }] });
    return new Response(JSON.stringify({ content: result.choices[0].message.content }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Response failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }); }
});