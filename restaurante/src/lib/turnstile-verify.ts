/**
 * Verificación servidor de Cloudflare Turnstile (opcional en reservas web).
 * https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
 */
export function clientIpFromRequest(req: Request): string | undefined {
  const h = req.headers;
  return (
    h.get("cf-connecting-ip")?.trim() ||
    h.get("x-real-ip")?.trim() ||
    h.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    undefined
  );
}

export async function verifyTurnstileToken(
  secret: string,
  token: string,
  remoteip?: string,
): Promise<boolean> {
  const body = new URLSearchParams();
  body.set("secret", secret);
  body.set("response", token.trim());
  if (remoteip) {
    body.set("remoteip", remoteip);
  }
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
    signal: AbortSignal.timeout(12_000),
  });
  if (!r.ok) {
    return false;
  }
  const data = (await r.json().catch(() => null)) as { success?: boolean } | null;
  return Boolean(data?.success);
}

export function turnstileConfigured(): boolean {
  const site = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();
  const secret = (process.env.TURNSTILE_SECRET_KEY || "").trim();
  return Boolean(site && secret);
}
