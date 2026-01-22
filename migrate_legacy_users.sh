#!/bin/bash
# migrate_legacy_users.sh

# Load environment variables (to get MONGODB_URI)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$MONGODB_URI" ]; then
  echo "Error: MONGODB_URI not set in .env"
  exit 1
fi

echo "Starting migration of legacy user records..."

mongosh "$MONGODB_URI" --eval '
  db = db.getSiblingDB("expTracker");

  // 1. Migrate "tier: premium" to "role: premium_user"
  print("Migrating premium users...");
  var res1 = db.settings.updateMany(
    { "subscription_tier": "premium" },
    {
      $set: { "role": "premium_user" },
      $unset: { "subscription_tier": "" }
    }
  );
  print("Updated " + res1.modifiedCount + " premium users.");

  // 2. Set default "role: user" for anyone missing a role
  print("Setting default role for legacy users...");
  var res2 = db.settings.updateMany(
    { "role": { $exists: false } },
    { $set: { "role": "user" } }
  );
  print("Updated " + res2.modifiedCount + " users to default role.");

  print("Migration complete.");
'