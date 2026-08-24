import { getPostBySlug } from "@/lib/queries";

type Params = { params: Promise<{ slug: string }> };

export async function GET(_request: Request, { params }: Params) {
  const { slug } = await params;
  const post = await getPostBySlug(slug);

  if (!post) {
    return Response.json({ error: "post not found" }, { status: 404 });
  }

  return Response.json(post);
}
