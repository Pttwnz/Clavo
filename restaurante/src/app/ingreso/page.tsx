import { redirect } from "next/navigation";
import { gastroPanelUrl } from "@/lib/gastro-site";

/** El acceso de equipo es por Gastro Manager (`/panel`). */
export default function IngresoRedirectPage() {
  redirect(gastroPanelUrl());
}
