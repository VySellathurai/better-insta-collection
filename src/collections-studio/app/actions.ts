"use server";

import { startCollectionJob as start } from "@/lib/job-runner";

export async function startCollectionJob(collectionName: string, limit: number) {
  return start(collectionName, limit);
}
