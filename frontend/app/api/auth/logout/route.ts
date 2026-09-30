import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const token = request.cookies.get("relay_session")?.value;
  const base = process.env.API_BASE_URL?.trim() || (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
  if (token && base) {
    try { await fetch(`${base.replace(/\/$/, "")}/v1/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }); } catch { /* Clear browser session even if API is down. */ }
  }
  const result = NextResponse.json({ ok: true });
  result.cookies.set("relay_session", "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
  return result;
}
