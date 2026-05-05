import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

export type SupplierRow = {
  id: number;
  name: string;
  whatsapp_phone: string | null;
  notes: string | null;
  /** 0=domingo … 6=sábado; null si no usas día fijo */
  order_weekday: number | null;
  /** días entre pedidos si no usas weekday */
  order_interval_days: number | null;
  /** última fecha en la que marcaste “pedido enviado” (ISO date YYYY-MM-DD) */
  last_sent_on: string | null;
  template_json: string;
  created_at: string;
  updated_at: string;
};

export type OrderRow = {
  id: number;
  supplier_id: number;
  status: "draft" | "sent" | "received";
  notes: string | null;
  lines_json: string;
  whatsapp_draft: string | null;
  created_at: string;
  sent_at: string | null;
  received_at: string | null;
};

export type TaskRow = {
  id: number;
  title: string;
  cadence: "once" | "daily" | "weekly" | "monthly";
  next_due_on: string | null;
  last_done_on: string | null;
  created_at: string;
  updated_at: string;
};

let dbSingleton: Database.Database | null = null;

export function getDb(filePath: string): Database.Database {
  if (dbSingleton) return dbSingleton;
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const db = new Database(filePath);
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS suppliers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      whatsapp_phone TEXT,
      notes TEXT,
      order_weekday INTEGER,
      order_interval_days INTEGER,
      last_sent_on TEXT,
      template_json TEXT NOT NULL DEFAULT '[]',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','received')),
      notes TEXT,
      lines_json TEXT NOT NULL DEFAULT '[]',
      whatsapp_draft TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      sent_at TEXT,
      received_at TEXT
    );

    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      cadence TEXT NOT NULL CHECK (cadence IN ('once','daily','weekly','monthly')),
      next_due_on TEXT,
      last_done_on TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_orders_supplier_status ON orders(supplier_id, status);
  `);
  dbSingleton = db;
  return db;
}

export function isoDateInTimeZone(d: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const y = parts.find((p) => p.type === "year")?.value;
  const m = parts.find((p) => p.type === "month")?.value;
  const day = parts.find((p) => p.type === "day")?.value;
  if (!y || !m || !day) throw new Error("isoDateInTimeZone");
  return `${y}-${m}-${day}`;
}

export function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}
