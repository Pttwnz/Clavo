import { redirect } from "next/navigation";
import { gastroPanelUrl } from "@/lib/gastro-site";

/** El panel de gestión vive en Gastro Manager (Flask), no en Next. */
export default function AdminRedirectPage() {
  redirect(gastroPanelUrl());
}
