import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const base = process.env.API_BASE_URL?.trim() || (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
  if (!base) return NextResponse.json({ detail: "API_BASE_URL is not configured" }, { status: 500 });
  try {
    const response = await fetch(`${base.replace(/\/$/, "")}/v1/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: await request.text(), cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) return NextResponse.json({ detail: data.detail || "Sign in failed" }, { status: response.status });
    const result = NextResponse.json(data.user);
    result.cookies.set("relay_session", data.token, { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: data.expires_in });
    return result;
  } catch {
    return NextResponse.json({ detail: "The support API is unavailable" }, { status: 502 });
  }
}
