import "dotenv/config";
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "../src/generated/prisma/client";
import bcrypt from "bcryptjs";

const datasourceUrl = process.env.DATABASE_URL ?? "file:./dev.db";
const adapter = new PrismaBetterSqlite3({ url: datasourceUrl });
const prisma = new PrismaClient({ adapter });

async function main() {
  const pin = process.env.SEED_EMPLOYEE_PIN ?? "1234";
  const hash = await bcrypt.hash(pin, 10);

  await prisma.employee.upsert({
    where: { email: "demo@restaurante.local" },
    update: { pinHash: hash, name: "María García", role: "MANAGER", active: true },
    create: {
      email: "demo@restaurante.local",
      name: "María García",
      role: "MANAGER",
      pinHash: hash,
    },
  });

  await prisma.employee.upsert({
    where: { email: "cocina@restaurante.local" },
    update: { pinHash: hash, name: "Carlos Ruiz", role: "KITCHEN", active: true },
    create: {
      email: "cocina@restaurante.local",
      name: "Carlos Ruiz",
      role: "KITCHEN",
      pinHash: hash,
    },
  });

  const tableCount = await prisma.diningTable.count();
  if (tableCount === 0) {
    const sala = Array.from({ length: 12 }, (_, i) => ({
      label: String(i + 1),
      zone: "Sala",
      capacity: i < 4 ? 2 : 4,
      sortOrder: i,
      active: true,
    }));
    const terraza = ["A", "B", "C", "D"].map((x, i) => ({
      label: `T-${x}`,
      zone: "Terraza",
      capacity: 4,
      sortOrder: 100 + i,
      active: true,
    }));
    await prisma.diningTable.createMany({ data: [...sala, ...terraza] });
    console.log("Mesas de sala (1–12) y terraza (T-A…T-D) creadas.");
  }

  const slotCount = await prisma.bookingSlot.count();
  if (slotCount === 0) {
    const rows: {
      weekday: number;
      startMinute: number;
      endMinute: number;
      label: string | null;
      webPercent: number;
      sortOrder: number;
      active: boolean;
    }[] = [];
    for (let d = 1; d <= 7; d++) {
      rows.push(
        {
          weekday: d,
          startMinute: 13 * 60,
          endMinute: 16 * 60,
          label: "Comida",
          webPercent: 70,
          sortOrder: 0,
          active: true,
        },
        {
          weekday: d,
          startMinute: 20 * 60,
          endMinute: 23 * 60 + 30,
          label: "Cena",
          webPercent: 70,
          sortOrder: 1,
          active: true,
        },
      );
    }
    await prisma.bookingSlot.createMany({ data: rows });
    console.log("Franjas de reserva web por defecto: comida 13:00–16:00 y cena 20:00–23:30 (todos los días).");
  }

  console.log(`Empleados demo creados. PIN por defecto: ${pin}`);
}

main()
  .then(() => prisma.$disconnect())
  .catch((e) => {
    console.error(e);
    prisma.$disconnect();
    process.exit(1);
  });
