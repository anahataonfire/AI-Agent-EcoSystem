-- CreateTable
CREATE TABLE "Listing" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "source" TEXT NOT NULL,
    "sourceId" TEXT,
    "url" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "addressRaw" TEXT,
    "buildingName" TEXT,
    "lat" REAL,
    "lng" REAL,
    "neighborhoodLabel" TEXT NOT NULL,
    "rentBase" INTEGER NOT NULL,
    "feesParsed" TEXT,
    "rentAllInEstimate" INTEGER,
    "beds" INTEGER NOT NULL,
    "baths" REAL NOT NULL,
    "sqft" INTEGER,
    "parking" TEXT NOT NULL DEFAULT 'unknown',
    "parkingType" TEXT,
    "ac" TEXT NOT NULL DEFAULT 'unknown',
    "acType" TEXT,
    "wdInUnit" TEXT NOT NULL DEFAULT 'unknown',
    "lanai" TEXT NOT NULL DEFAULT 'unknown',
    "outdoorSpace" TEXT NOT NULL DEFAULT 'unknown',
    "amenities" TEXT NOT NULL DEFAULT '[]',
    "viewTags" TEXT NOT NULL DEFAULT '[]',
    "photos" TEXT NOT NULL DEFAULT '[]',
    "availableDate" DATETIME,
    "postedDate" DATETIME,
    "lastSeenDate" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'new',
    "notes" TEXT,
    "redFlags" TEXT NOT NULL DEFAULT '[]',
    "scoreTotal" INTEGER NOT NULL DEFAULT 0,
    "scoreBreakdown" TEXT NOT NULL DEFAULT '{}',
    "dedupeKey" TEXT,
    "canonicalListingId" TEXT,
    CONSTRAINT "Listing_canonicalListingId_fkey" FOREIGN KEY ("canonicalListingId") REFERENCES "Listing" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "WatchedBuilding" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "buildingName" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "ScoringConfig" (
    "id" TEXT NOT NULL PRIMARY KEY DEFAULT 'default',
    "weights" TEXT NOT NULL,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ScanRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" DATETIME,
    "connector" TEXT NOT NULL,
    "listingsFound" INTEGER NOT NULL DEFAULT 0,
    "newListings" INTEGER NOT NULL DEFAULT 0,
    "errors" TEXT NOT NULL DEFAULT '[]'
);

-- CreateIndex
CREATE UNIQUE INDEX "Listing_url_key" ON "Listing"("url");

-- CreateIndex
CREATE INDEX "Listing_neighborhoodLabel_idx" ON "Listing"("neighborhoodLabel");

-- CreateIndex
CREATE INDEX "Listing_status_idx" ON "Listing"("status");

-- CreateIndex
CREATE INDEX "Listing_scoreTotal_idx" ON "Listing"("scoreTotal");

-- CreateIndex
CREATE INDEX "Listing_rentBase_idx" ON "Listing"("rentBase");

-- CreateIndex
CREATE INDEX "Listing_canonicalListingId_idx" ON "Listing"("canonicalListingId");

-- CreateIndex
CREATE UNIQUE INDEX "WatchedBuilding_buildingName_key" ON "WatchedBuilding"("buildingName");
