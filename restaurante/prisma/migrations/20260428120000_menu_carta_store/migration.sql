-- CreateTable
CREATE TABLE "MenuCartaStore" (
    "id" TEXT NOT NULL PRIMARY KEY DEFAULT 'singleton',
    "itemsJson" TEXT NOT NULL DEFAULT '',
    "updatedAt" DATETIME NOT NULL
);
