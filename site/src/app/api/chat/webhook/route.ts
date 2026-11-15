import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json(
    {
      ok: false,
      error: "Legacy guest chat webhook is retired; Telegram support uses authenticated bot polling.",
    },
    { status: 410 }
  );
}
