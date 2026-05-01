import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { internalApiUnauthorized, verifyInternalClavoRequest } from "@/lib/internal-api-auth";
import { Prisma } from "@/generated/prisma/client";

export const dynamic = "force-dynamic";

function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(0, 0, 0, 0);
  return d;
}

function asCount(n: unknown): number {
  const x = typeof n === "bigint" ? Number(n) : Number(n);
  return Number.isFinite(x) ? x : 0;
}

export async function GET(req: Request) {
  if (!(await verifyInternalClavoRequest(req))) {
    return internalApiUnauthorized();
  }

  const url = new URL(req.url);
  const days = Math.min(90, Math.max(7, Number(url.searchParams.get("days")) || 30));
  const since = daysAgo(days);
  const since7 = daysAgo(7);

  let pageViews: {
    days: number;
    totalPeriod: number;
    total7d: number;
    byDay: { date: string; count: number }[];
    topPaths: { path: string; count: number }[];
    dbError?: boolean;
  } = {
    days,
    totalPeriod: 0,
    total7d: 0,
    byDay: [],
    topPaths: [],
    dbError: false,
  };

  try {
    const [totalPeriod, total7, topPaths] = await Promise.all([
      prisma.pageView.count({ where: { createdAt: { gte: since } } }),
      prisma.pageView.count({ where: { createdAt: { gte: since7 } } }),
      prisma.pageView.groupBy({
        by: ["path"],
        where: { createdAt: { gte: since } },
        _count: { _all: true },
        orderBy: { _count: { path: "desc" } },
        take: 20,
      }),
    ]);
    // Agregación en SQL (no findMany de cada fila): con 30–90 días y mucho tráfico el findMany
    // agotaba memoria / tiempo y la página «Web · estadísticas» fallaba mientras el dash (7 días) iba bien.
    const dailyRows = await prisma.$queryRaw<Array<{ d: string; c: bigint }>>(
      Prisma.sql`
        SELECT date("createdAt") AS d, COUNT(*) AS c
        FROM "PageView"
        WHERE "createdAt" >= ${since}
        GROUP BY date("createdAt")
        ORDER BY d ASC
      `,
    );
    const byDay = dailyRows.map((row) => ({
      date: row.d,
      count: asCount(row.c),
    }));
    pageViews = {
      days,
      totalPeriod: asCount(totalPeriod),
      total7d: asCount(total7),
      byDay,
      topPaths: topPaths.map((row) => ({
        path: String(row.path ?? ""),
        count: asCount(row._count?._all),
      })),
    };
  } catch {
    pageViews.dbError = true;
  }

  let reservations: {
    days: number;
    total7d: number;
    totalPeriod: number;
    bySource7d: Record<string, number>;
    bySourcePeriod: Record<string, number>;
    dbError?: boolean;
  } = {
    days,
    total7d: 0,
    totalPeriod: 0,
    bySource7d: {},
    bySourcePeriod: {},
  };

  try {
    const [g7, g30] = await Promise.all([
      prisma.reservation.groupBy({
        by: ["source"],
        where: { createdAt: { gte: since7 } },
        _count: { _all: true },
      }),
      prisma.reservation.groupBy({
        by: ["source"],
        where: { createdAt: { gte: since } },
        _count: { _all: true },
      }),
    ]);
    const bySource7d: Record<string, number> = {};
    for (const row of g7) {
      bySource7d[row.source] = asCount(row._count?._all);
    }
    const bySourcePeriod: Record<string, number> = {};
    for (const row of g30) {
      bySourcePeriod[row.source] = asCount(row._count?._all);
    }
    reservations = {
      days,
      total7d: asCount(g7.reduce((s, r) => s + asCount(r._count?._all), 0)),
      totalPeriod: asCount(g30.reduce((s, r) => s + asCount(r._count?._all), 0)),
      bySource7d,
      bySourcePeriod,
    };
  } catch {
    reservations.dbError = true;
  }

  try {
    return NextResponse.json({ pageViews, reservations });
  } catch (e) {
    console.error("[clavo-stats] JSON response", e);
    return NextResponse.json(
      {
        pageViews: {
          days,
          totalPeriod: 0,
          total7d: 0,
          byDay: [],
          topPaths: [],
          dbError: true,
        },
        reservations: {
          days,
          total7d: 0,
          totalPeriod: 0,
          bySource7d: {},
          bySourcePeriod: {},
          dbError: true,
        },
      },
      { status: 200 },
    );
  }
}
