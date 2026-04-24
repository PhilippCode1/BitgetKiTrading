import fs from "node:fs";
import path from "node:path";

/**
 * Muss mit dem laufenden Next-Dashboard (GATEWAY_JWT_SECRET) uebereinstimmen,
 * sonst ist Persona=unknown statt customer.
 */
export function loadGatewayJwtSecretFromRoot(): string {
  const fromEnv = process.env.GATEWAY_JWT_SECRET?.trim();
  if (fromEnv) {
    return fromEnv;
  }
  const root = path.resolve(__dirname, "../..");
  for (const name of [".env.local", ".env"]) {
    const p = path.join(root, name);
    if (!fs.existsSync(p)) continue;
    const text = fs.readFileSync(p, "utf8");
    const m = text.match(
      /^\s*GATEWAY_JWT_SECRET\s*=\s*([^\r\n]+?)\s*$/m,
    );
    if (m?.[1]) {
      return m[1]
        .trim()
        .replace(/^["']|["']$/g, "")
        .trim();
    }
  }
  return "";
}
