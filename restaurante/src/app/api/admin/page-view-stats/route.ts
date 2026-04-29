import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@/lib/db";
import { Prisma } from "@/generated/prisma/client";

export const dynamic = "force-dynamic";

function daysAgo(n: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - n);
  d.setHours(0, 0, 0, 0);
  return d;
}

export async function GET(req: Request) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  }

  const url = new URL(req.url);
  const days = Math.min(90, Math.max(7, Number(url.searchParams.get("days")) || 30));
  const since = daysAgo(days);

  try {
    const [totalPeriod, total7, topPaths] = await Promise.all([
      prisma.pageView.count({ where: { createdAt: { gte: since } } }),
      prisma.pageView.count({ where: { createdAt: { gte: daysAgo(7) } } }),
      prisma.pageView.groupBy({
        by: ["path"],
        where: { createdAt: { gte: since } },
        _count: { _all: true },
        orderBy: { _count: { path: "desc" } },
        take: 20,
      }),
    ]);

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
      count: Number(row.c),
    }));

    const paths = topPaths.map((row) => ({
      path: row.path,
      count: row._count._all,
    }));

    return NextResponse.json({
      days,
      totalPeriod,
      total7d: total7,
      byDay,
      topPaths: paths,
    });
  } catch (err) {
    console.error("[clavo] page-view-stats:", err);
    return NextResponse.json({
      days,
      totalPeriod: 0,
      total7d: 0,
      byDay: [],
      topPaths: [],
      dbError: true,
    });
  }
}
