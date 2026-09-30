import { NextRequest, NextResponse } from "next/server";

const allowed = new Set(["customers", "chat", "traces", "metrics", "conversations"]);

async function handler(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path[0] !== "v1" || !allowed.has(path[1]) || path.length > 3 || (path.length === 3 && !["traces", "conversations"].includes(path[1]))) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  const token = request.cookies.get("relay_session")?.value;
  if (!token) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  const base = process.env.API_BASE_URL?.trim() || (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
  if (!base) return NextResponse.json({ detail: "API_BASE_URL is not configured" }, { status: 500 });
  const url = new URL(`${base.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}`);
  url.search = request.nextUrl.search;
  try {
    const response = await fetch(url, {
      method: request.method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "The support API is unavailable" }, { status: 502 });
  }
}

export { handler as GET, handler as POST };
