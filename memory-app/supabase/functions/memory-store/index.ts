import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { corsHeaders } from "../_shared/openai.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const auth = request.headers.get("Authorization");
    const client = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth ?? "" } } });
    const { data: { user } } = await client.auth.getUser();
    if (!user) return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    const { content, importance, metadata, conversationId } = await request.json();
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const embedResponse = await fetch(`${Deno.env.get("SUPABASE_URL")}/functions/v1/memory-embed`, { method: "POST", headers: { Authorization: `Bearer ${Deno.env.get("SUPABASE_ANON_KEY")}`, "Content-Type": "application/json" }, body: JSON.stringify({ text: content }) });
    const { embedding } = await embedResponse.json();
    const { data, error } = await admin.from("memories").insert({ user_id: user.id, conversation_id: conversationId ?? null, content, embedding, importance, metadata }).select().single();
    if (error) throw error;
    return new Response(JSON.stringify(data), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Memory write failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }); }
});