import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";

export function internalApiUnauthorized(): NextResponse {
  return NextResponse.json({ error: "No autorizado" }, { status: 401 });
}

function normalizeEnvValue(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  let v = raw.trim();
  if (v.length >= 2 && ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))) {
    v = v.slice(1, -1);
  }
  return v;
}

function incomingToken(req: Request): string {
  const auth = req.headers.get("authorization") ?? "";
  const bearer = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";
  if (bearer) return bearer;
  return req.headers.get("x-clavo-internal")?.trim() ?? "";
}

function isProduction(): boolean {
  return (
    process.env.VERCEL === "1" ||
    process.env.NODE_ENV === "production" ||
    process.env.CI === "true"
  );
}

/**
 * API interna Gastro → Next: mismo criterio que el login admin (ADMIN_PASSWORD / hash),
 * o Bearer CLAVO_INTERNAL_API_SECRET. En desarrollo también AUTH_SECRET.
 */
export async function verifyInternalClavoRequest(req: Request): Promise<boolean> {
  const token = incomingToken(req);
  if (!token) return false;

  const clavo = normalizeEnvValue(process.env.CLAVO_INTERNAL_API_SECRET);
  if (clavo && token === clavo) return true;

  const adminPlain = normalizeEnvValue(process.env.ADMIN_PASSWORD);
  if (adminPlain && token === adminPlain) return true;

  const adminHash = normalizeEnvValue(process.env.ADMIN_PASSWORD_HASH);
  if (adminHash?.startsWith("$2") && adminHash.length >= 55) {
    try {
      if (await bcrypt.compare(token, adminHash)) return true;
    } catch {
      return false;
    }
  }

  if (!isProduction()) {
    const authSecret = normalizeEnvValue(process.env.AUTH_SECRET);
    if (authSecret && token === authSecret) return true;
  }

  return false;
}
