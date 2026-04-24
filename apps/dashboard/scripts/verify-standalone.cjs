const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const st = path.join(root, "build", "standalone");
const server = path.join(st, "apps", "dashboard", "server.js");

if (!fs.existsSync(server)) {
  console.error(
    "Erwartet: build/standalone/apps/dashboard/server.js (vorher: pnpm build in apps/dashboard)",
  );
  process.exit(1);
}
if (fs.existsSync(path.join(st, "pnpm-workspace.yaml"))) {
  console.error("Unerwartet: pnpm-workspace.yaml im Standalone-Output");
  process.exit(1);
}
// Kein vollstaendiger Monorepo-Lock im exportierten Laufzeit-Baum
if (fs.existsSync(path.join(st, "pnpm-lock.yaml"))) {
  console.error("Unerwartet: pnpm-lock.yaml im Standalone-Output");
  process.exit(1);
}
console.log("P82: standalone-Layout ok");
