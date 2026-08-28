DROP INDEX "posts_sort_order_idx";--> statement-breakpoint
ALTER TABLE "posts" ADD COLUMN "collection" text;