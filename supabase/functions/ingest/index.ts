// Edge Function "ingest": recebe a leitura (vinda do EMQX via HTTPS),
// autentica pelo header x-ingest-key, valida o contrato e grava em public.readings.
// Respostas: 201 inserido | 200 duplicata | 400 contrato inválido | 401 não autorizado.
import { createClient } from "npm:@supabase/supabase-js@2";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// Chave com permissão de escrita: secret key nova ou service_role legada.
function chaveAdmin(): string {
  try {
    const keys = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") ?? "{}");
    if (keys.default) return keys.default;
  } catch (_) { /* usa a legada */ }
  return Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
}

// Comparação em tempo constante (evita vazar o segredo por tempo de resposta).
function iguais(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

const num = (v: unknown) => typeof v === "number" && Number.isFinite(v);

Deno.serve(async (req) => {
  if (req.method !== "POST") return json(405, { error: "method_not_allowed" });

  const esperado = Deno.env.get("INGEST_KEY") ?? "";
  if (!esperado) return json(500, { error: "server_misconfigured" });
  const recebido = req.headers.get("x-ingest-key") ?? "";
  if (!iguais(recebido, esperado)) return json(401, { error: "unauthorized" });

  let corpo: any;
  try {
    corpo = await req.json();
  } catch (_) {
    return json(400, { error: "invalid_json" });
  }

  // O EMQX envia { topic, reading: {...} }. Aceita também o objeto simples (teste manual).
  let r = corpo?.reading ?? corpo;
  if (typeof r === "string") {
    try { r = JSON.parse(r); } catch (_) { /* cai na validação */ }
  }

  const erros: string[] = [];
  if (!r || typeof r !== "object") erros.push("reading ausente");
  else {
    if (typeof r.device_id !== "string" || !/^[a-z0-9_-]{1,40}$/.test(r.device_id))
      erros.push("device_id inválido");
    if (typeof r.message_id !== "string" || r.message_id.trim().length < 1 || r.message_id.length > 120)
      erros.push("message_id inválido");
    if (!num(r.level_percent) || r.level_percent < 0 || r.level_percent > 100)
      erros.push("level_percent fora de 0..100");
    if (!num(r.distance_cm) || r.distance_cm < 2 || r.distance_cm > 400)
      erros.push("distance_cm fora de 2..400");
    if (typeof r.alert !== "boolean") erros.push("alert deve ser booleano");
    if (r.metric !== undefined && (typeof r.metric !== "string" || r.metric.length > 40))
      erros.push("metric inválida");
    if (r.unit !== undefined && (typeof r.unit !== "string" || r.unit.length > 10))
      erros.push("unit inválida");
  }
  if (erros.length) return json(400, { error: "invalid_contract", detail: erros });

  const linha = {
    device_id: r.device_id,
    message_id: r.message_id,
    metric: r.metric ?? "water_level",
    unit: r.unit ?? "%",
    level_percent: r.level_percent,
    distance_cm: r.distance_cm,
    alert: r.alert,
  };

  const supabase = createClient(Deno.env.get("SUPABASE_URL")!, chaveAdmin(), {
    auth: { persistSession: false },
  });

  // ignoreDuplicates: se (device_id, message_id) já existe, nada é inserido -> inserted=false.
  const { data, error } = await supabase
    .from("readings")
    .upsert(linha, { onConflict: "device_id,message_id", ignoreDuplicates: true })
    .select();

  if (error) return json(500, { error: "database_error", detail: error.message });
  const inserted = (data?.length ?? 0) > 0;
  return json(inserted ? 201 : 200, { ok: true, inserted });
});
