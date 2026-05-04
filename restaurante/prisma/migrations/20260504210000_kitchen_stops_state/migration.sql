-- Paros de cocina: ítems ocultos en carta pública hasta que cocina los reactive.
CREATE TABLE "KitchenStopsState" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "stoppedItemIdsJson" TEXT NOT NULL DEFAULT '[]',
    "updatedAt" DATETIME NOT NULL
);

INSERT INTO "KitchenStopsState" ("id", "stoppedItemIdsJson", "updatedAt")
VALUES ('singleton', '[]', CURRENT_TIMESTAMP);
