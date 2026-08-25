"use server";

import { startCollectionJob as start } from "@/lib/job-runner";

export async function startCollectionJob(collectionName: string) {
  return start(collectionName);
}
