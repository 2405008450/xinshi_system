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

 Date: 09/03/2026 19:32:48
*/


-- ----------------------------
-- Table structure for translation_project
-- ----------------------------
DROP TABLE IF EXISTS "public"."translation_project";
CREATE TABLE "public"."translation_project" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "order_no" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "project_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "file_type_secondary" varchar(100) COLLATE "pg_catalog"."default",
  "client_id" uuid,
  "customer_reception_time" timestamp(6),
  "customer_deadline_time" timestamp(6),
  "sent_to_client_time" timestamp(6),
  "client_feedback" text COLLATE "pg_catalog"."default",
  "project_status" varchar(50) COLLATE "pg_catalog"."default",
  "pm_confirmed_by" uuid,
  "translator_id" uuid,
  "translator_assignment_time" timestamp(6),
  "expected_translator_stats_method" varchar(100) COLLATE "pg_catalog"."default",
  "expected_translator_word_count" int8,
  "translator_delivery_progress" varchar(20) COLLATE "pg_catalog"."default",
  "pre_review_qc_progress" varchar(20) COLLATE "pg_catalog"."default",
  "review1_progress" varchar(20) COLLATE "pg_catalog"."default",
  "review2_progress" varchar(20) COLLATE "pg_catalog"."default",
  "post_review_qc_progress" varchar(20) COLLATE "pg_catalog"."default",
  "layout_progress" varchar(20) COLLATE "pg_catalog"."default",
  "consolidation_progress" varchar(20) COLLATE "pg_catalog"."default",
  "created_by" uuid,
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "language_pair" varchar(100) COLLATE "pg_catalog"."default",
  "priority" varchar(50) COLLATE "pg_catalog"."default",
  "word_count" int8
)
;

-- ----------------------------
-- Records of translation_project
-- ----------------------------
INSERT INTO "public"."translation_project" VALUES ('1a58dfb0-8324-4cdb-a9ed-994ab0a7da9c', 'TP-20260302-0014', '测试翻译项目批次 610', '', 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, '', 'pending', NULL, NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', NULL, '2026-03-02 20:13:27.625592', '2026-03-02 20:13:27.625592', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('1c984f07-d318-473d-9fe2-921c3bec1dad', 'TP-20260228-0003', '测试翻译项目批次 840', NULL, '4b16bb7d-ce2c-4cc7-9453-3394825e712c', NULL, NULL, NULL, NULL, '已暂停', 'fb5c69c5-e422-48e7-9214-025aacee74b0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'fb5c69c5-e422-48e7-9214-025aacee74b0', '2026-02-28 16:02:11.750898', '2026-02-28 16:02:11.750898', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('c1cff36a-a800-4836-bcb7-2f4c7ca3bd43', 'TP-20260302-0012', '吉利', '', NULL, '2026-03-02 00:00:00', '2026-03-04 00:00:00', NULL, '', 'pending', NULL, NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', NULL, '2026-03-02 20:09:43.396552', '2026-03-02 20:09:43.396552', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('c9fcc0e2-256a-4455-8917-a9b5e4daed5e', 'TP-20260302-0015', '1231231', '', NULL, NULL, NULL, NULL, '', 'pending', NULL, NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', NULL, '2026-03-02 20:33:30.95642', '2026-03-02 20:33:30.95642', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('185e9769-af62-473a-be28-bdb777f7eaa6', 'TP-20260228-0004', '测试翻译项目批次 490', '', 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, '', 'pending', '1a55179f-026e-44f7-ac5d-c32bed603515', NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', '1a55179f-026e-44f7-ac5d-c32bed603515', '2026-02-28 16:02:11.7579', '2026-02-28 16:02:11.7579', '', '', 0);
INSERT INTO "public"."translation_project" VALUES ('d82e59de-f57f-4c13-a225-7c4637e44627', 'TP-20260228-0002', '测试翻译项目批次 603', '', '4b16bb7d-ce2c-4cc7-9453-3394825e712c', NULL, NULL, NULL, NULL, '进行中', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, '2026-03-03 00:00:00', NULL, NULL, '进行中', NULL, NULL, NULL, NULL, '', NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:02:11.739266', '2026-02-28 16:02:11.739266', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('f2e1ba83-141b-4c0a-a460-a2265ea96788', 'TP-20260228-0008', '测试翻译项目批次 533', NULL, '00df42a2-291a-4917-ac60-0acec68e4c16', NULL, NULL, NULL, NULL, 'pending', 'd7116c76-ae7c-4624-9e5b-4bad4418c74d', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'd7116c76-ae7c-4624-9e5b-4bad4418c74d', '2026-02-28 16:02:11.788583', '2026-02-28 16:02:11.788583', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('edc19c21-49dd-4118-b066-daa4dd728411', 'TP-20260228-0009', '测试翻译项目批次 610', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:02:11.795767', '2026-02-28 16:02:11.795767', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('a383da7c-6457-4a13-a837-ea8a5e00a805', 'TP-20260228-0010', '测试翻译项目批次 170', NULL, '88bc493e-e357-4600-9de7-4a507be5e9fd', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:02:11.802266', '2026-02-28 16:02:11.802266', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('2de21aed-d67d-4e02-9f8b-a978973bfc6f', 'TP-20260228-SQL001', 'SQL直插测试项目批次 422', NULL, 'c45edd34-2023-4b60-86d2-4ad6c815896e', NULL, NULL, NULL, NULL, 'pending', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('858c1e78-ad24-4ffb-9c5b-6bd645a6fc55', 'TP-20260228-SQL002', 'SQL直插测试项目批次 771', NULL, '2ff609a6-da58-4045-9e52-f6a7bd98cc33', NULL, NULL, NULL, NULL, 'pending', '74c04077-ea7c-4978-9735-10413dc62aa3', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '74c04077-ea7c-4978-9735-10413dc62aa3', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('9d869ebf-3d55-477d-a4db-0ec4e9c1488c', 'TP-20260228-SQL003', 'SQL直插测试项目批次 673', NULL, '12a4a437-73e3-4878-9eb2-22959da1df21', NULL, NULL, NULL, NULL, 'pending', 'fb5c69c5-e422-48e7-9214-025aacee74b0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'fb5c69c5-e422-48e7-9214-025aacee74b0', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('e95e6db2-3b58-4311-8525-e6691448829b', 'TP-20260228-SQL004', 'SQL直插测试项目批次 115', NULL, '12a4a437-73e3-4878-9eb2-22959da1df21', NULL, NULL, NULL, NULL, 'pending', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('b2b5fc81-163b-4497-a752-c7bff86d2d5e', 'TP-20260228-SQL005', 'SQL直插测试项目批次 314', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', 'b2c53252-9cb5-476e-b289-13019ad69c78', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'b2c53252-9cb5-476e-b289-13019ad69c78', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('c3cc69e8-f65b-42c3-bb7a-1628215a73e9', 'TP-20260228-SQL006', 'SQL直插测试项目批次 165', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', '74c04077-ea7c-4978-9735-10413dc62aa3', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '74c04077-ea7c-4978-9735-10413dc62aa3', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('8bacd012-a839-411c-9020-dd85d35d5c7d', 'TP-20260228-SQL007', 'SQL直插测试项目批次 525', NULL, 'c45edd34-2023-4b60-86d2-4ad6c815896e', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('efed205d-a908-4bb2-955a-0e1eb2c3c81b', 'TP-20260228-SQL008', 'SQL直插测试项目批次 805', NULL, '59e14867-dea0-49d4-bc14-220002a416e7', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('a3bb5bb9-11a1-4dc2-9b21-640848ed716a', 'TP-20260228-SQL009', 'SQL直插测试项目批次 483', NULL, '12a4a437-73e3-4878-9eb2-22959da1df21', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('be8e9dcd-8ba9-410f-ba19-64aa51c99dd0', 'TP-20260302-0002', '测试翻译项目批次 856', NULL, '621ae0b3-4237-4e80-947e-1649b57b2253', NULL, NULL, NULL, NULL, 'pending', '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', '2026-03-02 11:45:34.372763', '2026-03-02 11:45:34.372763', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('f3f59a1d-d792-4722-971d-63ebe9fd06cb', 'TP-20260302-0003', '测试翻译项目批次 267', NULL, '2ff609a6-da58-4045-9e52-f6a7bd98cc33', NULL, NULL, NULL, NULL, 'pending', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-03-02 11:45:34.389738', '2026-03-02 11:45:34.389738', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('12eb4bfd-8bd6-4a34-8010-5045d2c4fd6b', 'TP-20260302-0001', '测试翻译项目批次 254', NULL, '4b16bb7d-ce2c-4cc7-9453-3394825e712c', NULL, NULL, NULL, NULL, 'pending', '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', '2026-03-02 11:43:26.146969', '2026-03-02 11:43:26.146969', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('c3730723-a1e9-4be0-8a17-1082355a74c8', 'TP-20260228-0001', '测试翻译项目批次 239', '测试', '59e14867-dea0-49d4-bc14-220002a416e7', NULL, NULL, NULL, NULL, '进行中', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, '', NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-02-28 16:02:11.714498', '2026-02-28 16:02:11.714498', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('7b50514a-672d-49a6-9254-c2a470c91b29', 'TP-20260302-0004', '测试翻译项目批次 683', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', 'b2c53252-9cb5-476e-b289-13019ad69c78', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'b2c53252-9cb5-476e-b289-13019ad69c78', '2026-03-02 11:45:34.397776', '2026-03-02 11:45:34.397776', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('bed7e3f0-d977-4fe9-b9ea-b079d55cde6d', 'TP-20260302-0006', '测试翻译项目批次 547', NULL, '2ff609a6-da58-4045-9e52-f6a7bd98cc33', NULL, NULL, NULL, NULL, 'pending', '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '5eb624c1-5fc6-4587-b469-6f75c9b2ce37', '2026-03-02 11:45:34.410117', '2026-03-02 11:45:34.410117', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('1cd973e9-9210-41f8-ba6c-0b54bd9f8c95', 'TP-20260302-0007', '测试翻译项目批次 757', NULL, '2ff609a6-da58-4045-9e52-f6a7bd98cc33', NULL, NULL, NULL, NULL, 'pending', 'd7116c76-ae7c-4624-9e5b-4bad4418c74d', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'd7116c76-ae7c-4624-9e5b-4bad4418c74d', '2026-03-02 11:45:34.416105', '2026-03-02 11:45:34.416105', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('d120d9f7-b0ab-46b1-9b03-e85a67666490', 'TP-20260302-0008', '测试翻译项目批次 726', NULL, '2ff609a6-da58-4045-9e52-f6a7bd98cc33', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-03-02 11:45:34.422296', '2026-03-02 11:45:34.422296', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('04d91a87-f7a0-4bf6-a899-557ec5ce2c36', 'TP-20260302-0009', '测试翻译项目批次 809', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-03-02 11:45:34.428856', '2026-03-02 11:45:34.428856', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('3e50a26e-61a6-4bbe-9c80-0e05ad4d10ea', 'TP-20260302-0010', '测试翻译项目批次 508', NULL, 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, NULL, 'pending', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-03-02 11:45:34.434834', '2026-03-02 11:45:34.434834', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('4ee5ca74-8e91-4f15-a388-9d820a7f84f4', 'TP-20260302-0011', '测试翻译项目批次 342', NULL, '4276a053-4cd7-4abc-87b7-a685a3044931', NULL, NULL, NULL, NULL, 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-03-02 11:45:34.441294', '2026-03-02 11:45:34.441294', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('42d2955b-d66a-4568-938e-896b2ba4cff7', 'TP-20260228-SQL010', 'SQL直插测试项目批次 312', NULL, '621ae0b3-4237-4e80-947e-1649b57b2253', NULL, NULL, NULL, NULL, 'pending', 'ba92e52a-f517-48a4-a422-1688f2afe067', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'ba92e52a-f517-48a4-a422-1688f2afe067', '2026-02-28 16:33:35.934747', '2026-02-28 16:33:35.934747', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('cc1c7817-b53d-472d-bfad-6051a0fbc323', 'TP-20260302-0013', '测试翻译项目批次 610', '', 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', NULL, NULL, NULL, '', 'pending', NULL, NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', NULL, '2026-03-02 20:13:15.630647', '2026-03-02 20:13:15.630647', NULL, NULL, NULL);
INSERT INTO "public"."translation_project" VALUES ('87d986e8-bb24-4e89-8407-3b6af6d8547f', 'TP-20260228-0006', '测试翻译项目批次 531', '', '4276a053-4cd7-4abc-87b7-a685a3044931', NULL, NULL, NULL, '', 'pending', '1a55179f-026e-44f7-ac5d-c32bed603515', NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', '1a55179f-026e-44f7-ac5d-c32bed603515', '2026-02-28 16:02:11.772405', '2026-02-28 16:02:11.772405', '', '', 0);
INSERT INTO "public"."translation_project" VALUES ('68644150-264c-4d8b-b040-47bf0498e0ec', 'TP-20260228-0007', '测试翻译项目批次 296', '', '88bc493e-e357-4600-9de7-4a507be5e9fd', NULL, NULL, NULL, '', 'pending', 'b2c53252-9cb5-476e-b289-13019ad69c78', NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', 'b2c53252-9cb5-476e-b289-13019ad69c78', '2026-02-28 16:02:11.780904', '2026-02-28 16:02:11.780904', '', '', 0);
INSERT INTO "public"."translation_project" VALUES ('ac6b248a-48aa-48ff-805f-c5e8d2852dbf', 'TP-20260228-0005', '测试翻译项目批次 363', '', 'c45edd34-2023-4b60-86d2-4ad6c815896e', NULL, NULL, NULL, '', 'pending', 'e228c697-4885-41a3-a02f-ef389defedd0', NULL, NULL, NULL, NULL, '', '', '', '', '', '', '', 'e228c697-4885-41a3-a02f-ef389defedd0', '2026-02-28 16:02:11.765485', '2026-02-28 16:02:11.765485', '', '', 0);
INSERT INTO "public"."translation_project" VALUES ('92c71151-584c-4d70-a657-f85c472c9390', 'TP-20260302-0005', '测试翻译项目批次 950', 'PDF', 'ce50afb4-ec6d-416e-91b7-b527f7a07abd', '2026-03-11 00:00:00', '2026-03-11 00:00:00', NULL, NULL, 'terminated', '74c04077-ea7c-4978-9735-10413dc62aa3', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '74c04077-ea7c-4978-9735-10413dc62aa3', '2026-03-02 11:45:34.403402', '2026-03-02 11:45:34.403402', '中译英', NULL, 9999);

-- ----------------------------
-- Uniques structure for table translation_project
-- ----------------------------
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "translation_project_order_no_key" UNIQUE ("order_no");

-- ----------------------------
-- Primary Key structure for table translation_project
-- ----------------------------
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "translation_project_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table translation_project
-- ----------------------------
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "fk_project_client" FOREIGN KEY ("client_id") REFERENCES "public"."client" ("id") ON DELETE RESTRICT ON UPDATE NO ACTION;
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "fk_project_creator" FOREIGN KEY ("created_by") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "fk_project_pm" FOREIGN KEY ("pm_confirmed_by") REFERENCES "public"."app_user" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."translation_project" ADD CONSTRAINT "fk_project_translator" FOREIGN KEY ("translator_id") REFERENCES "public"."translator" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
