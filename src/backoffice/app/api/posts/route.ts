import { NextRequest } from "next/server";
import { z } from "zod";

import { getAllPostsWithDetails } from "@/lib/queries";

const querySchema = z.object({
  theme: z.string().trim().min(1).optional(),
  q: z.string().trim().min(1).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(200).default(200),
});

export async function GET(request: NextRequest) {
  const searchParams = Object.fromEntries(request.nextUrl.searchParams);
  const parsed = querySchema.safeParse(searchParams);

  if (!parsed.success) {
    return Response.json({ error: parsed.error.flatten() }, { status: 400 });
  }

  const { theme, q, page, pageSize } = parsed.data;
  const { items, total } = await getAllPostsWithDetails({ theme, q, page, pageSize });

  return Response.json({ posts: items, page, pageSize, total });
}
