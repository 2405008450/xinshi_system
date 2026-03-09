/*
 Navicat Premium Dump SQL

 Source Server         : localhost_5432
 Source Server Type    : PostgreSQL
 Source Server Version : 170007 (170007)
 Source Host           : localhost:5432
 Source Catalog        : xinshi_system
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170007 (170007)
 File Encoding         : 65001

 Date: 09/03/2026 19:32:59
*/


-- ----------------------------
-- Table structure for consultation
-- ----------------------------
DROP TABLE IF EXISTS "public"."consultation";
CREATE TABLE "public"."consultation" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "consultation_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "client_id" uuid,
  "consultation_time" timestamp(6),
  "consultation_method" varchar(50) COLLATE "pg_catalog"."default",
  "client_source" varchar(100) COLLATE "pg_catalog"."default",
  "source_keyword" varchar(255) COLLATE "pg_catalog"."default",
  "consultation_description" text COLLATE "pg_catalog"."default",
  "remarks" text COLLATE "pg_catalog"."default",
  "customer_service_id" uuid,
  "sales_person_id" uuid,
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "consultation_type" varchar(50) COLLATE "pg_catalog"."default",
  "handling_method" varchar(100) COLLATE "pg_catalog"."default",
  "editor_id" uuid,
  "follow_up_count" int4 DEFAULT 0,
  "follow_up_time" timestamp(6),
  "follow_up_status" varchar(20) COLLATE "pg_catalog"."default",
  "follow_up_remarks" text COLLATE "pg_catalog"."default",
  "follow_up_person_id" uuid,
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Records of consultation
-- ----------------------------
INSERT INTO "public"."consultation" VALUES ('0727c39d-6197-44ff-83c9-e8e403f62a7b', 'EQ-260309-001', NULL, NULL, 'phone', 'referral', '', '12312', '12312', NULL, NULL, 'pending', 'price', NULL, NULL, 0, NULL, NULL, NULL, NULL, '2026-03-09 16:16:24.780099', '2026-03-09 16:16:24.780099');
INSERT INTO "public"."consultation" VALUES ('8b99deed-aa94-48cf-8328-1398e75e54df', 'EQ-260309-002', '4b16bb7d-ce2c-4cc7-9453-3394825e712c', '2026-03-09 00:00:00', 'phone', 'website', '12312', '', '', NULL, NULL, 'processing', '', NULL, NULL, 0, NULL, NULL, NULL, NULL, '2026-03-09 16:25:39.843711', '2026-03-09 16:25:39.843711');

-- ----------------------------
-- Indexes structure for table consultation
-- ----------------------------
CREATE INDEX "idx_consultation_client_id" ON "public"."consultation" USING btree (
  "client_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_consultation_consultation_code" ON "public"."consultation" USING btree (
  "consultation_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_consultation_status" ON "public"."consultation" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table consultation
-- ----------------------------
ALTER TABLE "public"."consultation" ADD CONSTRAINT "consultation_consultation_code_key" UNIQUE ("consultation_code");

-- ----------------------------
-- Primary Key structure for table consultation
-- ----------------------------
ALTER TABLE "public"."consultation" ADD CONSTRAINT "consultation_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table consultation
-- ----------------------------
ALTER TABLE "public"."consultation" ADD CONSTRAINT "fk_consultation_client" FOREIGN KEY ("client_id") REFERENCES "public"."client" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."consultation" ADD CONSTRAINT "fk_consultation_customer_service" FOREIGN KEY ("customer_service_id") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."consultation" ADD CONSTRAINT "fk_consultation_editor" FOREIGN KEY ("editor_id") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."consultation" ADD CONSTRAINT "fk_consultation_follow_up_person" FOREIGN KEY ("follow_up_person_id") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."consultation" ADD CONSTRAINT "fk_consultation_sales_person" FOREIGN KEY ("sales_person_id") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
