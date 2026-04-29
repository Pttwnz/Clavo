import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "@/generated/prisma/client";

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
  sqliteAdapter: PrismaBetterSqlite3 | undefined;
};

const datasourceUrl = process.env.DATABASE_URL ?? "file:./dev.db";

function createPrisma() {
  const adapter = new PrismaBetterSqlite3({ url: datasourceUrl });
  return new PrismaClient({ adapter });
}

/**
 * Tras ampliar el schema, el singleton en caliente (p. ej. `next dev`) puede quedar con un `PrismaClient`
 * viejo (sin campos nuevos en runtime) → validación falla al actualizar mesas walk-in, etc.
 * Subir este número cuando añadas campos/tablas relevantes para forzar un cliente nuevo.
 */
export const PRISMA_SCHEMA_EPOCH = 7;

const globalEpoch = globalThis as unknown as { __clavoPrismaEpoch?: number };

/**
 * Tras ampliar el schema, el singleton en caliente (p. ej. `next dev`) puede quedar sin modelos nuevos
 * → `prisma.bookingSlot` undefined y 500 al reservar por web.
 */
function diningTableFieldsFromClient(client: PrismaClient): string[] | null {
  const raw = client as unknown as {
    _runtimeDataModel?: { models?: Record<string, { fields?: { name: string }[] }> };
  };
  const fields = raw._runtimeDataModel?.models?.DiningTable?.fields;
  if (!fields?.length) return null;
  return fields.map((f) => f.name);
}

/**
 * Si el singleton sigue siendo de un `prisma generate` antiguo, faltan campos (p. ej. `walkInStartedAt`)
 * y las actualizaciones fallan con PrismaClientValidationError.
 */
function prismaClientMatchesCurrentSchema(client: PrismaClient): boolean {
  const c = client as {
    diningTable?: { aggregate: unknown };
    bookingSlot?: { findMany: unknown };
  };
  const base =
    typeof c.diningTable?.aggregate === "function" &&
    typeof c.bookingSlot?.findMany === "function";
  if (!base) return false;
  const names = diningTableFieldsFromClient(client);
  if (names == null) return true;
  return names.includes("walkInStartedAt");
}

function getOrRecreatePrisma(): PrismaClient {
  let client = globalForPrisma.prisma;
  const epochOk = globalEpoch.__clavoPrismaEpoch === PRISMA_SCHEMA_EPOCH;
  if (client && epochOk && prismaClientMatchesCurrentSchema(client)) {
    return client;
  }
  void client?.$disconnect().catch(() => {});
  client = createPrisma();
  globalForPrisma.prisma = client;
  globalEpoch.__clavoPrismaEpoch = PRISMA_SCHEMA_EPOCH;
  return client;
}

export const prisma = getOrRecreatePrisma();
