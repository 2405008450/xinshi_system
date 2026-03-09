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

 Date: 09/03/2026 19:32:35
*/


-- ----------------------------
-- Table structure for client
-- ----------------------------
DROP TABLE IF EXISTS "public"."client";
CREATE TABLE "public"."client" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "client_code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "client_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "client_short_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "client_manager" varchar(100) COLLATE "pg_catalog"."default",
  "manager_contact" varchar(100) COLLATE "pg_catalog"."default",
  "field_level1" varchar(100) COLLATE "pg_catalog"."default",
  "field_level2" varchar(100) COLLATE "pg_catalog"."default",
  "country" varchar(50) COLLATE "pg_catalog"."default",
  "province" varchar(50) COLLATE "pg_catalog"."default",
  "city" varchar(50) COLLATE "pg_catalog"."default",
  "district" varchar(50) COLLATE "pg_catalog"."default",
  "client_status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "cooperation_start_date" timestamp(6),
  "remarks" text COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "english_name" varchar(255) COLLATE "pg_catalog"."default",
  "english_short_name" varchar(100) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Records of client
-- ----------------------------
INSERT INTO "public"."client" VALUES ('2ff609a6-da58-4045-9e52-f6a7bd98cc33', 'laE5QuD9U0nyl20', '澳门吴', '澳门吴翻译', '11', '34', 'NTfTJOg1IN31Nt4', 'dfoUpKmcI0JJEWC', '北塞浦路斯*', 'qTuJnp7aCYzvUUY', '海西蒙古族藏族自治州', 'nukAL6V6FVK9RUD', 'A5vG5gU6wy4QDFf', '2018-03-17 23:09:12', 'dbalYUxxZjdwUY5cUsfvfgI2rA8nNtSHuhSofnFbFwLhVwX8mKWoThBiIGdw60Lr0rroUFP7EEZJB2CuadeIvvbUhyfSSiMzvOCF165qdKZh8EVBkGdeyiq1k3FtsNBdeNDJDr6d7eeByjQb7S5nw9jP4CxlFLWRO30R0ptZ5zGERmUeBG6l8lokQVYoxua3nlyAQ0y4HSP1dHMvqLcObXJdGhULhjmxthtln1hCiAMWT3h1wpyYFNugtbI9EItX1g0wNutlRZLQMPRs3eaCjYYKAUgoLF794X1PBgKpeYkQ7DuEtz6NkbwLkLyqGuY3g1MZaHyEU7XRSFE27zr5nMLtGpOVowZ6M7XPMJ5pym8y6BxOHJdqxMQJwHNjq5YF3uNPU95wXMddwgl3gZ9K5yCgL5dlV90z0liM8S9WO4nFtm50zhdsdmHfWrkE3Kn6BBIyxD', '1975-01-09 21:43:38', '1978-11-15 17:41:15', NULL, NULL);
INSERT INTO "public"."client" VALUES ('59e14867-dea0-49d4-bc14-220002a416e7', 'geSgLNdSJDkSnOl', '中翻译', '北京中翻译', '29', '90', 'EEDCkQ0jtWF49kC', '9mspvvp7OMNpGAC', '毛里求斯', 'zGP2E1sfrR1gzoO', '重庆市', 'zZXHMFMMVnuFGCa', 'V8t0IBthfGIBRiz', '1985-06-18 15:02:10', 'BU5VMBVudNlRvhi5XgNwQjhhhJkbjlu2B1EvM22s8mLKocmEuAfUAOHN2pUZdq9FutIapS41ma2sm7snY1yZXZ3bX9Knqp0MGVi55Poq9tKAuAOThnaSWOptjuMOFCsvk3EnF4Jc7LVJJhQTXDSgkuObRSMBTPpmnDulQzroZ1cnOeqrIimNDCgqDgjUdUL6GkBxU2c55jeNYMrO6MS6kTJVDtc2eoA4fKC2xQ98yBbliTgvXDmuXn2dAKfBti0rn553awnrOOKjkzFkte29xMJu4vkJ0vDRWjO1OC6A22h4AkXfp2hbSmy775lzGTa6Wx76mfUHixRxSIIhyme8dCYBS9aATcnO41fSwDz5XvAKBX9hysXhboz2jkFdT7FZhevQ7Be0CB7AMtRneZ2oYR2KBn1Dpm52cZ4hIBTi8TUAoRjJE', '1974-06-18 17:49:45', '1998-01-16 18:46:07', NULL, NULL);
INSERT INTO "public"."client" VALUES ('621ae0b3-4237-4e80-947e-1649b57b2253', 'zO4XmDRYMZa1tjV', '资翻译', '上海资翻译', '23', '11', '制造业', 'qdVGhBqzySi8yhy', '格林纳达', '甘肃', '银川市', 'pl70eL7Vp9Zc22f', 'active', '2023-05-30 00:14:38', 'x7RoI1Apu8fnfGD3GtHo8HbGkewf1hJ241MlBRFPkmrCDZW4eB6BCvFZ38HiDkgGZC5q13vBvzhIw2Erv5Zk8FE8qnzaqsJtnU8WYigRrHZy1cf9UmcNqQ2QXIp75yrkaUNih6A5uvISCkVcokzziVj1RdoW05DBqeXqZxRF1Lu7nwG6cvzpp1ERCWLpCZX2Ox1SDzZwUXiTowaiS6VGv4oCYdZEzJCoowGYICbolZLDHFGGISN0SotYFiZWp0qx5xGLcrERG2HD1qSJqPUcFTcXm3SIBz9uFSGiTkr9PgG6hKXLMX0jRMzR1q3GgVhZyaQMVMS83Odu6HvBMvnRHJasUslbj7IOKAULOhoFO1uhQSAJB3EWGLweIpKWIP8p4RRzjSgGYT7tqMyQKaQhOQIRWQHbeErXUejjF1L9lIJ7Zk1utFAfFfjKTACUJFuX5Le9CetG789VwjWp2VoZygNkkbUoEIIog8tx', '2014-07-29 12:52:04', '2017-11-13 08:52:35', NULL, NULL);
INSERT INTO "public"."client" VALUES ('ce50afb4-ec6d-416e-91b7-b527f7a07abd', 'rLsYa4lnauGsnOg', '美国玲', '美国玲翻译', '23', '60', '1TmLNqehQX5kmiD', '7HYJQjzRMPbI2eH', '密克罗尼西亚联邦', 'w9xdJaMl7MZW8oQ', '西宁市', 'nc2n36mBU7CxndT', 'QxFQHN8cEmmGgW2', '2008-07-16 02:11:38', 'lzcRhDoJAoJ4KXBEycUS0CKL4Lm6p3DWNpmw2lYA2wPfRRNeAr8yR21o2pI8n6nsLplNqxxJ0xjrtWRxrhyobc9gehMQVBaeKikKMq99XaGz5EJPWZiS6HHeyBqWGrupmXhb8NhHwUQFTwi6oPlszLnQSISx6kWfHdrY5iYEK2rkeIs8ZzJs4Umf6IdxZIHLHILb8A3EGqMZZGRxlkigZuvZZIfw5clYrb8wfpXqnPLzAGAsB1VEcNaJnTBu3uxDVBapJostpmNjqLMt6XUHqZbE8eiBHXNDMofG1HJp08t51UzX4cqaRWZtCHNuwn9gG2Wu625abvg2dfSAkXaqiLsjhBrfck6mJTEpQHpoIf0Tz6S8ZtdpjR0vXCGPBCrsGii9r8ghmvWekOyUs8X4rZYBZtscWuGTLcw75iKjEXAFp7XdwH5peW6LqKSuhuw3CI3klgNOfsHl1rVmEAzhJeSdulPuVZKL0q75gOTFQXD9xJwXqwJ6WRP3wv9MmHWmV6xrcU7ejtZQLltDBrFSuVslEyL3ssGy1oeVtrgWCkAUivXa5', '1995-11-24 15:00:39', '2018-10-24 08:26:53', NULL, NULL);
INSERT INTO "public"."client" VALUES ('c45edd34-2023-4b60-86d2-4ad6c815896e', 'YftxWzqSjssKIh2', '吉利', '吉利乘用车集团', '40', '89', 'kVwrsKyLtlNkxNV', 'lEWWdEJkWgeqxrB', '匈牙利', 'GAibyyaDDoZmium', '张家口市', 'RJSmeeQax8ptKq2', 'IYba7aRw7NlZ6T7', '1990-03-25 06:46:18', 'lPzKyKtos38UZExO2B706cWNTwMMD6S3HPxHfpD9DiaZeot04wsFG36aqNg7zuuDtO3OEtsbYABNg1ib3N64bRVC6C8vBs3lOePl9BJQ3WLzifIqUCOOCjeqfvYadcrmqMxPd0fP0H4n1BIsgnu7793ZpmdvsYqxVINv64fDrX9TQdvSZ3a0dRPlMtjBuhqRqjYLcd0YYV9rlbNJWGS3QTeWYG2imMOGYKZ8Sn7MiDMIdNNTA2ezGNOuL8h8Gt4k3E2zXebjPGpTvzcgZyrC9q', '1980-03-28 07:29:00', '1996-01-25 05:03:59', NULL, NULL);
INSERT INTO "public"."client" VALUES ('00df42a2-291a-4917-ac60-0acec68e4c16', 'KtDB5JxLH87hXeL', '吉利汽车研究院', '吉利汽车研究院', '91', '99', 'oVO3qeid4Bghfnm', 'CwVfqTx6LESOd4Q', '印度尼西亚', '89UTfSIJTZqWK2l', '宣城市', 'ZmvsRohCGxwmJGN', 'ExEi7OlCjyp18re', '1987-04-22 17:14:36', 'W9K48RSB7sPq4WhW9lPTUSXpGJ2chYIgkUJ1AmyaGCR1ndVNVH9eSORo03iNO37mxhiRL08UE2BMix2tJhz2IGxrR1VrOegJwoD0kWGh1oOuokrI4Sgdye0TzFEngFQyHw3tIZAIZIUOaP144Q1pwZeQrlZjuJ3GOfhLrR3OZR8kNwkwhnl6kR1SlAsOMw2k22zwOKSP1OMiVGIzRcA90DN5lOwv1D1xaVjKS8lnh5Mw2', '2003-10-07 07:07:03', '2024-06-20 00:03:54', NULL, NULL);
INSERT INTO "public"."client" VALUES ('4b16bb7d-ce2c-4cc7-9453-3394825e712c', 'dWsF881wasoVmvj', '上海唐能翻译咨询有限公司', '上海顾翻译', '74', '33', '2ynGBgAbD4PDLrG', 'c2gAgCowJaigMG9', '约旦', 'GtDripUO92UobIK', '重庆市', 'Tv2Ce2E8E0c4vrT', 'iFabKeNdgOtqX8z', '1983-02-12 12:40:04', 'Bj9c56RkUhf1hkyq1X08yCBSOvlXgRbhbLLGwMyvpBqZImJKh0QMAiTdsoW7GYinjNuQCFJMRXndjHHF8AxutKdrXOLoEMNqxQXqZXQL4X3XqZoZyJdYDSt7SzFQqYPCGvd1KUeNFvh1wtuWGIemfUvst1hdXwTrNGleV1ln4rtzpt2e3HQrKewIb6QekfWSVGncV7fBO8u7N93c6Huag4SaoS5UpcZbZyHPdJ10g49LgtkN2zxCZSGFpBZ6QA6DxpafkzLXTCSf7AMjlYlIPY2EPgAlWnuov7Qf8LstLKlOHdoD63LLmgxOb7kq6A5WeyC8hEWEeZBcXNg8ydkKcqdiOoLnI0r3JjnwyujTTX6bKOZrFGRwGbusoQgQLnDdVmMO1hW80sSQlvRJ83j5agcCFZxLc', '1991-08-07 13:05:25', '2014-10-30 07:51:03', NULL, NULL);
INSERT INTO "public"."client" VALUES ('88bc493e-e357-4600-9de7-4a507be5e9fd', 'NGNZuYLFWT19jy9', '深圳市星月翻译有限公司', '深圳安翻译', '27', '9', 'y9k76mZfmJrtto1', '97FJCWGAdnupSbU', '比利时', 'cbTch8jPp5IBmTu', '鄂尔多斯市', 'V0JTj6iI6QhUhUJ', 'El0KSJg3ge6PiAc', '2020-02-26 00:00:32', 'mtkWBAtdWmlJhCCVOn2X59BxgeSLzjeqS9SfUUaghdVCuOSussjNJ8rM1yM4m8dNdJnlH0SPHPDO5xEHeV8euoKs8vrwSQGydrVYHVNLNrXgRIF8vJttcS1CIiKMTCa4ppccIYxbbWwH5jFsedEjaM5uJSTlE5gICx11l03t3l7KJbZwaaHFfEgzvuaxCY7My2o8XrAG6HtEAKIFhuhCP6ZNeqUP3ut2UHMmtOVRmlgIj6648CkfnE697pDKkSqjaosJQbQDdj7ZmJnemUTBSeGwf9mWC6E7nw6aUhm8QTveu0TXwOree72NTrgykfd4YsDdAqT2IK2JJWxUjpVmzpZo6GbLM8gqaiXlev9S6SO3HS2R09N8xF1JmfFvBzK3fahCAmib2ce8Obz4mAzqKZMCRS4nI8BFB3nhIc4VEJpUFkNPxfLchOQF6enhfovlVO3RIJNto2N7lSOsRqQHj3HgI3s1cmL9cFYl9yi2zNRxZhvvyBSiRfBhbwTOwIIg9C9Ahu0773B3U07IjUITZolO5tp62tquaPiuecdwPrRGO5WVraweqvqPsiOSDDAE3Ua4DYTbaDfURMvYZgiQMsJdZWmMDMs9Zt1Q502GwlSShfHHsEyGZzpfLfsAI1K0LGQkZ06QvLM5i3VyWaCSTzSftwvCu8jLxkBuQEaG02jWg4cYaGd2ddSSJLXSaAf', '2018-01-11 04:52:23', '1985-09-17 04:20:08', NULL, NULL);
INSERT INTO "public"."client" VALUES ('4276a053-4cd7-4abc-87b7-a685a3044931', 'ELTntnVqHJD5aLy', '广州中集集装箱有限公司', '中集集装箱', '12', '79', '7dSVUJrCJFyfODF', 'D5fdeq8ajC8ghrH', '韩国', 'exfRTToyxTWJmol', '六安市', 'EVz3Z0sZIpQPjp7', 'sjixDA9uY2s7np6', '1983-10-08 06:19:49', 'vlhPu3qHelhIWSscPH4TsP5Uus2LaJzPBbyA2Dsf5u5P90D8EguVRvxbzfX7bFcIEHNPZJOrsr8TNBRLlJ1nxJmwOQ7ezWCevBoU7rGpufB4j5fAg8eBVhlmPWzRj36xChnf3OCBNobB6Ga4I3RjveAR7yAwvdrmWNOQMbRQemDFGCC84Funoj46SCk6O5BUXe3hcWp1nt9EJzMB7k6kRYfgBWqFOKaf7Mv4K7oh6yEfD2iEdh0YrbW3GlnziGdoSv35v44vsL4DzUfd359MsnvvtLTzBI0pzXl89Sn4sz9ztfiSUH3ovX0H748YR5IB2YPvCYgwpWH91F4wqrRjAZOzU5OKGS75ysdOj7QAyqOjA3OSISxiS4vucPA0WJLWqIUE67Q8ov5oIWKkubr7rOuUJbbMmrA7of9HSDEKWQf4bWCX52JkXEdHBoXGudoILjYETxKG8JfrXreEnxp30AVe5hkeWAD6mJ7pDOAgcbw8JJy9X5SUYODV8XJboddgUsoDgskA8q0PdMoGjnGXM6ubRYZRgdGvz3MlD1uOJFpgHl11pkOcnzPTcgtSv5GShXLUF6gX4sfbeeAacH9dBtYCLpDuu4FjvZrtnN1GHOPTqohCDgA30R2TxdEXSth4p0ECZZwRDfI5fsBS4Y', '2012-11-20 11:34:20', '2017-01-07 07:18:36', NULL, NULL);
INSERT INTO "public"."client" VALUES ('12a4a437-73e3-4878-9eb2-22959da1df21', '7rBbLjdPj9k1SiQ', '网易广州', '网易', '71', '69', 'IeQa1zgMuLQUb6L', '0GlhC363CbF5qf0', '约旦', 'Qhzx8g6VHn0LAri', '长治市', 'MEivLnaqY1mcieI', 'UMDIqPIZq6r2BUg', '1986-09-05 00:25:10', 'qhxgbmPeAFc0EP0OAHgBao75Vd3ohm1KirzWtNl9YvvEzg2GUb9GriejYhc15wlxm4JijncgN44nDoodKbG0DAmM9TjqWDyFsTt9BDb2WND6Cx8CqVlAFB2wcpbqnVqL0DPJkJT9vjJx6rnJ2wyfQyC2U6GA89qEcauPqB2r3fjR9zp2K62YzFmp7CNylGYOiqAVkIz4Mk6lAFPSKsjQUOfAhVgASv3PVw9RaTF06CvuhBkbRzqbJej2nD2gEWNH9CiMB0NDaKW1TWXv98X9qJswr0BwLpCgbTVX8HaZcBfO8fYvyrT7HYenjrkqtNBOsnccE0Skip6gbYyv5P3JcoxOMUyrXboCRdPJjLHY76Q0mIIpBjyt00QzktsgYwCz9FfkyFsSAsVorpRvAFkMdnF9XZiWWPL5Ri8lyrVSed5U50R2XG2HbPnbjyFlxhjbxnGsIEfAYoudVLbx4v1Iot7Xsf903nTG65tRRe0dHJtlAoYTHQKftODtTqq177siV82nUAPNm46bK5GT6dAXRpwZst11OGHUmAW2FTlyXe1zgO2Dn8OTNZBleFispeh4plAhjOOBJLuZdj7lRMu9P0dBGs0jWJryt94DKvUFOTBdEl4p8mwmQKGVOVF0FgbHwJlp6xCa0Uh3m39hkteFSFB35D774OTaHON2KYqSxgXm3uvHuDelb0ho4gh6AuaB3A2VMslVCN7yyyOFdApdWadojrfe7eNQkWHrKX3yntHt2byvcY0nKaC5Z0wGoLwsoIOQV2qMqQZ8p5', '1981-07-04 15:54:34', '1990-07-27 08:15:13', NULL, NULL);

-- ----------------------------
-- Uniques structure for table client
-- ----------------------------
ALTER TABLE "public"."client" ADD CONSTRAINT "client_client_code_key" UNIQUE ("client_code");

-- ----------------------------
-- Primary Key structure for table client
-- ----------------------------
ALTER TABLE "public"."client" ADD CONSTRAINT "client_pkey" PRIMARY KEY ("id");
