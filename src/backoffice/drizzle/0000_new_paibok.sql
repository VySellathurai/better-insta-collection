CREATE TABLE "post_images" (
	"post_id" text NOT NULL,
	"position" integer NOT NULL,
	"file_name" text NOT NULL,
	CONSTRAINT "post_images_post_id_position_pk" PRIMARY KEY("post_id","position"),
	CONSTRAINT "post_images_position_check" CHECK ("post_images"."position" BETWEEN 1 AND 3)
);
--> statement-breakpoint
CREATE TABLE "post_themes" (
	"post_id" text NOT NULL,
	"theme_id" integer NOT NULL,
	CONSTRAINT "post_themes_post_id_theme_id_pk" PRIMARY KEY("post_id","theme_id")
);
--> statement-breakpoint
CREATE TABLE "posts" (
	"id" text PRIMARY KEY NOT NULL,
	"source_url" text NOT NULL,
	"platform" text NOT NULL,
	"genre" text,
	"author" text NOT NULL,
	"author_handle" text,
	"duration_s" double precision,
	"processed_at" date NOT NULL,
	"status" text NOT NULL,
	"title" text NOT NULL,
	"summary" text NOT NULL,
	"description" text,
	"transcript" text,
	"sort_order" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE "themes" (
	"id" serial PRIMARY KEY NOT NULL,
	"slug" text NOT NULL,
	"name" text NOT NULL
);
--> statement-breakpoint
ALTER TABLE "post_images" ADD CONSTRAINT "post_images_post_id_posts_id_fk" FOREIGN KEY ("post_id") REFERENCES "public"."posts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "post_themes" ADD CONSTRAINT "post_themes_post_id_posts_id_fk" FOREIGN KEY ("post_id") REFERENCES "public"."posts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "post_themes" ADD CONSTRAINT "post_themes_theme_id_themes_id_fk" FOREIGN KEY ("theme_id") REFERENCES "public"."themes"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "post_themes_theme_id_idx" ON "post_themes" USING btree ("theme_id");--> statement-breakpoint
CREATE UNIQUE INDEX "posts_source_url_unique" ON "posts" USING btree ("source_url");--> statement-breakpoint
CREATE INDEX "posts_sort_order_idx" ON "posts" USING btree ("sort_order");--> statement-breakpoint
CREATE UNIQUE INDEX "themes_slug_unique" ON "themes" USING btree ("slug");