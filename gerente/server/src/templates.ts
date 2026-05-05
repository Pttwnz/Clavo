export type TemplateLine = { label: string; qty: number };

export function parseTemplateJson(raw: string): TemplateLine[] {
  try {
    const v = JSON.parse(raw) as unknown;
    if (!Array.isArray(v)) return [];
    return v
      .map((row) => {
        if (!row || typeof row !== "object") return null;
        const label = (row as { label?: unknown }).label;
        const qty = (row as { qty?: unknown }).qty;
        if (typeof label !== "string" || typeof qty !== "number") return null;
        return { label: label.trim(), qty: Math.max(0, Math.floor(qty)) };
      })
      .filter(Boolean) as TemplateLine[];
  } catch {
    return [];
  }
}

export function buildWhatsappDraft(supplierName: string, lines: TemplateLine[], deliveryNote?: string): string {
  const header = `Pedido — ${supplierName}`;
  const body = lines.map((l, i) => `${i + 1}. ${l.label} × ${l.qty}`).join("\n");
  const foot = deliveryNote?.trim() ? `\n\nNota: ${deliveryNote.trim()}` : "";
  return `${header}\n\n${body}${foot}`;
}
