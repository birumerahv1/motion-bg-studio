import { NextRequest, NextResponse } from "next/server";
import { callFreepik, extractResultUrls } from "@/lib/freepik";
import { getModel } from "@/lib/models";
import type { ModelId } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  let body: {
    modelId: ModelId;
    taskId: string;
    apiKeys: string[];
    preferredKeyIndex?: number;
  };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const { modelId, taskId, apiKeys, preferredKeyIndex } = body;
  if (!modelId || !taskId) {
    return NextResponse.json({ ok: false, error: "missing_args" }, { status: 400 });
  }
  if (!Array.isArray(apiKeys) || apiKeys.length === 0) {
    return NextResponse.json({ ok: false, error: "no_api_keys" }, { status: 400 });
  }
  const model = getModel(modelId);
  if (!model) {
    return NextResponse.json({ ok: false, error: "unknown_model" }, { status: 400 });
  }

  const result = await callFreepik<{ data?: Record<string, unknown> }>({
    method: "GET",
    path: `${model.taskBasePath}/${encodeURIComponent(taskId)}`,
    apiKeys,
    preferredIndex: preferredKeyIndex,
  });

  if (!result.ok || !result.data) {
    return NextResponse.json(
      {
        ok: false,
        error: result.errorMessage || "freepik_poll_failed",
        status: result.status,
      },
      { status: result.status >= 400 ? result.status : 502 },
    );
  }

  const taskData = (result.data as { data?: Record<string, unknown> }).data || {};
  const status = (taskData.status as string) || "IN_PROGRESS";
  const urls = extractResultUrls(taskData);

  return NextResponse.json({
    ok: true,
    status,
    urls,
    raw: taskData,
  });
}
