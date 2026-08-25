import { getJobState } from "@/lib/job-runner";

export async function GET() {
  return Response.json(getJobState());
}
