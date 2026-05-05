import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Server-side fetch proxy used so that gallery downloads work even when the
 * remote storage doesn't expose CORS to the browser. Only allows http(s) URLs.
 */
export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url");
  const filename = req.nextUrl.searchParams.get("filename") || undefined;
  if (!url) return NextResponse.json({ ok: false, error: "missing_url" }, { status: 400 });
  if (!/^https?:\/\//i.test(url)) {
    return NextResponse.json({ ok: false, error: "bad_scheme" }, { status: 400 });
  }
  try {
    const upstream = await fetch(url, { cache: "no-store" });
    if (!upstream.ok || !upstream.body) {
      return NextResponse.json(
        { ok: false, error: `upstream_${upstream.status}` },
        { status: 502 },
      );
    }
    const contentType = upstream.headers.get("content-type") || "application/octet-stream";
    const headers = new Headers({
      "Content-Type": contentType,
      "Cache-Control": "no-store",
    });
    if (filename) {
      headers.set("Content-Disposition", `attachment; filename="${sanitizeFilename(filename)}"`);
    }
    return new NextResponse(upstream.body, { status: 200, headers });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: (err as Error).message || "proxy_error" },
      { status: 502 },
    );
  }
}

function sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 120);
}
