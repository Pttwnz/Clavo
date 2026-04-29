import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const TABLET_COOKIE = "clavo_tablet";

const MAX_AGE_SEC = 8 * 60 * 60;

function secret(): string {
  const s = process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET;
  if (!s) throw new Error("AUTH_SECRET (o NEXTAUTH_SECRET) es obligatorio para la sesión tablet");
  return s;
}

export function signTabletToken(employeeId: string): string {
  const exp = Date.now() + MAX_AGE_SEC * 1000;
  const payload = `${employeeId}:${exp}`;
  const sig = createHmac("sha256", secret()).update(payload).digest("hex");
  return Buffer.from(JSON.stringify({ payload, sig }), "utf8").toString("base64url");
}

export function verifyTabletToken(token: string): { employeeId: string } | null {
  try {
    const raw = Buffer.from(token, "base64url").toString("utf8");
    const parsed = JSON.parse(raw) as { payload?: string; sig?: string };
    if (!parsed.payload || !parsed.sig) return null;
    const expected = createHmac("sha256", secret()).update(parsed.payload).digest("hex");
    const a = Buffer.from(parsed.sig, "hex");
    const b = Buffer.from(expected, "hex");
    if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
    const parts = parsed.payload.split(":");
    const employeeId = parts[0];
    const exp = Number(parts[1]);
    if (!employeeId || Number.isNaN(exp) || Date.now() > exp) return null;
    return { employeeId };
  } catch {
    return null;
  }
}

export async function getTabletEmployeeId(): Promise<string | null> {
  const jar = await cookies();
  const v = jar.get(TABLET_COOKIE)?.value;
  if (!v) return null;
  return verifyTabletToken(v)?.employeeId ?? null;
}

export function tabletCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: MAX_AGE_SEC,
  };
}
