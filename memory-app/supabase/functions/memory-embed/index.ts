import { corsHeaders, openAi } from "../_shared/openai.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  try {
    const { text } = await request.json();
    if (typeof text !== "string" || text.length < 2 || text.length > 8000) return new Response(JSON.stringify({ error: "Invalid text" }), { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    const auth = request.headers.get("Authorization");
    const userClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, { global: { headers: { Authorization: auth ?? "" } } });
    const { data: { user } } = await userClient.auth.getUser();
    if (!user) return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const { data: allowed } = await admin.rpc("consume_embedding_rate_limit", { target_user_id: user.id, max_requests: 60 });
    if (!allowed) return new Response(JSON.stringify({ error: "Embedding rate limit exceeded" }), { status: 429, headers: { ...corsHeaders, "Content-Type": "application/json", "Retry-After": "60" } });
    const result = await openAi("embeddings", { model: "text-embedding-3-small", input: text });
    return new Response(JSON.stringify({ embedding: result.data[0].embedding }), { headers: { ...corsHeaders, "Content-Type": "application/json" } });
  } catch (error) { return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Embedding failed" }), { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }); }
});