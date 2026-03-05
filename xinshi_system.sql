--
-- PostgreSQL database dump
--

\restrict FCe96DvmenMN9JiL1V2UqsK7Yi3uiDUrq4dd8KzKDD9Ud2DjVka3LgI7DJMnrjD

-- Dumped from database version 17.7
-- Dumped by pg_dump version 17.7

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_user (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    email character varying(255),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    department character varying(50),
    fixed_tasks jsonb DEFAULT '[]'::jsonb
);


ALTER TABLE public.app_user OWNER TO postgres;

--
-- Name: client; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.client (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_code character varying(50) NOT NULL,
    client_name character varying(255) NOT NULL,
    client_short_name character varying(100) NOT NULL,
    client_manager character varying(100),
    manager_contact character varying(100),
    field_level1 character varying(100),
    field_level2 character varying(100),
    country character varying(50),
    province character varying(50),
    city character varying(50),
    district character varying(50),
    client_status character varying(20) DEFAULT 'pending'::character varying,
    cooperation_start_date timestamp without time zone,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.client OWNER TO postgres;

--
-- Name: employee_leave; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_leave (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employee_id uuid NOT NULL,
    employee_name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    leave_type character varying(50),
    reason character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.employee_leave OWNER TO postgres;

--
-- Name: project_file; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.project_file (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    translation_project_id uuid NOT NULL,
    file_name character varying(255) NOT NULL,
    storage_path text NOT NULL,
    file_type character varying(50),
    file_ext character varying(20),
    file_size bigint,
    storage_type character varying(50),
    uploaded_by uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.project_file OWNER TO postgres;

--
-- Name: role; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.role (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    role_name character varying(50) NOT NULL,
    description text
);


ALTER TABLE public.role OWNER TO postgres;

--
-- Name: translation_project; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.translation_project (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    order_no character varying(50) NOT NULL,
    project_name character varying(255) NOT NULL,
    file_type_secondary character varying(100),
    client_id uuid,
    customer_reception_time timestamp without time zone,
    customer_deadline_time timestamp without time zone,
    sent_to_client_time timestamp without time zone,
    client_feedback text,
    project_status character varying(50),
    pm_confirmed_by uuid,
    translator_id uuid,
    translator_assignment_time timestamp without time zone,
    expected_translator_stats_method character varying(100),
    expected_translator_word_count bigint,
    translator_delivery_progress character varying(20),
    pre_review_qc_progress character varying(20),
    review1_progress character varying(20),
    review2_progress character varying(20),
    post_review_qc_progress character varying(20),
    layout_progress character varying(20),
    consolidation_progress character varying(20),
    created_by uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.translation_project OWNER TO postgres;

--
-- Name: translator; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.translator (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    translator_code character varying(50),
    translator_name character varying(255) NOT NULL,
    cooperation_type character varying(50),
    contact_info character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    translation_type character varying(255),
    quality_score character varying(10),
    cloud_revision character varying(50),
    daily_rate character varying(100),
    direction character varying(20),
    default_priority integer DEFAULT 0,
    schedule_remarks text,
    languages character varying(255),
    gender character varying(10),
    height character varying(20),
    appearance character varying(100),
    nationality character varying(50),
    ethnicity character varying(50),
    phone character varying(50),
    phone2 character varying(50),
    email1 character varying(100),
    email2 character varying(100),
    resume_path character varying(500),
    other_contact character varying(255),
    overdue_count integer DEFAULT 0,
    overall_rating text,
    first_contact_date date,
    remarks text
);


ALTER TABLE public.translator OWNER TO postgres;

--
-- Name: user_role; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_role (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_role OWNER TO postgres;

--
-- Name: work_schedule; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.work_schedule (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    schedule_date date NOT NULL,
    shift_table jsonb DEFAULT '[]'::jsonb,
    leave_notes jsonb DEFAULT '[]'::jsonb,
    urgent_table_zh_en jsonb DEFAULT '[]'::jsonb,
    urgent_table_en_zh jsonb DEFAULT '[]'::jsonb,
    dept_person_data jsonb DEFAULT '[]'::jsonb,
    not_scheduled_tasks jsonb DEFAULT '[]'::jsonb,
    pm_rotation_order character varying(500),
    updated_by uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.work_schedule OWNER TO postgres;

--
-- Name: workflow_instance; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.workflow_instance (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    translation_project_id uuid NOT NULL,
    difficulty character varying(20),
    file_editable boolean,
    current_stage_key character varying(50) DEFAULT 'reception'::character varying NOT NULL,
    current_assignee_id uuid,
    project_status character varying(30) DEFAULT 'pending'::character varying,
    stage_notes jsonb DEFAULT '{}'::jsonb,
    stage_data jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.workflow_instance OWNER TO postgres;

--
-- Name: workflow_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.workflow_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    workflow_instance_id uuid NOT NULL,
    operator_id uuid,
    from_stage character varying(50),
    to_stage character varying(50),
    direction character varying(20),
    description text,
    note text,
    next_assignee_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.workflow_log OWNER TO postgres;

--
-- Data for Name: app_user; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_user (id, username, password_hash, full_name, email, is_active, created_at, updated_at, department, fixed_tasks) FROM stdin;
5eb624c1-5fc6-4587-b469-6f75c9b2ce37	奶奶的龙	a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3	测试中	123user@example.com	t	2026-01-16 15:20:20.078816	2026-01-16 15:20:20.078816	\N	[]
ba92e52a-f517-48a4-a422-1688f2afe067	admin	8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918	admin	user@example.com	t	2026-01-16 16:32:50.385926	2026-01-16 16:32:50.385926	\N	[]
794d62da-689b-4b52-98fe-165c708d26b4	kuangjiao	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	旷姣	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目部	[]
e228c697-4885-41a3-a02f-ef389defedd0	HR	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	项目助理	user@example.com	t	2026-02-09 19:16:33.752236	2026-02-09 19:16:33.752236	项目部	[]
1a55179f-026e-44f7-ac5d-c32bed603515	service	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	客户专员	user@example.com	t	2026-02-05 15:28:05.660439	2026-02-05 15:28:05.660439	\N	[]
b2c53252-9cb5-476e-b289-13019ad69c78	trans	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	项目专员	user@example.com	t	2026-02-05 17:03:10.096255	2026-02-05 17:03:10.096255	\N	[]
74c04077-ea7c-4978-9735-10413dc62aa3	LPM	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	项目经理	1111@qq.com	t	2026-02-05 17:05:13.657683	2026-02-05 17:05:13.657683	\N	[]
d7116c76-ae7c-4624-9e5b-4bad4418c74d	sales	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	销售专员	12312312@qq.com	t	2026-02-05 17:06:00.235289	2026-02-05 17:06:00.235289	\N	[]
fb5c69c5-e422-48e7-9214-025aacee74b0	DTP	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	排版专员	123@qq.com	t	2026-02-10 16:27:09.049628	2026-02-10 16:27:09.049628	项目部	[]
27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	chuqiao	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	楚翘	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
b9e7efff-0da1-41a0-9925-35f4ebf99fc9	lixian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	李娴	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目经理	[]
0bc4d77f-6c3c-4a88-811d-856f6a95ae96	menghua	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	孟花	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目经理	[]
fcc0e174-7b8e-4775-bbc2-b21384f04c3e	shaofei	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	少妃	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目经理	[]
f1254b6a-b858-4787-a075-cc2e9769f7e6	chenjia	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	陈佳	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	翻译部	["银行词汇", "信实翻译 中译小语种 机翻引擎测试"]
2bdefb2f-b23e-447f-903c-ede4dbf72cbb	thomas	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	Thomas	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	翻译部	[]
72712263-ea72-43c5-8b1c-1b05f7680988	yaran	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	雅然	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
85d5dd64-f93b-47ad-a7a4-e3fc1d758954	miaodan	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	苗丹	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
aa6c3c99-58a4-4ede-a510-3924ae469309	jiaming	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	家铭	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
f6d137e3-2664-4daf-84ed-ce67e5691f49	huangmeng	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	黄萌	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
2d30f9df-1082-4975-8f23-dd27d8ba491f	wuge	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	武哥	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
69c5737a-d90a-44e4-964c-733260da185d	jinglin	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	靖琳	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
296067f8-38f9-4c57-86ad-575e739e338e	xinjian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	辛建	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
08165a0c-b40d-4206-8407-236d5875c46f	shuqian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	舒倩	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
3ff6a06a-395e-47cd-a7d6-5248605120a2	yeshan	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	烨珊	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
48324d9a-58bf-4b9c-bc6b-591007b0bdcc	yunyu	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	韵钰	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	["（暂停）项目专员培训资料调整", "（暂停）项目经理培训资料梳理、编写"]
e6ba212f-2cc3-4f95-9a04-b8f7c20392b5	lirong	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	立溶	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
f19abbad-49fe-4dcc-bed8-e13d54e555b4	shuting	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	舒婷	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
7bdff3f4-a101-4648-84dd-5412948edcb2	yuqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	宇琪	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
f174bde7-af8b-4c28-b94e-4d2c07bab29c	cuizhen	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	翠珍	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
4a282914-f05c-47e3-a4ea-e7511bc3e8c8	zixia	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	紫霞	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
5709ddb9-38b2-4dcb-9d7b-30b217fa8071	wanjun	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	菀筠	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
f50a5f1e-1553-4456-8b38-f4ecdebc849d	yingqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	颖琦	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
e3e45710-2408-45ae-ba6e-54e0691506f5	weiqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	伟琪	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目部	[]
97f891c3-5319-4e0d-92da-1eabc773598e	shaojie	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	少洁	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
72cc5448-bb49-42d0-a873-8d22e206eb54	wenhui	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	文慧	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
84e460fc-1d5a-4c69-aa12-e84a178fbfed	yunjian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	运坚	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
bc55fda0-78d1-492b-804c-0c59607c3922	ruizhu	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	瑞珠	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	["每月专检稽查（梁承敏、沈佳佳）"]
d0ba4db1-3bac-407a-b052-5107830373d9	dajie	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	大杰	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	["每月专检稽查（贺媛、孙晓燕）"]
1a2bec37-e91c-473d-b493-35a0a84eea65	shenghui	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	胜辉	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
feb5c87e-693e-4c41-aab2-0171bbdf40e8	junxuan	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	浚轩	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
cd145a21-d5b3-4de8-b052-a581618b18e4	yulin	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	裕林	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
136e5884-ee13-4469-be1a-737ff5514e9e	chenxu	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	晨旭	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
843476e5-7a3f-46b8-a5da-e85403c6cf62	meixia	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	美霞	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
d4bcccdf-deb4-4f04-a50d-a93db5e29f88	zhenzhong	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	振中	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	招聘项目	[]
f8e49b50-bf82-4a52-9993-b838dfabb949	yilong	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	以龙	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	销售	[]
907c6ace-203e-4ab4-acb2-0d30a49c913e	zhilin	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	志林	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	销售	[]
098ae5c4-771e-4fc5-9502-187f16603369	quange	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	泉哥	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	销售	[]
\.


--
-- Data for Name: client; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.client (id, client_code, client_name, client_short_name, client_manager, manager_contact, field_level1, field_level2, country, province, city, district, client_status, cooperation_start_date, remarks, created_at, updated_at) FROM stdin;
59e14867-dea0-49d4-bc14-220002a416e7	geSgLNdSJDkSnOl	胡云	漕启鸣	29	90	EEDCkQ0jtWF49kC	9mspvvp7OMNpGAC	毛里求斯	zGP2E1sfrR1gzoO	重庆市	zZXHMFMMVnuFGCa	V8t0IBthfGIBRiz	1985-06-18 15:02:10	BU5VMBVudNlRvhi5XgNwQjhhhJkbjlu2B1EvM22s8mLKocmEuAfUAOHN2pUZdq9FutIapS41ma2sm7snY1yZXZ3bX9Knqp0MGVi55Poq9tKAuAOThnaSWOptjuMOFCsvk3EnF4Jc7LVJJhQTXDSgkuObRSMBTPpmnDulQzroZ1cnOeqrIimNDCgqDgjUdUL6GkBxU2c55jeNYMrO6MS6kTJVDtc2eoA4fKC2xQ98yBbliTgvXDmuXn2dAKfBti0rn553awnrOOKjkzFkte29xMJu4vkJ0vDRWjO1OC6A22h4AkXfp2hbSmy775lzGTa6Wx76mfUHixRxSIIhyme8dCYBS9aATcnO41fSwDz5XvAKBX9hysXhboz2jkFdT7FZhevQ7Be0CB7AMtRneZ2oYR2KBn1Dpm52cZ4hIBTi8TUAoRjJE	1974-06-18 17:49:45	1998-01-16 18:46:07
4276a053-4cd7-4abc-87b7-a685a3044931	ELTntnVqHJD5aLy	宁娅碧	金希元	12	79	7dSVUJrCJFyfODF	D5fdeq8ajC8ghrH	韩国	exfRTToyxTWJmol	六安市	EVz3Z0sZIpQPjp7	sjixDA9uY2s7np6	1983-10-08 06:19:49	vlhPu3qHelhIWSscPH4TsP5Uus2LaJzPBbyA2Dsf5u5P90D8EguVRvxbzfX7bFcIEHNPZJOrsr8TNBRLlJ1nxJmwOQ7ezWCevBoU7rGpufB4j5fAg8eBVhlmPWzRj36xChnf3OCBNobB6Ga4I3RjveAR7yAwvdrmWNOQMbRQemDFGCC84Funoj46SCk6O5BUXe3hcWp1nt9EJzMB7k6kRYfgBWqFOKaf7Mv4K7oh6yEfD2iEdh0YrbW3GlnziGdoSv35v44vsL4DzUfd359MsnvvtLTzBI0pzXl89Sn4sz9ztfiSUH3ovX0H748YR5IB2YPvCYgwpWH91F4wqrRjAZOzU5OKGS75ysdOj7QAyqOjA3OSISxiS4vucPA0WJLWqIUE67Q8ov5oIWKkubr7rOuUJbbMmrA7of9HSDEKWQf4bWCX52JkXEdHBoXGudoILjYETxKG8JfrXreEnxp30AVe5hkeWAD6mJ7pDOAgcbw8JJy9X5SUYODV8XJboddgUsoDgskA8q0PdMoGjnGXM6ubRYZRgdGvz3MlD1uOJFpgHl11pkOcnzPTcgtSv5GShXLUF6gX4sfbeeAacH9dBtYCLpDuu4FjvZrtnN1GHOPTqohCDgA30R2TxdEXSth4p0ECZZwRDfI5fsBS4Y	2012-11-20 11:34:20	2017-01-07 07:18:36
88bc493e-e357-4600-9de7-4a507be5e9fd	NGNZuYLFWT19jy9	石渝天	宋尤	27	9	y9k76mZfmJrtto1	97FJCWGAdnupSbU	比利时	cbTch8jPp5IBmTu	鄂尔多斯市	V0JTj6iI6QhUhUJ	El0KSJg3ge6PiAc	2020-02-26 00:00:32	mtkWBAtdWmlJhCCVOn2X59BxgeSLzjeqS9SfUUaghdVCuOSussjNJ8rM1yM4m8dNdJnlH0SPHPDO5xEHeV8euoKs8vrwSQGydrVYHVNLNrXgRIF8vJttcS1CIiKMTCa4ppccIYxbbWwH5jFsedEjaM5uJSTlE5gICx11l03t3l7KJbZwaaHFfEgzvuaxCY7My2o8XrAG6HtEAKIFhuhCP6ZNeqUP3ut2UHMmtOVRmlgIj6648CkfnE697pDKkSqjaosJQbQDdj7ZmJnemUTBSeGwf9mWC6E7nw6aUhm8QTveu0TXwOree72NTrgykfd4YsDdAqT2IK2JJWxUjpVmzpZo6GbLM8gqaiXlev9S6SO3HS2R09N8xF1JmfFvBzK3fahCAmib2ce8Obz4mAzqKZMCRS4nI8BFB3nhIc4VEJpUFkNPxfLchOQF6enhfovlVO3RIJNto2N7lSOsRqQHj3HgI3s1cmL9cFYl9yi2zNRxZhvvyBSiRfBhbwTOwIIg9C9Ahu0773B3U07IjUITZolO5tp62tquaPiuecdwPrRGO5WVraweqvqPsiOSDDAE3Ua4DYTbaDfURMvYZgiQMsJdZWmMDMs9Zt1Q502GwlSShfHHsEyGZzpfLfsAI1K0LGQkZ06QvLM5i3VyWaCSTzSftwvCu8jLxkBuQEaG02jWg4cYaGd2ddSSJLXSaAf	2018-01-11 04:52:23	1985-09-17 04:20:08
4b16bb7d-ce2c-4cc7-9453-3394825e712c	dWsF881wasoVmvj	位尧鸣	隋信灿	74	33	2ynGBgAbD4PDLrG	c2gAgCowJaigMG9	约旦	GtDripUO92UobIK	重庆市	Tv2Ce2E8E0c4vrT	iFabKeNdgOtqX8z	1983-02-12 12:40:04	Bj9c56RkUhf1hkyq1X08yCBSOvlXgRbhbLLGwMyvpBqZImJKh0QMAiTdsoW7GYinjNuQCFJMRXndjHHF8AxutKdrXOLoEMNqxQXqZXQL4X3XqZoZyJdYDSt7SzFQqYPCGvd1KUeNFvh1wtuWGIemfUvst1hdXwTrNGleV1ln4rtzpt2e3HQrKewIb6QekfWSVGncV7fBO8u7N93c6Huag4SaoS5UpcZbZyHPdJ10g49LgtkN2zxCZSGFpBZ6QA6DxpafkzLXTCSf7AMjlYlIPY2EPgAlWnuov7Qf8LstLKlOHdoD63LLmgxOb7kq6A5WeyC8hEWEeZBcXNg8ydkKcqdiOoLnI0r3JjnwyujTTX6bKOZrFGRwGbusoQgQLnDdVmMO1hW80sSQlvRJ83j5agcCFZxLc	1991-08-07 13:05:25	2014-10-30 07:51:03
12a4a437-73e3-4878-9eb2-22959da1df21	7rBbLjdPj9k1SiQ	丁阳荣	于梓萱	71	69	IeQa1zgMuLQUb6L	0GlhC363CbF5qf0	约旦	Qhzx8g6VHn0LAri	长治市	MEivLnaqY1mcieI	UMDIqPIZq6r2BUg	1986-09-05 00:25:10	qhxgbmPeAFc0EP0OAHgBao75Vd3ohm1KirzWtNl9YvvEzg2GUb9GriejYhc15wlxm4JijncgN44nDoodKbG0DAmM9TjqWDyFsTt9BDb2WND6Cx8CqVlAFB2wcpbqnVqL0DPJkJT9vjJx6rnJ2wyfQyC2U6GA89qEcauPqB2r3fjR9zp2K62YzFmp7CNylGYOiqAVkIz4Mk6lAFPSKsjQUOfAhVgASv3PVw9RaTF06CvuhBkbRzqbJej2nD2gEWNH9CiMB0NDaKW1TWXv98X9qJswr0BwLpCgbTVX8HaZcBfO8fYvyrT7HYenjrkqtNBOsnccE0Skip6gbYyv5P3JcoxOMUyrXboCRdPJjLHY76Q0mIIpBjyt00QzktsgYwCz9FfkyFsSAsVorpRvAFkMdnF9XZiWWPL5Ri8lyrVSed5U50R2XG2HbPnbjyFlxhjbxnGsIEfAYoudVLbx4v1Iot7Xsf903nTG65tRRe0dHJtlAoYTHQKftODtTqq177siV82nUAPNm46bK5GT6dAXRpwZst11OGHUmAW2FTlyXe1zgO2Dn8OTNZBleFispeh4plAhjOOBJLuZdj7lRMu9P0dBGs0jWJryt94DKvUFOTBdEl4p8mwmQKGVOVF0FgbHwJlp6xCa0Uh3m39hkteFSFB35D774OTaHON2KYqSxgXm3uvHuDelb0ho4gh6AuaB3A2VMslVCN7yyyOFdApdWadojrfe7eNQkWHrKX3yntHt2byvcY0nKaC5Z0wGoLwsoIOQV2qMqQZ8p5	1981-07-04 15:54:34	1990-07-27 08:15:13
00df42a2-291a-4917-ac60-0acec68e4c16	KtDB5JxLH87hXeL	沈佳琪	柳河顺	91	99	oVO3qeid4Bghfnm	CwVfqTx6LESOd4Q	印度尼西亚	89UTfSIJTZqWK2l	宣城市	ZmvsRohCGxwmJGN	ExEi7OlCjyp18re	1987-04-22 17:14:36	W9K48RSB7sPq4WhW9lPTUSXpGJ2chYIgkUJ1AmyaGCR1ndVNVH9eSORo03iNO37mxhiRL08UE2BMix2tJhz2IGxrR1VrOegJwoD0kWGh1oOuokrI4Sgdye0TzFEngFQyHw3tIZAIZIUOaP144Q1pwZeQrlZjuJ3GOfhLrR3OZR8kNwkwhnl6kR1SlAsOMw2k22zwOKSP1OMiVGIzRcA90DN5lOwv1D1xaVjKS8lnh5Mw2	2003-10-07 07:07:03	2024-06-20 00:03:54
c45edd34-2023-4b60-86d2-4ad6c815896e	YftxWzqSjssKIh2	贾义诚	曾娅凝	40	89	kVwrsKyLtlNkxNV	lEWWdEJkWgeqxrB	匈牙利	GAibyyaDDoZmium	张家口市	RJSmeeQax8ptKq2	IYba7aRw7NlZ6T7	1990-03-25 06:46:18	lPzKyKtos38UZExO2B706cWNTwMMD6S3HPxHfpD9DiaZeot04wsFG36aqNg7zuuDtO3OEtsbYABNg1ib3N64bRVC6C8vBs3lOePl9BJQ3WLzifIqUCOOCjeqfvYadcrmqMxPd0fP0H4n1BIsgnu7793ZpmdvsYqxVINv64fDrX9TQdvSZ3a0dRPlMtjBuhqRqjYLcd0YYV9rlbNJWGS3QTeWYG2imMOGYKZ8Sn7MiDMIdNNTA2ezGNOuL8h8Gt4k3E2zXebjPGpTvzcgZyrC9q	1980-03-28 07:29:00	1996-01-25 05:03:59
ce50afb4-ec6d-416e-91b7-b527f7a07abd	rLsYa4lnauGsnOg	关欣妍	谷艳巧	23	60	1TmLNqehQX5kmiD	7HYJQjzRMPbI2eH	密克罗尼西亚联邦	w9xdJaMl7MZW8oQ	西宁市	nc2n36mBU7CxndT	QxFQHN8cEmmGgW2	2008-07-16 02:11:38	lzcRhDoJAoJ4KXBEycUS0CKL4Lm6p3DWNpmw2lYA2wPfRRNeAr8yR21o2pI8n6nsLplNqxxJ0xjrtWRxrhyobc9gehMQVBaeKikKMq99XaGz5EJPWZiS6HHeyBqWGrupmXhb8NhHwUQFTwi6oPlszLnQSISx6kWfHdrY5iYEK2rkeIs8ZzJs4Umf6IdxZIHLHILb8A3EGqMZZGRxlkigZuvZZIfw5clYrb8wfpXqnPLzAGAsB1VEcNaJnTBu3uxDVBapJostpmNjqLMt6XUHqZbE8eiBHXNDMofG1HJp08t51UzX4cqaRWZtCHNuwn9gG2Wu625abvg2dfSAkXaqiLsjhBrfck6mJTEpQHpoIf0Tz6S8ZtdpjR0vXCGPBCrsGii9r8ghmvWekOyUs8X4rZYBZtscWuGTLcw75iKjEXAFp7XdwH5peW6LqKSuhuw3CI3klgNOfsHl1rVmEAzhJeSdulPuVZKL0q75gOTFQXD9xJwXqwJ6WRP3wv9MmHWmV6xrcU7ejtZQLltDBrFSuVslEyL3ssGy1oeVtrgWCkAUivXa5	1995-11-24 15:00:39	2018-10-24 08:26:53
2ff609a6-da58-4045-9e52-f6a7bd98cc33	laE5QuD9U0nyl20	丛浩宇	牛文	11	34	NTfTJOg1IN31Nt4	dfoUpKmcI0JJEWC	北塞浦路斯*	qTuJnp7aCYzvUUY	海西蒙古族藏族自治州	nukAL6V6FVK9RUD	A5vG5gU6wy4QDFf	2018-03-17 23:09:12	dbalYUxxZjdwUY5cUsfvfgI2rA8nNtSHuhSofnFbFwLhVwX8mKWoThBiIGdw60Lr0rroUFP7EEZJB2CuadeIvvbUhyfSSiMzvOCF165qdKZh8EVBkGdeyiq1k3FtsNBdeNDJDr6d7eeByjQb7S5nw9jP4CxlFLWRO30R0ptZ5zGERmUeBG6l8lokQVYoxua3nlyAQ0y4HSP1dHMvqLcObXJdGhULhjmxthtln1hCiAMWT3h1wpyYFNugtbI9EItX1g0wNutlRZLQMPRs3eaCjYYKAUgoLF794X1PBgKpeYkQ7DuEtz6NkbwLkLyqGuY3g1MZaHyEU7XRSFE27zr5nMLtGpOVowZ6M7XPMJ5pym8y6BxOHJdqxMQJwHNjq5YF3uNPU95wXMddwgl3gZ9K5yCgL5dlV90z0liM8S9WO4nFtm50zhdsdmHfWrkE3Kn6BBIyxD	1975-01-09 21:43:38	1978-11-15 17:41:15
621ae0b3-4237-4e80-947e-1649b57b2253	zO4XmDRYMZa1tjV	熊虹雄	柴克龙	23	11	制造业	qdVGhBqzySi8yhy	格林纳达	甘肃	银川市	pl70eL7Vp9Zc22f	active	2023-05-30 00:14:38	x7RoI1Apu8fnfGD3GtHo8HbGkewf1hJ241MlBRFPkmrCDZW4eB6BCvFZ38HiDkgGZC5q13vBvzhIw2Erv5Zk8FE8qnzaqsJtnU8WYigRrHZy1cf9UmcNqQ2QXIp75yrkaUNih6A5uvISCkVcokzziVj1RdoW05DBqeXqZxRF1Lu7nwG6cvzpp1ERCWLpCZX2Ox1SDzZwUXiTowaiS6VGv4oCYdZEzJCoowGYICbolZLDHFGGISN0SotYFiZWp0qx5xGLcrERG2HD1qSJqPUcFTcXm3SIBz9uFSGiTkr9PgG6hKXLMX0jRMzR1q3GgVhZyaQMVMS83Odu6HvBMvnRHJasUslbj7IOKAULOhoFO1uhQSAJB3EWGLweIpKWIP8p4RRzjSgGYT7tqMyQKaQhOQIRWQHbeErXUejjF1L9lIJ7Zk1utFAfFfjKTACUJFuX5Le9CetG789VwjWp2VoZygNkkbUoEIIog8tx	2014-07-29 12:52:04	2017-11-13 08:52:35
\.


--
-- Data for Name: employee_leave; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.employee_leave (id, employee_id, employee_name, start_date, end_date, leave_type, reason, created_at) FROM stdin;
c69f25b0-2ad6-4a7d-bd2e-efa75f217fe1	e3e45710-2408-45ae-ba6e-54e0691506f5	伟琪	2026-03-03	2026-03-04	调休		2026-03-03 10:44:02.541794
3ade4bbf-8efb-457c-9522-76a51d23b8fb	72cc5448-bb49-42d0-a873-8d22e206eb54	文慧	2026-03-03	2026-03-03	请假	病假	2026-03-03 10:43:38.464477
\.


--
-- Data for Name: project_file; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.project_file (id, translation_project_id, file_name, storage_path, file_type, file_ext, file_size, storage_type, uploaded_by, created_at) FROM stdin;
\.


--
-- Data for Name: role; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.role (id, role_name, description) FROM stdin;
55e89dc0-243f-45c0-adb0-05c1a3b9d348	超级管理员	系统超级管理员，可访问所有功能
dcd94cfa-8b9e-4493-a2cc-d694dd00fe9c	项目经理	仅可访问笔译项目管理
65aeb506-5438-408c-a292-04be84f40d73	测试	测试
b1e902df-ce20-4d56-b339-87d194e3a262	客户专员	仅可访问笔译项目管理
795f6146-2ff9-449f-b634-c372c9d4d2d2	项目专员	仅可访问笔译项目管理
982c21de-585f-4171-b27b-d09f2446557a	译审	仅可访问笔译项目管理
fb884bdc-de4a-44b4-8cd5-ada5dee0adf3	销售	仅可访问笔译项目管理
f5f66f29-5822-4b6c-ba48-342a18eca296	项目助理	\t\n仅可访问笔译项目管理
5dfa1d12-9f43-4e8e-9a3b-c0fc002469dd	排版专员	仅可访问笔译项目管理
\.


--
-- Data for Name: translation_project; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.translation_project (id, order_no, project_name, file_type_secondary, client_id, customer_reception_time, customer_deadline_time, sent_to_client_time, client_feedback, project_status, pm_confirmed_by, translator_id, translator_assignment_time, expected_translator_stats_method, expected_translator_word_count, translator_delivery_progress, pre_review_qc_progress, review1_progress, review2_progress, post_review_qc_progress, layout_progress, consolidation_progress, created_by, created_at, updated_at) FROM stdin;
185e9769-af62-473a-be28-bdb777f7eaa6	PRJ-20260228-0004	[谷艳巧] 测试翻译项目批次 490	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	1a55179f-026e-44f7-ac5d-c32bed603515	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	1a55179f-026e-44f7-ac5d-c32bed603515	2026-02-28 16:02:11.7579	2026-02-28 16:02:11.7579
ac6b248a-48aa-48ff-805f-c5e8d2852dbf	PRJ-20260228-0005	[曾娅凝] 测试翻译项目批次 363	\N	c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.765485	2026-02-28 16:02:11.765485
87d986e8-bb24-4e89-8407-3b6af6d8547f	PRJ-20260228-0006	[金希元] 测试翻译项目批次 531	\N	4276a053-4cd7-4abc-87b7-a685a3044931	\N	\N	\N	\N	pending	1a55179f-026e-44f7-ac5d-c32bed603515	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	1a55179f-026e-44f7-ac5d-c32bed603515	2026-02-28 16:02:11.772405	2026-02-28 16:02:11.772405
68644150-264c-4d8b-b040-47bf0498e0ec	PRJ-20260228-0007	[宋尤] 测试翻译项目批次 296	\N	88bc493e-e357-4600-9de7-4a507be5e9fd	\N	\N	\N	\N	pending	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	b2c53252-9cb5-476e-b289-13019ad69c78	2026-02-28 16:02:11.780904	2026-02-28 16:02:11.780904
f2e1ba83-141b-4c0a-a460-a2265ea96788	PRJ-20260228-0008	[柳河顺] 测试翻译项目批次 533	\N	00df42a2-291a-4917-ac60-0acec68e4c16	\N	\N	\N	\N	pending	d7116c76-ae7c-4624-9e5b-4bad4418c74d	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-02-28 16:02:11.788583	2026-02-28 16:02:11.788583
edc19c21-49dd-4118-b066-daa4dd728411	PRJ-20260228-0009	[谷艳巧] 测试翻译项目批次 610	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.795767	2026-02-28 16:02:11.795767
a383da7c-6457-4a13-a837-ea8a5e00a805	PRJ-20260228-0010	[宋尤] 测试翻译项目批次 170	\N	88bc493e-e357-4600-9de7-4a507be5e9fd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.802266	2026-02-28 16:02:11.802266
2de21aed-d67d-4e02-9f8b-a978973bfc6f	PRJ-20260228-SQL001	[曾娅凝] SQL直插测试项目批次 422	\N	c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
858c1e78-ad24-4ffb-9c5b-6bd645a6fc55	PRJ-20260228-SQL002	[牛文] SQL直插测试项目批次 771	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	74c04077-ea7c-4978-9735-10413dc62aa3	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
9d869ebf-3d55-477d-a4db-0ec4e9c1488c	PRJ-20260228-SQL003	[于梓萱] SQL直插测试项目批次 673	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	fb5c69c5-e422-48e7-9214-025aacee74b0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	fb5c69c5-e422-48e7-9214-025aacee74b0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
e95e6db2-3b58-4311-8525-e6691448829b	PRJ-20260228-SQL004	[于梓萱] SQL直插测试项目批次 115	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
b2b5fc81-163b-4497-a752-c7bff86d2d5e	PRJ-20260228-SQL005	[谷艳巧] SQL直插测试项目批次 314	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	b2c53252-9cb5-476e-b289-13019ad69c78	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
c3cc69e8-f65b-42c3-bb7a-1628215a73e9	PRJ-20260228-SQL006	[谷艳巧] SQL直插测试项目批次 165	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	74c04077-ea7c-4978-9735-10413dc62aa3	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
8bacd012-a839-411c-9020-dd85d35d5c7d	PRJ-20260228-SQL007	[曾娅凝] SQL直插测试项目批次 525	\N	c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
efed205d-a908-4bb2-955a-0e1eb2c3c81b	PRJ-20260228-SQL008	[漕启鸣] SQL直插测试项目批次 805	\N	59e14867-dea0-49d4-bc14-220002a416e7	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
a3bb5bb9-11a1-4dc2-9b21-640848ed716a	PRJ-20260228-SQL009	[于梓萱] SQL直插测试项目批次 483	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
42d2955b-d66a-4568-938e-896b2ba4cff7	PRJ-20260228-SQL010	[柴克龙] SQL直插测试项目批次 312	\N	621ae0b3-4237-4e80-947e-1649b57b2253	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
be8e9dcd-8ba9-410f-ba19-64aa51c99dd0	PRJ-20260302-0002	[柴克龙] 测试翻译项目批次 856	\N	621ae0b3-4237-4e80-947e-1649b57b2253	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:45:34.372763	2026-03-02 11:45:34.372763
f3f59a1d-d792-4722-971d-63ebe9fd06cb	PRJ-20260302-0003	[牛文] 测试翻译项目批次 267	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-03-02 11:45:34.389738	2026-03-02 11:45:34.389738
12eb4bfd-8bd6-4a34-8010-5045d2c4fd6b	PRJ-20260302-0001	[隋信灿] 测试翻译项目批次 254	\N	4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:43:26.146969	2026-03-02 11:43:26.146969
c3730723-a1e9-4be0-8a17-1082355a74c8	PRJ-20260228-0001	[漕启鸣] 测试翻译项目批次 239	测试	59e14867-dea0-49d4-bc14-220002a416e7	\N	\N	\N	\N	进行中	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N		\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:02:11.714498	2026-02-28 16:02:11.714498
7b50514a-672d-49a6-9254-c2a470c91b29	PRJ-20260302-0004	[谷艳巧] 测试翻译项目批次 683	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	b2c53252-9cb5-476e-b289-13019ad69c78	2026-03-02 11:45:34.397776	2026-03-02 11:45:34.397776
92c71151-584c-4d70-a657-f85c472c9390	PRJ-20260302-0005	[谷艳巧] 测试翻译项目批次 950	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	74c04077-ea7c-4978-9735-10413dc62aa3	2026-03-02 11:45:34.403402	2026-03-02 11:45:34.403402
bed7e3f0-d977-4fe9-b9ea-b079d55cde6d	PRJ-20260302-0006	[牛文] 测试翻译项目批次 547	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:45:34.410117	2026-03-02 11:45:34.410117
1cd973e9-9210-41f8-ba6c-0b54bd9f8c95	PRJ-20260302-0007	[牛文] 测试翻译项目批次 757	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	d7116c76-ae7c-4624-9e5b-4bad4418c74d	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-03-02 11:45:34.416105	2026-03-02 11:45:34.416105
d120d9f7-b0ab-46b1-9b03-e85a67666490	PRJ-20260302-0008	[牛文] 测试翻译项目批次 726	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.422296	2026-03-02 11:45:34.422296
04d91a87-f7a0-4bf6-a899-557ec5ce2c36	PRJ-20260302-0009	[谷艳巧] 测试翻译项目批次 809	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.428856	2026-03-02 11:45:34.428856
3e50a26e-61a6-4bbe-9c80-0e05ad4d10ea	PRJ-20260302-0010	[谷艳巧] 测试翻译项目批次 508	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-03-02 11:45:34.434834	2026-03-02 11:45:34.434834
4ee5ca74-8e91-4f15-a388-9d820a7f84f4	PRJ-20260302-0011	[金希元] 测试翻译项目批次 342	\N	4276a053-4cd7-4abc-87b7-a685a3044931	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.441294	2026-03-02 11:45:34.441294
c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	PRJ-20260302-0012	吉利		\N	2026-03-02 00:00:00	2026-03-04 00:00:00	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:09:43.396552	2026-03-02 20:09:43.396552
cc1c7817-b53d-472d-bfad-6051a0fbc323	PRJ-20260302-0013	[谷艳巧] 测试翻译项目批次 610		ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:13:15.630647	2026-03-02 20:13:15.630647
1a58dfb0-8324-4cdb-a9ed-994ab0a7da9c	PRJ-20260302-0014	[谷艳巧] 测试翻译项目批次 610		ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:13:27.625592	2026-03-02 20:13:27.625592
c9fcc0e2-256a-4455-8917-a9b5e4daed5e	PRJ-20260302-0015	1231231		\N	\N	\N	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:33:30.95642	2026-03-02 20:33:30.95642
a4d82da0-7827-4ccd-ab05-0dc20d90e174	TP-260304-002	12312312		\N	\N	\N	\N		completed	\N	\N	\N	\N	\N								\N	2026-03-04 15:14:24.257329	2026-03-04 15:14:24.257329
1c984f07-d318-473d-9fe2-921c3bec1dad	PRJ-20260228-0003	[隋信灿] 测试翻译项目批次 840	\N	4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	\N	\N	\N	已暂停	fb5c69c5-e422-48e7-9214-025aacee74b0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	fb5c69c5-e422-48e7-9214-025aacee74b0	2026-02-28 16:02:11.750898	2026-02-28 16:02:11.750898
d82e59de-f57f-4c13-a225-7c4637e44627	PRJ-20260228-0002	[隋信灿] 测试翻译项目批次 603		4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	\N	\N	\N	进行中	e228c697-4885-41a3-a02f-ef389defedd0	\N	2026-03-03 00:00:00	\N	\N	进行中	\N	\N	\N	\N		\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.739266	2026-02-28 16:02:11.739266
c63d97a1-aa7f-449c-8bf2-83c1cbcf074f	TP-260304-001	1231231		\N	\N	\N	\N		in_progress	\N	\N	\N	\N	\N								\N	2026-03-04 15:14:17.950319	2026-03-04 15:14:17.950319
\.


--
-- Data for Name: translator; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.translator (id, translator_code, translator_name, cooperation_type, contact_info, created_at, updated_at, translation_type, quality_score, cloud_revision, daily_rate, direction, default_priority, schedule_remarks, languages, gender, height, appearance, nationality, ethnicity, phone, phone2, email1, email2, resume_path, other_contact, overdue_count, overall_rating, first_contact_date, remarks) FROM stdin;
f05ebce4-fb4b-4b04-90c2-4318e89a795b	T_wangting	王婷	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	73	-	5/1000/8000	zh_en	2	法律类需审改，其他中英要求不是很高的可基本检查	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
cf8eb435-202e-4c12-9bbe-7ef9e1d49b12	T_gaochao	高超	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	73	可/可	5/1000/8000	zh_en	1	大概仅适合银行，法律类需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
c2471f0f-288d-48ab-8ae6-6f1fcf84bab9	T_sunhy	孙红艳	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	74	可/可	2/500/2000	zh_en	0	中英要求不高的均可基本检查	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
96b29f08-9bce-4e69-b779-5ea6b052f3df	T_shangying	商莹	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	74	可/可	3/500/3000	zh_en	1	不接法律和医学	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
683d070d-734c-4abc-ac62-89daf3683b69	T_chenfeng	陈风	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	73	-	?/?/7000	zh_en	0	需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
50d887bd-75d9-4712-ae4f-e417cf29df17	T_leizhi	雷智	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	74	-	?/?/4000	zh_en	2	需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
47328d15-8437-44b1-af56-81a82ab11ea1	T_hecq	何长青	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	74	-	?/?/4000	zh_en	0	需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
ecfd6a51-f7d4-480e-af39-55c941b77fe6	T_lilusa	李鲁莎	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	73	-	?/?/6000	zh_en	1	需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
f46cd8fc-b8c8-453c-aad6-883a40c9f72b	T_shimy	史明月	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部（不适合对中文要求高的）	74	可/未知	1/500/4000	en_zh	2	工作日中午和下午不能做稿，一般需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
d2bc8ca3-44af-47a6-8768-23b3f8991346	T_yangxue	杨雪	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部（法律类优先）	75	可/未知	5/350/3000	en_zh	1	律师，一般需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
0b3b416f-51c6-46e8-bdb0-3c10459c9737	T_liangcj	梁昌金	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	75	可/未知	-	en_zh	1	一般需审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
aee396ff-5574-4b8f-8d8d-09b9e121b82b	T_xiongjl	熊建磊	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	75	可/未知	-	en_zh	1	一般要审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
d3abc7ee-db52-4e13-9c07-629ce31aa448	T_zhanglh	张留寰	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	75	可/未知	-	en_zh	1	一般要审改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
73f523e6-b4d8-4c2a-8832-b5c1ea09c211	T_qiaoyh	乔艳红	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	75	可/可	?/?/7000	en_zh	1	急稿可不改	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
4bdf9026-0e3f-4359-8b58-35d1195d8583	T_wangsl	王邃玲	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	80	可/可	5/1000/6000	both	3	法律类需安排审改；英译中质量78，注意优先安排中英项目	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
049b95ee-95df-42aa-bbe9-e13f25304825	T_caoly	曹柳云	\N	\N	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	全部	74	可/可	5/500/4000	both	0	非合同法律类需审改；中英/英中均可	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	0	\N	\N	\N
\.


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_role (id, user_id, role_id, created_at) FROM stdin;
3e5a2993-8166-42fa-85f6-1072d8e37b4c	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	65aeb506-5438-408c-a292-04be84f40d73	2026-01-16 16:01:00.808532
3e65b4d3-cfa4-4ae0-9cea-e957f24b6eeb	ba92e52a-f517-48a4-a422-1688f2afe067	55e89dc0-243f-45c0-adb0-05c1a3b9d348	2026-02-05 16:40:36.67509
6285b470-2c60-4d2c-9a56-29875ed463d1	1a55179f-026e-44f7-ac5d-c32bed603515	b1e902df-ce20-4d56-b339-87d194e3a262	2026-02-05 16:44:08.94538
7cf363ef-3e37-498d-abfc-003c0a170d2d	74c04077-ea7c-4978-9735-10413dc62aa3	dcd94cfa-8b9e-4493-a2cc-d694dd00fe9c	2026-02-05 17:06:45.525326
b7959652-399c-41ca-96d3-00b6f9f52bdc	b2c53252-9cb5-476e-b289-13019ad69c78	795f6146-2ff9-449f-b634-c372c9d4d2d2	2026-02-07 17:28:00.839675
49b19ba2-ead8-44e5-b173-e3d3b2c380a0	d7116c76-ae7c-4624-9e5b-4bad4418c74d	fb884bdc-de4a-44b4-8cd5-ada5dee0adf3	2026-02-07 17:28:54.77878
8f06f801-1611-4f74-ab4b-651ada208914	e228c697-4885-41a3-a02f-ef389defedd0	f5f66f29-5822-4b6c-ba48-342a18eca296	2026-02-09 19:19:30.97515
d1e9f971-8132-46bf-9477-4430ca75f05b	fb5c69c5-e422-48e7-9214-025aacee74b0	5dfa1d12-9f43-4e8e-9a3b-c0fc002469dd	2026-02-10 16:27:31.336197
ef7694f9-2c22-4666-9623-92e2fd590253	b9e7efff-0da1-41a0-9925-35f4ebf99fc9	795f6146-2ff9-449f-b634-c372c9d4d2d2	2026-03-02 15:59:34.123391
779171d9-8a4c-4781-ad37-6866f66d438e	e3e45710-2408-45ae-ba6e-54e0691506f5	795f6146-2ff9-449f-b634-c372c9d4d2d2	2026-03-02 16:43:57.819969
5c583856-5578-45a6-89e0-83515894cb5e	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	b1e902df-ce20-4d56-b339-87d194e3a262	2026-03-02 16:54:38.647095
48e38aff-3a3c-4301-be6a-a0c1f0876d94	bc55fda0-78d1-492b-804c-0c59607c3922	5dfa1d12-9f43-4e8e-9a3b-c0fc002469dd	2026-03-02 16:56:23.614043
1344c98e-c911-45d3-8cb5-3960db6ca9fc	f174bde7-af8b-4c28-b94e-4d2c07bab29c	f5f66f29-5822-4b6c-ba48-342a18eca296	2026-03-02 16:57:07.021629
dbfe78c3-a44b-4cca-a61c-e7d34905694a	2bdefb2f-b23e-447f-903c-ede4dbf72cbb	982c21de-585f-4171-b27b-d09f2446557a	2026-03-04 18:16:38.030988
\.


--
-- Data for Name: work_schedule; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.work_schedule (id, schedule_date, shift_table, leave_notes, urgent_table_zh_en, urgent_table_en_zh, dept_person_data, not_scheduled_tasks, pm_rotation_order, updated_by, created_at, updated_at) FROM stdin;
8800fe57-05c2-4a95-a1c3-f809ee32c936	2026-03-02	[{"hr": "翠珍", "shift": "早早班 8:30-18:00", "client": "靖琳、楚翘", "layoutIt": "", "translationProject": "伟琪"}, {"hr": "雅然、辛建、文慧", "shift": "早班 9:00-18:30", "client": "瑞珠", "layoutIt": "胜辉、浚轩、裕林、晨旭", "translationProject": "以龙、志林"}, {"hr": "立溶、舒婷、宇琪", "shift": "9:30-18:30", "client": "家铭（9点半）", "layoutIt": "", "translationProject": "旷姣"}, {"hr": "紫霞", "shift": "晚班 10:30-20:00", "client": "舒倩(晚班)", "layoutIt": "美霞、苗丹、黄萌", "translationProject": "振中、孟花"}, {"hr": "颖琦、少洁、菀筠", "shift": "晚晚班 13:30-21:30", "client": "烨珊", "layoutIt": "大杰", "translationProject": "李娴"}, {"hr": "", "shift": "8:45~9:30", "client": "少妃、陈佳、韵钰", "layoutIt": "泉哥、武哥（销售）", "translationProject": "Thomas"}]	["武哥周五（2月6日）12:00后请假", "Thomas周五（0206）14:00开始请假，7、8点在家办公", "陈佳0206上午请假，0206下午、0208-0210、0215在家办公共5天，0211-0214请假4天", "瑞珠2月11日-14日（周三至周六）休年假", "以龙2月11日-14日请假四天", "美霞0213-0214调休两天"]	[{"name": "王婷", "type": "全部", "order": "2 中午12点后", "quality": "73", "remarks": "法律类需审改，其他中英要求不是很高的可基本检查", "cloudRev": "-", "dailyRate": "5/1000/8000"}, {"name": "王邃玲", "type": "全部", "order": "3 傍晚5点后", "quality": "80", "remarks": "法律类需安排审改", "cloudRev": "可/可", "dailyRate": "5/1000/6000"}, {"name": "高超", "type": "全部", "order": "1", "quality": "73", "remarks": "大概仅适合银行，法律类需审改", "cloudRev": "可/可", "dailyRate": "5/1000/8000"}, {"name": "曹柳云", "type": "全部", "order": "N/A", "quality": "73", "remarks": "非合同法律类需审改", "cloudRev": "可/可", "dailyRate": "-"}, {"name": "孙红艳", "type": "全部", "order": "0", "quality": "74", "remarks": "中英要求不高的均可基本检查", "cloudRev": "可/可", "dailyRate": "2/500/2000"}, {"name": "商莹", "type": "全部", "order": "1", "quality": "74", "remarks": "不接法律和医学", "cloudRev": "可/可", "dailyRate": "3/500/3000"}, {"name": "陈风", "type": "全部", "order": "N/A", "quality": "73", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/7000"}, {"name": "雷智", "type": "全部", "order": "2 中午12点后", "quality": "74", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/4000"}, {"name": "何长青", "type": "全部", "order": "N/A", "quality": "74", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/4000"}, {"name": "李鲁莎", "type": "全部", "order": "1", "quality": "73", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/6000"}]	[{"name": "史明月", "type": "全部（不适合对中文要求高的）", "order": "2（白天不做稿）", "quality": "74", "remarks": "工作日中午和下午不能做稿，一般需审改", "cloudRev": "可/未知", "dailyRate": "1/500/4000"}, {"name": "杨雪", "type": "全部（法律类优先）", "order": "1", "quality": "75", "remarks": "律师，一般需审改", "cloudRev": "可/未知", "dailyRate": "5/350/3000"}, {"name": "王邃玲", "type": "全部（中文较好）", "order": "N/A", "quality": "78", "remarks": "注意优先安排中英项目", "cloudRev": "可/可", "dailyRate": "5/500/4000"}, {"name": "曹柳云", "type": "全部", "order": "N/A", "quality": "75", "remarks": "一般需审改", "cloudRev": "可/可", "dailyRate": "5/500/4000"}, {"name": "梁昌金", "type": "全部", "order": "1", "quality": "75", "remarks": "一般需审改", "cloudRev": "可/未知", "dailyRate": "5/500/4000"}, {"name": "熊建磊", "type": "全部", "order": "1", "quality": "75", "remarks": "一般要审改", "cloudRev": "可/未知", "dailyRate": "-"}, {"name": "张留寰", "type": "全部", "order": "1", "quality": "75", "remarks": "一般要审改", "cloudRev": "可/未知", "dailyRate": "-"}, {"name": "乔艳红", "type": "全部", "order": "1", "quality": "75", "remarks": "急稿可不改", "cloudRev": "可/可", "dailyRate": "?/?/7000"}]	[{"dept": "项目经理", "name": "伟琪", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "整理词汇并上传术语库（完成项目任务后再做）", "category": "直接项目任务", "deadline": "", "projectNo": "爱彼"}, {"content": "1.2w跟进：舒婷派王珊娜，导出完整版译文、给颖琦派专检排版", "category": "直接项目任务", "deadline": "2月9日9:30", "projectNo": "TP260205004"}, {"content": "剩06：60w+，李鲁莎已回，已发惠喜专检+排版，周日下午6点回", "category": "直接项目任务", "deadline": "周日下午6点", "projectNo": "TP260115013"}], "status": "scheduled", "fixedTasks": ["登记文件属性", "每月专检稽查（崔盼盼、水雅丽）"]}, {"dept": "项目经理", "name": "李娴", "tasks": [{"content": "待安排的分析、继续已安排的分析、跟进自己的项目", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "461份（961页）分析及跟进：英文转录已完成，其他语种继续转录", "category": "直接项目任务", "deadline": "2026年3月22日17点", "projectNo": "TP251224018"}, {"content": "2.5k，翠珍派沙柏霖，HR收稿时确认词汇及QA", "category": "直接项目任务", "deadline": "2月9日10点", "projectNo": "TP260205025"}, {"content": "2.8k跟进：11语种，各译员回稿后专检排版、验收", "category": "直接项目任务", "deadline": "2月10日下午17点", "projectNo": "TP260205016"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（戴欣然、刘惠喜）"]}, {"dept": "项目经理", "name": "孟花", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "跟进：英语已派孙红艳检查反馈，繁体已派贺媛处理更新", "category": "直接项目任务", "deadline": "尽快回", "projectNo": "TP251224029"}, {"content": "大概15万中朝，MT后抽查、HR派数检、运坚还原、前中后抽查", "category": "直接项目任务", "deadline": "2月8日晚18点", "projectNo": "TP260202012"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（王雨菡、陈慧楠）", "整理词汇（待定）"]}, {"dept": "翻译部", "name": "少妃", "tasks": [{"content": "词汇整理+句式跟进等非项目任务、跟进自己的项目", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "译员开拓跟进：哈萨克/乌克兰/格鲁吉亚/阿塞拜疆语", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "项目安排：185份Excel 40w跟进、483页整理跟进、13w分析跟进", "category": "直接项目任务", "deadline": "", "projectNo": "TP260121020 等"}], "status": "scheduled", "fixedTasks": []}, {"dept": "翻译部", "name": "陈佳", "tasks": [{"content": "跟进招聘项目、安排邮件", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "10w（37份）跟进：文件15-29已派王婷修订，周六9点回", "category": "直接项目任务", "deadline": "2月8日9:30/2月25日9:30", "projectNo": "TP260119005"}, {"content": "尼泊尔/英译中 审改", "category": "直接项目任务", "deadline": "2月6日15点", "projectNo": "TP260204018"}, {"content": "3.6w 排版早上回，专检、基本检查，最后陈佳看看", "category": "直接项目任务", "deadline": "2月6日17点", "projectNo": "TP260202006"}, {"content": "8k，黎凤周五下午6点回，陈佳看看，颖琦派专检排版", "category": "直接项目任务", "deadline": "2月8日12点", "projectNo": "TP260205006"}, {"content": "19份，葡译中/德译中 审改", "category": "直接项目任务", "deadline": "2月9日17点", "projectNo": "TP260204020"}], "status": "scheduled", "fixedTasks": ["银行词汇", "信实翻译 中译小语种 机翻引擎测试"]}, {"dept": "翻译部", "name": "Thomas", "tasks": [{"content": "银行词汇", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "2.6k，彭霓周五早九点回，Thomas看看，瑞珠专检排版", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260204013"}, {"content": "4.6w（8k+1.2w+2.6w）跟进审改", "category": "直接项目任务", "deadline": "2月6日12点/16:30", "projectNo": "TP260203010"}, {"content": "4.5k 已审改，已一检，瑞珠二检及排版，最后Thomas验收", "category": "直接项目任务", "deadline": "2月13日17点", "projectNo": "TP260130008"}, {"content": "广州年鉴 中译英（母语）整体流程跟进", "category": "直接项目任务", "deadline": "2月13日17点", "projectNo": "TP260202007"}], "status": "scheduled", "fixedTasks": []}, {"dept": "项目部", "name": "旷姣", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "楚翘", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "6k排版已回，陈慧楠专检早八点半回，验收发客户", "category": "直接项目任务", "deadline": "2月6日9点", "projectNo": "TP260204003"}, {"content": "1.4k修订，黎凤早8:30回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205003"}, {"content": "900修订，曹柳云早八点半回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260205026"}, {"content": "王纵横 中译英（NAATI翻译）", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260130023"}, {"content": "吴先生 中译英（MTPE）", "category": "直接项目任务", "deadline": "2月6日下午18点", "projectNo": "TP260203015"}, {"content": "费雪尔 英译中（对照回稿）", "category": "直接项目任务", "deadline": "2月6日下午18点", "projectNo": "TP260204002"}, {"content": "胜美达 日译中", "category": "直接项目任务", "deadline": "2月6日下午17点", "projectNo": "TP260204019"}, {"content": "马小姐 英译中（代办澳洲海牙认证）", "category": "直接项目任务", "deadline": "2月10日下午18点", "projectNo": "TP260123012"}], "status": "not_scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "雅然", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260203005"}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205019"}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205028"}, {"content": "专检排版", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205027"}, {"content": "王雨菡检查修订+专检，早九点回，看是否需调整排版", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260204015"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "苗丹", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "杨雪周四晚十一点回，苗丹后续", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260205029"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "家铭", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "已派曹柳云，早八点半回，专检排版", "category": "直接项目任务", "deadline": "", "projectNo": "TP251226015"}, {"content": "杨雪周四晚回，专检排版", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260205030"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "黄萌", "tasks": [{"content": "专检排版", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260204027"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "武哥", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "靖琳", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "辛建", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "韵钰", "tasks": [{"content": "词汇整理+句式跟进等非项目任务", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "合肥思达智数信息科技，评测项目，多语种翻译质检", "category": "直接项目任务", "deadline": "2月28日23点", "projectNo": "TP260202003"}], "status": "scheduled", "fixedTasks": ["（暂停）项目专员培训资料调整", "（暂停）项目经理培训资料梳理、编写"]}, {"dept": "HR部", "name": "立溶", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "舒婷", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "百度地图上架", "category": "其他", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "宇琪", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "翠珍", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "紫霞", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "菀筠", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "爱企查上架", "category": "其他", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "颖琦", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "少洁", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "排版", "name": "运坚", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "排版", "name": "瑞珠", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "4k，已派王珊娜，早八点半回稿，专检排版", "category": "直接项目任务", "deadline": "2月6日10点", "projectNo": "TP260205022"}, {"content": "3.5k，已派廖伟燕修订，早九点回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日11:30", "projectNo": "TP260205020"}, {"content": "7k，柬译中（MTPE），专检排版", "category": "直接项目任务", "deadline": "2月6日15点", "projectNo": "TP260202014"}, {"content": "7k，已派陆素明，周五晚十点回，专检排版", "category": "直接项目任务", "deadline": "2月9日9:30", "projectNo": "TP260205023"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（梁承敏、沈佳佳）"]}, {"dept": "排版", "name": "大杰", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "大杰调整排版，运坚转HTML（吉利汽车客户反馈）", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": ["每月专检稽查（贺媛、孙晓燕）"]}, {"dept": "招聘项目", "name": "振中", "tasks": [{"content": "非直接项目任务、固定项目任务", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "销售", "name": "以龙", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "销售", "name": "志林", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}]	[{"remarks": "广州年鉴，中译英（母语），2月28日交", "projectNo": "TP260202016", "department": "翻译部", "personName": "-", "projectOrTask": "3w，李娴跟进：已派曹柳云9号早八点半回，Thomas审改，李娴导出完整版、给翠珍派一检二检，瑞珠排版，待安排内部细节检查"}]	伟琪 / 李娴 / 孟花	\N	2026-03-02 14:27:09.781481	2026-03-02 14:27:09.781481
c507b5f0-16fc-44c1-aa81-276b04f93643	2026-03-03	[{"hr": "翠珍", "shift": "早早班 8:30-18:00", "client": "靖琳、楚翘", "layoutIt": "", "translationProject": "伟琪"}, {"hr": "雅然、辛建、文慧", "shift": "早班 9:00-18:30", "client": "瑞珠", "layoutIt": "胜辉、浚轩、裕林、晨旭", "translationProject": "以龙、志林"}, {"hr": "立溶、舒婷、宇琪", "shift": "9:30-18:30", "client": "家铭（9点半）", "layoutIt": "", "translationProject": "旷姣"}, {"hr": "紫霞", "shift": "晚班 10:30-20:00", "client": "舒倩(晚班)", "layoutIt": "美霞、苗丹、黄萌", "translationProject": "振中、孟花"}, {"hr": "颖琦、少洁、菀筠", "shift": "晚晚班 13:30-21:30", "client": "烨珊", "layoutIt": "大杰", "translationProject": "李娴"}, {"hr": "", "shift": "8:45~9:30", "client": "少妃、陈佳、韵钰", "layoutIt": "泉哥、武哥（销售）", "translationProject": "Thomas"}]	["武哥周五（2月6日）12:00后请假", "Thomas周五（0206）14:00开始请假，7、8点在家办公", "陈佳0206上午请假，0206下午、0208-0210、0215在家办公共5天，0211-0214请假4天", "瑞珠2月11日-14日（周三至周六）休年假", "以龙2月11日-14日请假四天", "美霞0213-0214调休两天"]	[{"name": "王婷", "type": "全部", "order": "2 中午12点后", "quality": "73", "remarks": "法律类需审改，其他中英要求不是很高的可基本检查", "cloudRev": "-", "dailyRate": "5/1000/8000"}, {"name": "王邃玲", "type": "全部", "order": "3 傍晚5点后", "quality": "80", "remarks": "法律类需安排审改", "cloudRev": "可/可", "dailyRate": "5/1000/6000"}, {"name": "高超", "type": "全部", "order": "1", "quality": "73", "remarks": "大概仅适合银行，法律类需审改", "cloudRev": "可/可", "dailyRate": "5/1000/8000"}, {"name": "曹柳云", "type": "全部", "order": "N/A", "quality": "73", "remarks": "非合同法律类需审改", "cloudRev": "可/可", "dailyRate": "-"}, {"name": "孙红艳", "type": "全部", "order": "0", "quality": "74", "remarks": "中英要求不高的均可基本检查", "cloudRev": "可/可", "dailyRate": "2/500/2000"}, {"name": "商莹", "type": "全部", "order": "1", "quality": "74", "remarks": "不接法律和医学", "cloudRev": "可/可", "dailyRate": "3/500/3000"}, {"name": "陈风", "type": "全部", "order": "N/A", "quality": "73", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/7000"}, {"name": "雷智", "type": "全部", "order": "2 中午12点后", "quality": "74", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/4000"}, {"name": "何长青", "type": "全部", "order": "N/A", "quality": "74", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/4000"}, {"name": "李鲁莎", "type": "全部", "order": "1", "quality": "73", "remarks": "需审改", "cloudRev": "-", "dailyRate": "?/?/6000"}]	[{"name": "史明月", "type": "全部（不适合对中文要求高的）", "order": "2（白天不做稿）", "quality": "74", "remarks": "工作日中午和下午不能做稿，一般需审改", "cloudRev": "可/未知", "dailyRate": "1/500/4000"}, {"name": "杨雪", "type": "全部（法律类优先）", "order": "1", "quality": "75", "remarks": "律师，一般需审改", "cloudRev": "可/未知", "dailyRate": "5/350/3000"}, {"name": "王邃玲", "type": "全部（中文较好）", "order": "N/A", "quality": "78", "remarks": "注意优先安排中英项目", "cloudRev": "可/可", "dailyRate": "5/500/4000"}, {"name": "曹柳云", "type": "全部", "order": "N/A", "quality": "75", "remarks": "一般需审改", "cloudRev": "可/可", "dailyRate": "5/500/4000"}, {"name": "梁昌金", "type": "全部", "order": "1", "quality": "75", "remarks": "一般需审改", "cloudRev": "可/未知", "dailyRate": "5/500/4000"}, {"name": "熊建磊", "type": "全部", "order": "1", "quality": "75", "remarks": "一般要审改", "cloudRev": "可/未知", "dailyRate": "-"}, {"name": "张留寰", "type": "全部", "order": "1", "quality": "75", "remarks": "一般要审改", "cloudRev": "可/未知", "dailyRate": "-"}, {"name": "乔艳红", "type": "全部", "order": "1", "quality": "75", "remarks": "急稿可不改", "cloudRev": "可/可", "dailyRate": "?/?/7000"}]	[{"dept": "项目经理", "name": "伟琪", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "整理词汇并上传术语库（完成项目任务后再做）", "category": "直接项目任务", "deadline": "", "projectNo": "爱彼"}, {"content": "1.2w跟进：舒婷派王珊娜，导出完整版译文、给颖琦派专检排版", "category": "直接项目任务", "deadline": "2月9日9:30", "projectNo": "TP260205004"}, {"content": "剩06：60w+，李鲁莎已回，已发惠喜专检+排版，周日下午6点回", "category": "直接项目任务", "deadline": "周日下午6点", "projectNo": "TP260115013"}], "status": "scheduled", "fixedTasks": ["登记文件属性", "每月专检稽查（崔盼盼、水雅丽）"]}, {"dept": "项目经理", "name": "李娴", "tasks": [{"content": "待安排的分析、继续已安排的分析、跟进自己的项目", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "461份（961页）分析及跟进：英文转录已完成，其他语种继续转录", "category": "直接项目任务", "deadline": "2026年3月22日17点", "projectNo": "TP251224018"}, {"content": "2.5k，翠珍派沙柏霖，HR收稿时确认词汇及QA", "category": "直接项目任务", "deadline": "2月9日10点", "projectNo": "TP260205025"}, {"content": "2.8k跟进：11语种，各译员回稿后专检排版、验收", "category": "直接项目任务", "deadline": "2月10日下午17点", "projectNo": "TP260205016"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（戴欣然、刘惠喜）"]}, {"dept": "项目经理", "name": "孟花", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "跟进：英语已派孙红艳检查反馈，繁体已派贺媛处理更新", "category": "直接项目任务", "deadline": "尽快回", "projectNo": "TP251224029"}, {"content": "大概15万中朝，MT后抽查、HR派数检、运坚还原、前中后抽查", "category": "直接项目任务", "deadline": "2月8日晚18点", "projectNo": "TP260202012"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（王雨菡、陈慧楠）", "整理词汇（待定）"]}, {"dept": "翻译部", "name": "少妃", "tasks": [{"content": "词汇整理+句式跟进等非项目任务、跟进自己的项目", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "译员开拓跟进：哈萨克/乌克兰/格鲁吉亚/阿塞拜疆语", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "项目安排：185份Excel 40w跟进、483页整理跟进、13w分析跟进", "category": "直接项目任务", "deadline": "", "projectNo": "TP260121020 等"}], "status": "scheduled", "fixedTasks": []}, {"dept": "翻译部", "name": "陈佳", "tasks": [{"content": "跟进招聘项目、安排邮件", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "10w（37份）跟进：文件15-29已派王婷修订，周六9点回", "category": "直接项目任务", "deadline": "2月8日9:30/2月25日9:30", "projectNo": "TP260119005"}, {"content": "尼泊尔/英译中 审改", "category": "直接项目任务", "deadline": "2月6日15点", "projectNo": "TP260204018"}, {"content": "3.6w 排版早上回，专检、基本检查，最后陈佳看看", "category": "直接项目任务", "deadline": "2月6日17点", "projectNo": "TP260202006"}, {"content": "8k，黎凤周五下午6点回，陈佳看看，颖琦派专检排版", "category": "直接项目任务", "deadline": "2月8日12点", "projectNo": "TP260205006"}, {"content": "19份，葡译中/德译中 审改", "category": "直接项目任务", "deadline": "2月9日17点", "projectNo": "TP260204020"}], "status": "scheduled", "fixedTasks": ["银行词汇", "信实翻译 中译小语种 机翻引擎测试"]}, {"dept": "翻译部", "name": "Thomas", "tasks": [{"content": "银行词汇", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "2.6k，彭霓周五早九点回，Thomas看看，瑞珠专检排版", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260204013"}, {"content": "4.6w（8k+1.2w+2.6w）跟进审改", "category": "直接项目任务", "deadline": "2月6日12点/16:30", "projectNo": "TP260203010"}, {"content": "4.5k 已审改，已一检，瑞珠二检及排版，最后Thomas验收", "category": "直接项目任务", "deadline": "2月13日17点", "projectNo": "TP260130008"}, {"content": "广州年鉴 中译英（母语）整体流程跟进", "category": "直接项目任务", "deadline": "2月13日17点", "projectNo": "TP260202007"}], "status": "scheduled", "fixedTasks": []}, {"dept": "项目部", "name": "旷姣", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "楚翘", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "6k排版已回，陈慧楠专检早八点半回，验收发客户", "category": "直接项目任务", "deadline": "2月6日9点", "projectNo": "TP260204003"}, {"content": "1.4k修订，黎凤早8:30回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205003"}, {"content": "900修订，曹柳云早八点半回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260205026"}, {"content": "王纵横 中译英（NAATI翻译）", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260130023"}, {"content": "吴先生 中译英（MTPE）", "category": "直接项目任务", "deadline": "2月6日下午18点", "projectNo": "TP260203015"}, {"content": "费雪尔 英译中（对照回稿）", "category": "直接项目任务", "deadline": "2月6日下午18点", "projectNo": "TP260204002"}, {"content": "胜美达 日译中", "category": "直接项目任务", "deadline": "2月6日下午17点", "projectNo": "TP260204019"}, {"content": "马小姐 英译中（代办澳洲海牙认证）", "category": "直接项目任务", "deadline": "2月10日下午18点", "projectNo": "TP260123012"}], "status": "not_scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "雅然", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260203005"}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205019"}, {"content": "验收发客户", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205028"}, {"content": "专检排版", "category": "直接项目任务", "deadline": "2月6日9:30", "projectNo": "TP260205027"}, {"content": "王雨菡检查修订+专检，早九点回，看是否需调整排版", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260204015"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "苗丹", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "杨雪周四晚十一点回，苗丹后续", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260205029"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "家铭", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "已派曹柳云，早八点半回，专检排版", "category": "直接项目任务", "deadline": "", "projectNo": "TP251226015"}, {"content": "杨雪周四晚回，专检排版", "category": "直接项目任务", "deadline": "2月6日中午12点", "projectNo": "TP260205030"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "黄萌", "tasks": [{"content": "专检排版", "category": "直接项目任务", "deadline": "2月6日11点", "projectNo": "TP260204027"}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "武哥", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "靖琳", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "客户部", "name": "辛建", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "韵钰", "tasks": [{"content": "词汇整理+句式跟进等非项目任务", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "合肥思达智数信息科技，评测项目，多语种翻译质检", "category": "直接项目任务", "deadline": "2月28日23点", "projectNo": "TP260202003"}], "status": "scheduled", "fixedTasks": ["（暂停）项目专员培训资料调整", "（暂停）项目经理培训资料梳理、编写"]}, {"dept": "HR部", "name": "立溶", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "舒婷", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "百度地图上架", "category": "其他", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "宇琪", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "翠珍", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "紫霞", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "菀筠", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "爱企查上架", "category": "其他", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "颖琦", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "HR部", "name": "少洁", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "排版", "name": "运坚", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "排版", "name": "瑞珠", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "4k，已派王珊娜，早八点半回稿，专检排版", "category": "直接项目任务", "deadline": "2月6日10点", "projectNo": "TP260205022"}, {"content": "3.5k，已派廖伟燕修订，早九点回，检查修订及专检", "category": "直接项目任务", "deadline": "2月6日11:30", "projectNo": "TP260205020"}, {"content": "7k，柬译中（MTPE），专检排版", "category": "直接项目任务", "deadline": "2月6日15点", "projectNo": "TP260202014"}, {"content": "7k，已派陆素明，周五晚十点回，专检排版", "category": "直接项目任务", "deadline": "2月9日9:30", "projectNo": "TP260205023"}], "status": "scheduled", "fixedTasks": ["每月专检稽查（梁承敏、沈佳佳）"]}, {"dept": "排版", "name": "大杰", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}, {"content": "大杰调整排版，运坚转HTML（吉利汽车客户反馈）", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": ["每月专检稽查（贺媛、孙晓燕）"]}, {"dept": "招聘项目", "name": "振中", "tasks": [{"content": "非直接项目任务、固定项目任务", "category": "非直接项目任务", "deadline": "", "projectNo": ""}, {"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "销售", "name": "以龙", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}, {"dept": "销售", "name": "志林", "tasks": [{"content": "搜索自己名字", "category": "直接项目任务", "deadline": "", "projectNo": ""}], "status": "scheduled", "fixedTasks": []}]	[{"remarks": "广州年鉴，中译英（母语），2月28日交", "projectNo": "TP260202016", "department": "翻译部", "personName": "-", "projectOrTask": "3w，李娴跟进：已派曹柳云9号早八点半回，Thomas审改，李娴导出完整版、给翠珍派一检二检，瑞珠排版，待安排内部细节检查"}]	伟琪 / 李娴 / 孟花	\N	2026-03-02 16:26:04.875722	2026-03-02 16:26:04.875722
\.


--
-- Data for Name: workflow_instance; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.workflow_instance (id, translation_project_id, difficulty, file_editable, current_stage_key, current_assignee_id, project_status, stage_notes, stage_data, created_at, updated_at) FROM stdin;
b68b1897-1139-4317-80c8-2489edb2e988	185e9769-af62-473a-be28-bdb777f7eaa6	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.762264	2026-02-28 16:02:11.762264
3ef92b8e-c8b6-4873-a18f-2c56aff44f60	ac6b248a-48aa-48ff-805f-c5e8d2852dbf	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.769358	2026-02-28 16:02:11.769358
69563a01-6092-44b5-b687-d2238b05fd5a	87d986e8-bb24-4e89-8407-3b6af6d8547f	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.776867	2026-02-28 16:02:11.776867
534f8e68-dc5c-4528-a46f-606f46611728	68644150-264c-4d8b-b040-47bf0498e0ec	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.785409	2026-02-28 16:02:11.785409
2de2024e-52c0-4537-b963-be9f7fa3626b	f2e1ba83-141b-4c0a-a460-a2265ea96788	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.792893	2026-02-28 16:02:11.792893
e554de75-65b3-4f9b-aae2-99306410b37b	edc19c21-49dd-4118-b066-daa4dd728411	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.799714	2026-02-28 16:02:11.799714
23e7a18c-a9d2-4e13-8954-2157e0516996	a383da7c-6457-4a13-a837-ea8a5e00a805	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.806859	2026-02-28 16:02:11.806859
4072ba0a-306d-4055-9674-beec3a805e2a	2de21aed-d67d-4e02-9f8b-a978973bfc6f	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
8a6aaec1-faaf-4551-a252-32abc60c8180	858c1e78-ad24-4ffb-9c5b-6bd645a6fc55	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
8eb8946e-bcfe-4431-9ab7-f9888be9cb56	9d869ebf-3d55-477d-a4db-0ec4e9c1488c	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
02bc9842-d57e-443e-b212-76d005323904	e95e6db2-3b58-4311-8525-e6691448829b	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
32c69615-b5a6-4f32-a192-ac66a079c60a	b2b5fc81-163b-4497-a752-c7bff86d2d5e	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
78698395-06be-4898-980b-bbeb117f469b	c3cc69e8-f65b-42c3-bb7a-1628215a73e9	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
9ffb21ce-99b4-4c97-95c3-65497b91f698	8bacd012-a839-411c-9020-dd85d35d5c7d	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
22d46333-abca-4ab5-b51e-959716c0cbd9	efed205d-a908-4bb2-955a-0e1eb2c3c81b	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
ed986155-421c-45b9-a76c-fdf8258e6941	a3bb5bb9-11a1-4dc2-9b21-640848ed716a	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
9969eadf-44bc-4f48-a69a-94c32b0ac3f8	42d2955b-d66a-4568-938e-896b2ba4cff7	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747
fa30ce83-e2da-44eb-a2b1-92eb8c040ccb	7b50514a-672d-49a6-9254-c2a470c91b29	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.400821	2026-03-02 11:45:34.400821
87a1b169-1e1e-4c42-b086-c1b26718ff46	92c71151-584c-4d70-a657-f85c472c9390	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.407333	2026-03-02 11:45:34.407333
d2806189-51d6-404c-b7ce-a60e53d03d6a	bed7e3f0-d977-4fe9-b9ea-b079d55cde6d	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.413611	2026-03-02 11:45:34.413611
1e1f83a2-5278-406c-bccd-15fc493f76a5	1cd973e9-9210-41f8-ba6c-0b54bd9f8c95	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.41965	2026-03-02 11:45:34.41965
2b2c3a80-8051-4a47-8199-3921616e7d99	d120d9f7-b0ab-46b1-9b03-e85a67666490	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.426502	2026-03-02 11:45:34.426502
4e9b57dd-5ffd-488b-8346-9dd7657a06ae	04d91a87-f7a0-4bf6-a899-557ec5ce2c36	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.432493	2026-03-02 11:45:34.432493
37055887-4922-4d78-8d17-77363acd7d31	3e50a26e-61a6-4bbe-9c80-0e05ad4d10ea	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.438714	2026-03-02 11:45:34.438714
ce155bfd-fee9-4642-aa6c-4f8b782eda3d	4ee5ca74-8e91-4f15-a388-9d820a7f84f4	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.445152	2026-03-02 11:45:34.445152
4c8ef8aa-3a05-436b-996e-7c86faf354e8	d82e59de-f57f-4c13-a225-7c4637e44627	simple	t	completed	\N	completed	{"layout": "这个直接给客户专员交稿", "reception": "（无备注）", "special_qc": "直接排版", "project_assistant": "直接去专检", "project_specialist": "这是HR处理的阶段"}	{"layout": {"actualTime": "2026-03-03 09:29:01", "layoutNote": "", "estimatedTime": "", "projectStatus": "进行中", "layoutProgress": ""}, "reception": {"fileType": "", "wordCount": "", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": ""}, "special_qc": {"actualTime": "2026-03-03 09:27:31", "estimatedTime": "", "projectStatus": "进行中", "specialQcNote": "", "specialQcResult": ""}, "project_assistant": {"actualTime": "2", "estimatedTime": "1", "projectStatus": "进行中", "translatorAssignee": "孙红艳", "translatorAssignmentTime": "2026-03-03 00:00:00", "translatorDeliveryProgress": "进行中"}, "project_specialist": {"actualTime": "2026-03-03 09:23:54", "languagePair": "", "estimatedTime": "", "projectStatus": "进行中", "fileTypeSecondary": ""}}	2026-02-28 16:02:11.747316	2026-02-28 16:02:11.747316
c54ef09d-4918-4ec6-b3b5-a7515be25858	12eb4bfd-8bd6-4a34-8010-5045d2c4fd6b	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:43:26.160876	2026-03-02 11:43:26.160876
66bb4de4-01aa-458e-bfc9-fefde720875d	c3730723-a1e9-4be0-8a17-1082355a74c8	simple	t	project_assistant	e228c697-4885-41a3-a02f-ef389defedd0	in_progress	{"reception": "下一步", "project_specialist": "无问题"}	{"reception": {"fileType": "", "wordCount": "这是一个测试", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": "2026-03-02 00:00:00"}, "project_assistant": {"actualTime": "", "estimatedTime": "", "projectStatus": "进行中", "translatorAssignee": "", "translatorAssignmentTime": "", "translatorDeliveryProgress": ""}, "project_specialist": {"actualTime": "测试", "languagePair": "测试", "estimatedTime": "测试", "projectStatus": "已暂停", "fileTypeSecondary": "测试"}}	2026-02-28 16:02:11.731746	2026-02-28 16:02:11.731746
0b1e670a-d91e-42c6-b33a-46545aee8ca4	be8e9dcd-8ba9-410f-ba19-64aa51c99dd0	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.383733	2026-03-02 11:45:34.383733
533d9a5c-30a5-4c89-990f-684ac14c62ad	f3f59a1d-d792-4722-971d-63ebe9fd06cb	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.395095	2026-03-02 11:45:34.395095
12d400f9-0127-4f3b-af41-02454375793c	1c984f07-d318-473d-9fe2-921c3bec1dad	complex	f	project_manager	74c04077-ea7c-4978-9735-10413dc62aa3	in_progress	{"reception": "（无备注）", "layout_assign": "（无备注）"}	{"reception": {"fileType": "", "wordCount": "", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": ""}, "layout_assign": {"actualTime": "2026-03-04 18:03:29", "estimatedTime": "", "projectStatus": "进行中", "layoutAssignNote": ""}, "project_manager": {"priority": "", "wordCount": "", "actualTime": "", "estimatedTime": "", "projectStatus": "已暂停"}}	2026-02-28 16:02:11.755339	2026-02-28 16:02:11.755339
\.


--
-- Data for Name: workflow_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.workflow_log (id, workflow_instance_id, operator_id, from_stage, to_stage, direction, description, note, next_assignee_id, created_at) FROM stdin;
f19a2ac9-476e-4eb0-ae0b-5844b379a08b	66bb4de4-01aa-458e-bfc9-fefde720875d	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.731746
03496d39-c6a4-46fd-8276-0609304b311f	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.747316
03c725ce-c04b-4934-b909-fc7e02fc8d91	12d400f9-0127-4f3b-af41-02454375793c	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.755339
68f112e7-86f9-4283-b931-9013ccd902e6	b68b1897-1139-4317-80c8-2489edb2e988	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.762264
cae1bfae-5172-410d-bd1e-567c66377983	3ef92b8e-c8b6-4873-a18f-2c56aff44f60	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.769358
2eb3ee91-ba9b-4037-b3d0-3e05a715ff52	69563a01-6092-44b5-b687-d2238b05fd5a	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.776867
8e3f9eae-cb03-4337-bc0e-e4a0e70923db	534f8e68-dc5c-4528-a46f-606f46611728	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.785409
8e76674f-437c-4bdc-b5c2-473b1f0e9f48	2de2024e-52c0-4537-b963-be9f7fa3626b	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.792893
8f5a1bc6-b2d9-4ebd-bca8-049ff249439e	e554de75-65b3-4f9b-aae2-99306410b37b	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.799714
934e5608-dbfc-4f56-b687-2536b7560468	23e7a18c-a9d2-4e13-8954-2157e0516996	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-02-28 16:02:11.806859
5eadeb5a-e9e3-45a7-8c1e-a49c8ab82209	4072ba0a-306d-4055-9674-beec3a805e2a	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
54d0d9e5-b906-4494-acd5-4dbcf9513077	8a6aaec1-faaf-4551-a252-32abc60c8180	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
b8c3a074-1118-4e12-9d0c-f028e63e3c0c	8eb8946e-bcfe-4431-9ab7-f9888be9cb56	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
3485d5ae-5eb8-4a8a-8e35-6ec48ebca730	02bc9842-d57e-443e-b212-76d005323904	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
76e083ff-7915-42ba-b310-003bcdf9f679	32c69615-b5a6-4f32-a192-ac66a079c60a	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
46f4a471-7ea5-4524-902f-61cde243dd52	78698395-06be-4898-980b-bbeb117f469b	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
fc08fff7-019d-4804-b447-2161c0107411	9ffb21ce-99b4-4c97-95c3-65497b91f698	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
f3c0e2e0-f1d9-47a8-8686-b2441d732633	22d46333-abca-4ab5-b51e-959716c0cbd9	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
f5c23eb3-c0f8-4fd5-9bc8-ed10f86414ec	ed986155-421c-45b9-a76c-fdf8258e6941	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
9d4b1fee-9cd2-426e-b758-cb9c021a15b7	9969eadf-44bc-4f48-a69a-94c32b0ac3f8	\N		reception	forward	进入接稿（客户专员）	纯SQL自动初始化插入	\N	2026-02-28 16:33:35.934747
95628868-cada-4691-9f3b-428477d049d6	66bb4de4-01aa-458e-bfc9-fefde720875d	\N	reception	project_specialist	forward	确认难度为「simple」，进入项目专员，指定负责人：项目专员	下一步	b2c53252-9cb5-476e-b289-13019ad69c78	2026-03-02 10:37:22.625
60f79687-d977-47a6-85a4-2c593df5805b	66bb4de4-01aa-458e-bfc9-fefde720875d	\N	project_specialist	project_assistant	forward	从「项目专员」进入「项目助理」，指定负责人：项目助理	无问题	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:14:53.136348
15b67309-7362-407a-a9cd-db03dbb2e1b1	c54ef09d-4918-4ec6-b3b5-a7515be25858	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:43:26.160876
4dcbc55c-50ca-42fe-ade2-2a4c487f5d92	0b1e670a-d91e-42c6-b33a-46545aee8ca4	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.383733
8b12105b-ea1a-487a-93d7-bfe4c65cca6c	533d9a5c-30a5-4c89-990f-684ac14c62ad	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.395095
14c39687-d784-4e18-887a-49a68c5633b8	fa30ce83-e2da-44eb-a2b1-92eb8c040ccb	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.400821
874bf6c5-cb3a-4481-a616-ad17e6cc5d14	87a1b169-1e1e-4c42-b086-c1b26718ff46	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.407333
33ed6b2d-9214-4d42-a440-648721f9027c	d2806189-51d6-404c-b7ce-a60e53d03d6a	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.413611
12e746d6-06a4-406a-916a-c7358b190312	1e1f83a2-5278-406c-bccd-15fc493f76a5	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.41965
9c0b2bdd-a1cc-4cec-97a1-d2e8d8330bef	2b2c3a80-8051-4a47-8199-3921616e7d99	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.426502
13a01d8c-3df9-490e-a715-10c9f219099e	4e9b57dd-5ffd-488b-8346-9dd7657a06ae	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.432493
6c1e1aea-582b-48ad-a64a-d32659cdd48b	37055887-4922-4d78-8d17-77363acd7d31	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.438714
7169b1a2-80d9-4863-b223-3846f57d041c	ce155bfd-fee9-4642-aa6c-4f8b782eda3d	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-02 11:45:34.445152
c8a47911-a1e4-44b7-b43c-c2518ffd6252	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N	reception	project_specialist	forward	确认难度为「simple」，进入项目专员，指定负责人：伟琪	（无备注）	e3e45710-2408-45ae-ba6e-54e0691506f5	2026-03-02 17:00:31.496455
d280204f-fd89-4085-a8b9-170388840abc	12d400f9-0127-4f3b-af41-02454375793c	\N	reception	layout_assign	forward	确认难度为「complex」，进入排版指派，指定负责人：瑞珠	（无备注）	bc55fda0-78d1-492b-804c-0c59607c3922	2026-03-02 17:48:42.254766
2a480998-3718-4ce4-b4eb-a46543208b26	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N	project_specialist	project_assistant	forward	从「项目专员」进入「项目助理」，指定负责人：翠珍	这是HR处理的阶段	f174bde7-af8b-4c28-b94e-4d2c07bab29c	2026-03-03 09:23:55.277291
b407049e-54d1-4dcd-97c9-30c347068827	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N	project_assistant	special_qc	forward	从「项目助理」进入「专检」，指定负责人：李娴	直接去专检	b9e7efff-0da1-41a0-9925-35f4ebf99fc9	2026-03-03 09:25:52.686111
d7c5645c-09be-4e53-bfae-61f1f2c4fbee	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N	special_qc	layout	forward	从「专检」进入「排版」，指定负责人：瑞珠	直接排版	bc55fda0-78d1-492b-804c-0c59607c3922	2026-03-03 09:27:31.676011
f66506e2-f727-4b03-99df-102e33c7e4a6	4c8ef8aa-3a05-436b-996e-7c86faf354e8	\N	layout	completed	forward	从「排版」进入「完成」	这个直接给客户专员交稿	\N	2026-03-03 09:29:01.490888
35f0a2bc-f972-4f8e-a1e1-8b30d6a0acb5	12d400f9-0127-4f3b-af41-02454375793c	\N	layout_assign	project_manager	forward	从「排版指派」进入「项目经理」，指定负责人：项目经理	（无备注）	74c04077-ea7c-4978-9735-10413dc62aa3	2026-03-04 18:03:27.892585
\.


--
-- Name: app_user app_user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_user
    ADD CONSTRAINT app_user_pkey PRIMARY KEY (id);


--
-- Name: app_user app_user_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_user
    ADD CONSTRAINT app_user_username_key UNIQUE (username);


--
-- Name: client client_client_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT client_client_code_key UNIQUE (client_code);


--
-- Name: client client_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT client_pkey PRIMARY KEY (id);


--
-- Name: employee_leave employee_leave_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_leave
    ADD CONSTRAINT employee_leave_pkey PRIMARY KEY (id);


--
-- Name: project_file project_file_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.project_file
    ADD CONSTRAINT project_file_pkey PRIMARY KEY (id);


--
-- Name: role role_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role
    ADD CONSTRAINT role_pkey PRIMARY KEY (id);


--
-- Name: role role_role_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.role
    ADD CONSTRAINT role_role_name_key UNIQUE (role_name);


--
-- Name: translation_project translation_project_order_no_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT translation_project_order_no_key UNIQUE (order_no);


--
-- Name: translation_project translation_project_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT translation_project_pkey PRIMARY KEY (id);


--
-- Name: translator translator_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translator
    ADD CONSTRAINT translator_pkey PRIMARY KEY (id);


--
-- Name: translator translator_translator_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translator
    ADD CONSTRAINT translator_translator_code_key UNIQUE (translator_code);


--
-- Name: user_role uq_user_role; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT uq_user_role UNIQUE (user_id, role_id);


--
-- Name: workflow_instance uq_wf_instance_project; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_instance
    ADD CONSTRAINT uq_wf_instance_project UNIQUE (translation_project_id);


--
-- Name: user_role user_role_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT user_role_pkey PRIMARY KEY (id);


--
-- Name: work_schedule work_schedule_date_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.work_schedule
    ADD CONSTRAINT work_schedule_date_key UNIQUE (schedule_date);


--
-- Name: work_schedule work_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.work_schedule
    ADD CONSTRAINT work_schedule_pkey PRIMARY KEY (id);


--
-- Name: workflow_instance workflow_instance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_instance
    ADD CONSTRAINT workflow_instance_pkey PRIMARY KEY (id);


--
-- Name: workflow_log workflow_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_log
    ADD CONSTRAINT workflow_log_pkey PRIMARY KEY (id);


--
-- Name: project_file fk_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.project_file
    ADD CONSTRAINT fk_project FOREIGN KEY (translation_project_id) REFERENCES public.translation_project(id) ON DELETE CASCADE;


--
-- Name: translation_project fk_project_client; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT fk_project_client FOREIGN KEY (client_id) REFERENCES public.client(id) ON DELETE RESTRICT;


--
-- Name: translation_project fk_project_creator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT fk_project_creator FOREIGN KEY (created_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: translation_project fk_project_pm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT fk_project_pm FOREIGN KEY (pm_confirmed_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: translation_project fk_project_translator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_project
    ADD CONSTRAINT fk_project_translator FOREIGN KEY (translator_id) REFERENCES public.translator(id) ON DELETE SET NULL;


--
-- Name: user_role fk_role; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT fk_role FOREIGN KEY (role_id) REFERENCES public.role(id) ON DELETE CASCADE;


--
-- Name: project_file fk_uploader; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.project_file
    ADD CONSTRAINT fk_uploader FOREIGN KEY (uploaded_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: user_role fk_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES public.app_user(id) ON DELETE CASCADE;


--
-- Name: workflow_instance fk_wf_instance_assignee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_instance
    ADD CONSTRAINT fk_wf_instance_assignee FOREIGN KEY (current_assignee_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: workflow_instance fk_wf_instance_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_instance
    ADD CONSTRAINT fk_wf_instance_project FOREIGN KEY (translation_project_id) REFERENCES public.translation_project(id) ON DELETE CASCADE;


--
-- Name: workflow_log fk_wf_log_instance; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_log
    ADD CONSTRAINT fk_wf_log_instance FOREIGN KEY (workflow_instance_id) REFERENCES public.workflow_instance(id) ON DELETE CASCADE;


--
-- Name: workflow_log fk_wf_log_next_assignee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_log
    ADD CONSTRAINT fk_wf_log_next_assignee FOREIGN KEY (next_assignee_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: workflow_log fk_wf_log_operator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_log
    ADD CONSTRAINT fk_wf_log_operator FOREIGN KEY (operator_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict FCe96DvmenMN9JiL1V2UqsK7Yi3uiDUrq4dd8KzKDD9Ud2DjVka3LgI7DJMnrjD

