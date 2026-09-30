import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const token = request.cookies.get("relay_session")?.value;
  if (!token) return NextResponse.json({ detail: "Sign in required" }, { status: 401 });
  const base = process.env.API_BASE_URL?.trim() || (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
  if (!base) return NextResponse.json({ detail: "API_BASE_URL is not configured" }, { status: 500 });
  try {
    const response = await fetch(`${base.replace(/\/$/, "")}/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "The support API is unavailable" }, { status: 502 });
  }
}
