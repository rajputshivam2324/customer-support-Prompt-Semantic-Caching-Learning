import { NextResponse } from "next/server";

const names: Record<string, string> = { acme: "Acme Corp", globex: "Globex", wayne: "Wayne Industries", stark: "Stark Systems", umbrella: "Umbrella Labs" };

export function GET() {
  if (process.env.DEMO_MODE !== "false") {
    return NextResponse.json([{ id: "demo", name: "Demo Workspace" }]);
  }
  let keys: Record<string, string> = {};
  try { keys = JSON.parse(process.env.DEMO_TENANT_KEYS || "{}"); } catch { /* reported by gateway */ }
  return NextResponse.json(Object.keys(keys).map(id => ({ id, name: names[id] || id })));
}
