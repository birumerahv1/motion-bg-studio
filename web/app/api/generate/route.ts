import { NextRequest, NextResponse } from "next/server";
import { buildPostBody, callFreepik } from "@/lib/freepik";
import { getModel } from "@/lib/models";
import type { FreepikTaskResponse, ModelId } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface GenerateRequestBody {
  modelId: ModelId;
  apiKeys: string[];
  payload: {
    prompt?: string;
    negativePrompt?: string;
    aspectRatio?: string;
    resolution?: string;
    duration?: number | string;
    startImageUrl?: string;
    endImageUrl?: string;
    referenceVideoUrl?: string;
    seed?: number;
    generateAudio?: boolean;
  };
}

export async function POST(req: NextRequest) {
  let body: GenerateRequestBody;
  try {
    body = (await req.json()) as GenerateRequestBody;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid_json" }, { status: 400 });
  }

  const { modelId, apiKeys, payload } = body;
  if (!modelId) {
    return NextResponse.json({ ok: false, error: "missing_model_id" }, { status: 400 });
  }
  if (!Array.isArray(apiKeys) || apiKeys.length === 0) {
    return NextResponse.json(
      { ok: false, error: "no_api_keys", hint: "Open Settings and add at least one Freepik API key." },
      { status: 400 },
    );
  }
  const model = getModel(modelId);
  if (!model) {
    return NextResponse.json({ ok: false, error: "unknown_model" }, { status: 400 });
  }

  const apiBody = buildPostBody(model, payload || {});
  const result = await callFreepik<FreepikTaskResponse>({
    method: "POST",
    path: model.postPath,
    body: apiBody,
    apiKeys,
  });

  if (!result.ok || !result.data) {
    return NextResponse.json(
      {
        ok: false,
        error: result.errorMessage || "freepik_request_failed",
        status: result.status,
      },
      { status: result.status >= 400 ? result.status : 502 },
    );
  }

  const taskId = result.data.data?.task_id;
  const status = result.data.data?.status;
  if (!taskId) {
    return NextResponse.json(
      { ok: false, error: "no_task_id_in_response", raw: result.data },
      { status: 502 },
    );
  }

  return NextResponse.json({
    ok: true,
    taskId,
    status: status || "CREATED",
    apiKeyIndex: result.apiKeyIndex,
    apiKeyFingerprint: result.apiKeyFingerprint,
    modelId,
  });
}
