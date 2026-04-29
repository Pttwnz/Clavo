import { Suspense } from "react";
import { MenuBody } from "./MenuBody";
import { getMenuItemsResolved } from "@/lib/menu-items-resolved";

export default async function MenuPage() {
  const menuItems = await getMenuItemsResolved();
  return (
    <Suspense
      fallback={
        <div className="flex min-h-full items-center justify-center bg-[#faf5ef] p-8 font-display text-lg text-[#5c4033]">
          Cargando carta…
        </div>
      }
    >
      <MenuBody initialMenuItems={menuItems} />
    </Suspense>
  );
}
