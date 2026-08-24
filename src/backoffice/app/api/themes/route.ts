import { getThemeCounts } from "@/lib/queries";

export async function GET() {
  const themes = await getThemeCounts();
  return Response.json({ themes });
}
