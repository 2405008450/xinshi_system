--
-- PostgreSQL database dump
--

\restrict F1QRRfVu4NtJt24967bB1hIHQTZlkWMkpukCIvODUAs4qpLmpkhsawG2hBuLuia

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


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: app_notification; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.app_notification (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    recipient_user_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    notification_type character varying(50) DEFAULT 'workflow'::character varying NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    read_at timestamp without time zone,
    related_project_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.app_notification OWNER TO postgres;

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
-- Name: chat_project_enabled; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chat_project_enabled (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    enabled_by uuid,
    enabled_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.chat_project_enabled OWNER TO postgres;

--
-- Name: chat_project_mention; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chat_project_mention (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    message_id uuid NOT NULL,
    mentioned_user_id uuid NOT NULL,
    mentioned_user_name character varying(255) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.chat_project_mention OWNER TO postgres;

--
-- Name: chat_project_message; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chat_project_message (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    sender_user_id uuid,
    sender_name character varying(255) NOT NULL,
    content text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.chat_project_message OWNER TO postgres;

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
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    english_name character varying(255),
    english_short_name character varying(100)
);


ALTER TABLE public.client OWNER TO postgres;

--
-- Name: client_contact; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.client_contact (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid,
    client_code character varying(50),
    client_name character varying(255),
    client_short_name character varying(100),
    client_manager character varying(100),
    manager_contact character varying(100),
    visit_count integer DEFAULT 0,
    visit_date date,
    visit_type character varying(50),
    client_attitude character varying(50),
    description text,
    follow_up_count integer DEFAULT 0,
    follow_up_date date,
    follow_up_status text,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.client_contact OWNER TO postgres;

--
-- Name: consultation; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.consultation (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    consultation_code character varying(50) NOT NULL,
    client_id uuid,
    consultation_time timestamp without time zone,
    consultation_method character varying(50),
    client_source character varying(100),
    source_keyword character varying(255),
    consultation_description text,
    remarks text,
    customer_service_id uuid,
    sales_person_id uuid,
    status character varying(20) DEFAULT 'pending'::character varying,
    consultation_type character varying(50),
    handling_method character varying(100),
    editor_id uuid,
    follow_up_count integer DEFAULT 0,
    follow_up_time timestamp without time zone,
    follow_up_status character varying(20),
    follow_up_remarks text,
    follow_up_person_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.consultation OWNER TO postgres;

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
-- Name: finance_payment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.finance_payment (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    finance_id uuid NOT NULL,
    stage_type character varying(20) NOT NULL,
    stage_no integer DEFAULT 1 NOT NULL,
    planned_amount numeric(14,2),
    actual_amount numeric(14,2),
    payment_time timestamp without time zone,
    payment_method character varying(50),
    confirmed_by uuid,
    confirmed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_finance_payment_confirm_pair CHECK ((((confirmed_by IS NULL) AND (confirmed_at IS NULL)) OR ((confirmed_by IS NOT NULL) AND (confirmed_at IS NOT NULL)))),
    CONSTRAINT ck_finance_payment_stage_no_rule CHECK (((((stage_type)::text = 'mid'::text) AND (stage_no >= 1)) OR (((stage_type)::text = ANY ((ARRAY['deposit'::character varying, 'final'::character varying])::text[])) AND (stage_no = 1)))),
    CONSTRAINT finance_payment_actual_amount_check CHECK ((actual_amount >= (0)::numeric)),
    CONSTRAINT finance_payment_planned_amount_check CHECK ((planned_amount >= (0)::numeric)),
    CONSTRAINT finance_payment_stage_no_check CHECK ((stage_no >= 1)),
    CONSTRAINT finance_payment_stage_type_check CHECK (((stage_type)::text = ANY ((ARRAY['deposit'::character varying, 'mid'::character varying, 'final'::character varying])::text[])))
);


ALTER TABLE public.finance_payment OWNER TO postgres;

--
-- Name: finance_record; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.finance_record (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    project_id uuid NOT NULL,
    sales_person_id uuid,
    follow_up_person_id uuid,
    settlement_method character varying(50),
    unit_price_excl_tax numeric(14,2),
    unit_price_incl_tax numeric(14,2),
    total_excl_tax numeric(14,2),
    total_incl_tax numeric(14,2),
    invoice_status character varying(20) DEFAULT 'unissued'::character varying NOT NULL,
    remarks text,
    edited_by uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT finance_record_invoice_status_check CHECK (((invoice_status)::text = ANY ((ARRAY['unissued'::character varying, 'partial'::character varying, 'issued'::character varying])::text[]))),
    CONSTRAINT finance_record_total_excl_tax_check CHECK ((total_excl_tax >= (0)::numeric)),
    CONSTRAINT finance_record_total_incl_tax_check CHECK ((total_incl_tax >= (0)::numeric)),
    CONSTRAINT finance_record_unit_price_excl_tax_check CHECK ((unit_price_excl_tax >= (0)::numeric)),
    CONSTRAINT finance_record_unit_price_incl_tax_check CHECK ((unit_price_incl_tax >= (0)::numeric))
);


ALTER TABLE public.finance_record OWNER TO postgres;

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
-- Name: sub_client; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sub_client (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_client_id uuid NOT NULL,
    sub_client_code character varying(60) NOT NULL,
    client_name character varying(255) NOT NULL,
    client_short_name character varying(100) NOT NULL,
    english_name character varying(255),
    english_short_name character varying(100),
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


ALTER TABLE public.sub_client OWNER TO postgres;

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
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    language_pair character varying(100),
    priority character varying(50),
    word_count bigint,
    network_file_path character varying(500)
);


ALTER TABLE public.translation_project OWNER TO postgres;

--
-- Name: translation_sub_order; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.translation_sub_order (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    parent_project_id uuid NOT NULL,
    sub_order_no character varying(60) NOT NULL,
    sub_project_name character varying(255),
    language_pair character varying(100),
    word_count bigint,
    translator_id uuid,
    translator_assignment_time timestamp without time zone,
    status character varying(50) DEFAULT 'pending'::character varying,
    translator_delivery_progress character varying(20),
    review_progress character varying(20),
    layout_progress character varying(20),
    network_file_path character varying(500),
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    file_type_secondary character varying(100),
    priority character varying(50),
    customer_deadline_time timestamp without time zone,
    sent_to_client_time timestamp without time zone,
    client_feedback text,
    expected_translator_stats_method character varying(100),
    expected_translator_word_count bigint,
    pre_review_qc_progress character varying(20),
    review1_progress character varying(20),
    review2_progress character varying(20),
    post_review_qc_progress character varying(20),
    consolidation_progress character varying(20),
    created_by uuid
);


ALTER TABLE public.translation_sub_order OWNER TO postgres;

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
-- Name: v_finance_record_display; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_finance_record_display AS
 SELECT fr.id AS finance_id,
    fr.project_id,
    tp.order_no,
    c.client_short_name,
    tp.project_name,
    tp.project_status,
    tp.customer_reception_time,
    fr.settlement_method,
    fr.unit_price_excl_tax,
    fr.unit_price_incl_tax,
    fr.total_excl_tax,
    fr.total_incl_tax,
    fr.invoice_status,
    fr.remarks,
    fr.edited_by,
    fr.created_at,
    fr.updated_at
   FROM ((public.finance_record fr
     JOIN public.translation_project tp ON ((tp.id = fr.project_id)))
     LEFT JOIN public.client c ON ((c.id = tp.client_id)));


ALTER VIEW public.v_finance_record_display OWNER TO postgres;

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
    translation_project_id uuid,
    difficulty character varying(20),
    file_editable boolean,
    current_stage_key character varying(50) DEFAULT 'reception'::character varying NOT NULL,
    current_assignee_id uuid,
    project_status character varying(30) DEFAULT 'pending'::character varying,
    stage_notes jsonb DEFAULT '{}'::jsonb,
    stage_data jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    group_assign_role character varying(50),
    sub_order_id uuid,
    CONSTRAINT chk_workflow_one_target CHECK ((((translation_project_id IS NOT NULL) AND (sub_order_id IS NULL)) OR ((translation_project_id IS NULL) AND (sub_order_id IS NOT NULL))))
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
-- Data for Name: app_notification; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_notification (id, recipient_user_id, title, content, notification_type, is_read, read_at, related_project_id, created_at) FROM stdin;
8d6123a3-4ec4-4aff-b8b1-10a6be30ce77	f174bde7-af8b-4c28-b94e-4d2c07bab29c	Workflow Task Updated	Project TP-20260228-SQL001 / SQL直插测试项目批次 422 has entered 项目助理. Please handle it.	workflow_assign	t	2026-03-14 06:23:46.770173	2de21aed-d67d-4e02-9f8b-a978973bfc6f	2026-03-14 14:23:27.39988
9ee74d88-c03a-4182-ae78-d7f11ec9ca3f	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	Workflow Task Updated	Project TP-20260228-SQL001 / SQL直插测试项目批次 422 has entered 专检. Please handle it.	workflow_assign	t	2026-03-14 06:26:49.71661	2de21aed-d67d-4e02-9f8b-a978973bfc6f	2026-03-14 14:25:51.496034
b593dfb4-e1fa-488b-96a2-c36d56eeb7f7	f174bde7-af8b-4c28-b94e-4d2c07bab29c	Workflow Task Updated	TP-260302-0003 / 测试翻译项目批次 267 has entered 项目助理. Please handle it.	workflow_assign	f	\N	f3f59a1d-d792-4722-971d-63ebe9fd06cb	2026-03-14 18:15:04.186737
4fa03196-223e-4a7b-8151-a7c6b056e7ca	1a55179f-026e-44f7-ac5d-c32bed603515	项目沟通新消息	项目经理 在项目 TP-260311-0003 / 游戏翻译项目 中发送了新消息：这个需要外派	project_chat	f	\N	552d6dbb-4d84-4c78-95e5-db0af4b293d1	2026-03-16 16:25:22.833176
2cc0ee5a-f2b9-4e82-8e94-accc09b291f5	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	项目沟通提醒	项目经理 在项目 TP-260311-0003 / 游戏翻译项目 中 @了你：这个需要外派	project_chat_mention	t	2026-03-16 08:25:42.191694	552d6dbb-4d84-4c78-95e5-db0af4b293d1	2026-03-16 16:25:22.820881
499cbb4d-a45b-4fbc-958e-3e38633fe6e0	74c04077-ea7c-4978-9735-10413dc62aa3	项目沟通提醒	楚翘 在项目 TP-260311-0003 / 游戏翻译项目 中 @了你：具体是要怎么做呢	project_chat_mention	f	\N	552d6dbb-4d84-4c78-95e5-db0af4b293d1	2026-03-16 16:28:34.684035
c8dc8155-2d32-4191-b8f6-9fe2813bcfe2	1a55179f-026e-44f7-ac5d-c32bed603515	项目沟通新消息	楚翘 在项目 TP-260311-0003 / 游戏翻译项目 中发送了新消息：具体是要怎么做呢	project_chat	f	\N	552d6dbb-4d84-4c78-95e5-db0af4b293d1	2026-03-16 16:28:34.689907
618eeeb9-f900-45fa-bab7-31dd88298616	1a55179f-026e-44f7-ac5d-c32bed603515	项目沟通新消息	楚翘 在项目 TP-260311-0003 / 游戏翻译项目 中发送了新消息：这里只是一个测试的地方	project_chat	f	\N	552d6dbb-4d84-4c78-95e5-db0af4b293d1	2026-03-16 16:28:49.042145
\.


--
-- Data for Name: app_user; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.app_user (id, username, password_hash, full_name, email, is_active, created_at, updated_at, department, fixed_tasks) FROM stdin;
5eb624c1-5fc6-4587-b469-6f75c9b2ce37	奶奶的龙	a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3	测试中	123user@example.com	t	2026-01-16 15:20:20.078816	2026-01-16 15:20:20.078816	\N	[]
794d62da-689b-4b52-98fe-165c708d26b4	kuangjiao	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	旷姣	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目部	[]
e228c697-4885-41a3-a02f-ef389defedd0	HR	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	项目助理	user@example.com	t	2026-02-09 19:16:33.752236	2026-02-09 19:16:33.752236	项目部	[]
b2c53252-9cb5-476e-b289-13019ad69c78	trans	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	项目专员	user@example.com	t	2026-02-05 17:03:10.096255	2026-02-05 17:03:10.096255	\N	[]
d7116c76-ae7c-4624-9e5b-4bad4418c74d	sales	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	销售专员	12312312@qq.com	t	2026-02-05 17:06:00.235289	2026-02-05 17:06:00.235289	\N	[]
fb5c69c5-e422-48e7-9214-025aacee74b0	DTP	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	排版专员	123@qq.com	t	2026-02-10 16:27:09.049628	2026-02-10 16:27:09.049628	项目部	[]
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
1a55179f-026e-44f7-ac5d-c32bed603515	service	$2b$12$8Ieslg9R/uYHjD41FTrAfeqb/6PgDXvFu6bWjJv8hZC0D5lU8J6Qq	客户专员	user@example.com	t	2026-02-05 15:28:05.660439	2026-02-05 15:28:05.660439	\N	[]
74c04077-ea7c-4978-9735-10413dc62aa3	LPM	$2b$12$JmUhceJPQ33ppFZ/Bs4lNuKV8EP/wGPHQo0sCzZ6oA4Hs0wW6F.5.	项目经理	1111@qq.com	t	2026-02-05 17:05:13.657683	2026-02-05 17:05:13.657683	\N	[]
27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	chuqiao	$2b$12$q4TsOewvNX0ZMy56e4Ky/./tSWQhWlQGctDM/w3XtLsHRuUSNXac6	楚翘	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
ba92e52a-f517-48a4-a422-1688f2afe067	admin	$2b$12$Te6n2.kWkpo3EceaPOVEuu4wEghL25M94ps3WMZmvEkyuYwEUER0e	admin	user@example.com	t	2026-01-16 16:32:50.385926	2026-01-16 16:32:50.385926	\N	[]
296067f8-38f9-4c57-86ad-575e739e338e	xinjian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	辛建	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
08165a0c-b40d-4206-8407-236d5875c46f	shuqian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	舒倩	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
3ff6a06a-395e-47cd-a7d6-5248605120a2	yeshan	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	烨珊	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	客户部	[]
48324d9a-58bf-4b9c-bc6b-591007b0bdcc	yunyu	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	韵钰	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	["（暂停）项目专员培训资料调整", "（暂停）项目经理培训资料梳理、编写"]
e6ba212f-2cc3-4f95-9a04-b8f7c20392b5	lirong	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	立溶	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
f19abbad-49fe-4dcc-bed8-e13d54e555b4	shuting	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	舒婷	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
7bdff3f4-a101-4648-84dd-5412948edcb2	yuqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	宇琪	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
4a282914-f05c-47e3-a4ea-e7511bc3e8c8	zixia	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	紫霞	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
5709ddb9-38b2-4dcb-9d7b-30b217fa8071	wanjun	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	菀筠	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
f50a5f1e-1553-4456-8b38-f4ecdebc849d	yingqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	颖琦	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
e3e45710-2408-45ae-ba6e-54e0691506f5	weiqi	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	伟琪	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	项目部	[]
97f891c3-5319-4e0d-92da-1eabc773598e	shaojie	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	少洁	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
72cc5448-bb49-42d0-a873-8d22e206eb54	wenhui	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	文慧	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
84e460fc-1d5a-4c69-aa12-e84a178fbfed	yunjian	a964c9e169f7578b4ede811783a468dee6d9ce519ca7a7954da78a7b979429ea	运坚	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	[]
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
f174bde7-af8b-4c28-b94e-4d2c07bab29c	cuizhen	$2b$12$1Rw6049u7IvXc3pUyYVgBeK6Vp51jlKLEHQxhcNcFDTcoBsKET/HK	翠珍	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	HR部	[]
bc55fda0-78d1-492b-804c-0c59607c3922	ruizhu	$2b$12$.8jnCHd9BMLoZIRBefKHgebA4LWyU7lR2ZeyTFMufivBjlDFyeBwK	瑞珠	\N	t	2026-03-02 15:53:00.529448	2026-03-02 15:53:00.529448	排版	["每月专检稽查（梁承敏、沈佳佳）"]
\.


--
-- Data for Name: chat_project_enabled; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.chat_project_enabled (id, project_id, enabled, enabled_by, enabled_at, updated_at) FROM stdin;
d5cff823-84fe-4324-8765-21e7cff1e6fa	552d6dbb-4d84-4c78-95e5-db0af4b293d1	t	74c04077-ea7c-4978-9735-10413dc62aa3	2026-03-16 08:24:18.323368	2026-03-16 08:24:18.323368
\.


--
-- Data for Name: chat_project_mention; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.chat_project_mention (id, message_id, mentioned_user_id, mentioned_user_name, created_at) FROM stdin;
d7e8e3a8-b119-4095-b031-916cc28ae22b	a51a7908-c0a4-4996-8d77-0e0207d29a17	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	楚翘	2026-03-16 16:25:22.807449
434bdc58-9f1b-4056-8d3d-af3330a7b11a	abc31067-af3f-4950-b750-b47c8a9d6dbb	74c04077-ea7c-4978-9735-10413dc62aa3	项目经理	2026-03-16 16:28:34.677367
\.


--
-- Data for Name: chat_project_message; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.chat_project_message (id, project_id, sender_user_id, sender_name, content, created_at, updated_at) FROM stdin;
a51a7908-c0a4-4996-8d77-0e0207d29a17	552d6dbb-4d84-4c78-95e5-db0af4b293d1	74c04077-ea7c-4978-9735-10413dc62aa3	项目经理	这个需要外派	2026-03-16 16:25:22.807449	2026-03-16 16:25:22.807449
abc31067-af3f-4950-b750-b47c8a9d6dbb	552d6dbb-4d84-4c78-95e5-db0af4b293d1	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	楚翘	具体是要怎么做呢	2026-03-16 16:28:34.677367	2026-03-16 16:28:34.677367
ee8c55b5-c28b-4122-a7f9-d88846eb8604	552d6dbb-4d84-4c78-95e5-db0af4b293d1	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	楚翘	这里只是一个测试的地方	2026-03-16 16:28:49.03229	2026-03-16 16:28:49.03229
\.


--
-- Data for Name: client; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.client (id, client_code, client_name, client_short_name, client_manager, manager_contact, field_level1, field_level2, country, province, city, district, client_status, cooperation_start_date, remarks, created_at, updated_at, english_name, english_short_name) FROM stdin;
621ae0b3-4237-4e80-947e-1649b57b2253	CL-260309-0003	资翻译	上海资翻译	23	11	制造业	qdVGhBqzySi8yhy	格林纳达	甘肃	银川市	pl70eL7Vp9Zc22f	active	2023-05-30 00:14:38	x7RoI1Apu8fnfGD3GtHo8HbGkewf1hJ241MlBRFPkmrCDZW4eB6BCvFZ38HiDkgGZC5q13vBvzhIw2Erv5Zk8FE8qnzaqsJtnU8WYigRrHZy1cf9UmcNqQ2QXIp75yrkaUNih6A5uvISCkVcokzziVj1RdoW05DBqeXqZxRF1Lu7nwG6cvzpp1ERCWLpCZX2Ox1SDzZwUXiTowaiS6VGv4oCYdZEzJCoowGYICbolZLDHFGGISN0SotYFiZWp0qx5xGLcrERG2HD1qSJqPUcFTcXm3SIBz9uFSGiTkr9PgG6hKXLMX0jRMzR1q3GgVhZyaQMVMS83Odu6HvBMvnRHJasUslbj7IOKAULOhoFO1uhQSAJB3EWGLweIpKWIP8p4RRzjSgGYT7tqMyQKaQhOQIRWQHbeErXUejjF1L9lIJ7Zk1utFAfFfjKTACUJFuX5Le9CetG789VwjWp2VoZygNkkbUoEIIog8tx	2014-07-29 12:52:04	2017-11-13 08:52:35	\N	\N
c45edd34-2023-4b60-86d2-4ad6c815896e	CL-260309-0010	吉利	吉利乘用车集团	40	89	kVwrsKyLtlNkxNV	lEWWdEJkWgeqxrB	匈牙利	GAibyyaDDoZmium	张家口市	RJSmeeQax8ptKq2	IYba7aRw7NlZ6T7	1990-03-25 06:46:18	lPzKyKtos38UZExO2B706cWNTwMMD6S3HPxHfpD9DiaZeot04wsFG36aqNg7zuuDtO3OEtsbYABNg1ib3N64bRVC6C8vBs3lOePl9BJQ3WLzifIqUCOOCjeqfvYadcrmqMxPd0fP0H4n1BIsgnu7793ZpmdvsYqxVINv64fDrX9TQdvSZ3a0dRPlMtjBuhqRqjYLcd0YYV9rlbNJWGS3QTeWYG2imMOGYKZ8Sn7MiDMIdNNTA2ezGNOuL8h8Gt4k3E2zXebjPGpTvzcgZyrC9q	1980-03-28 07:29:00	1996-01-25 05:03:59	\N	\N
ce50afb4-ec6d-416e-91b7-b527f7a07abd	CL-260309-0004	美国玲	美国玲翻译	23	60	1TmLNqehQX5kmiD	7HYJQjzRMPbI2eH	密克罗尼西亚联邦	w9xdJaMl7MZW8oQ	西宁市	nc2n36mBU7CxndT	active	2008-07-16 02:11:38	lzcRhDoJAoJ4KXBEycUS0CKL4Lm6p3DWNpmw2lYA2wPfRRNeAr8yR21o2pI8n6nsLplNqxxJ0xjrtWRxrhyobc9gehMQVBaeKikKMq99XaGz5EJPWZiS6HHeyBqWGrupmXhb8NhHwUQFTwi6oPlszLnQSISx6kWfHdrY5iYEK2rkeIs8ZzJs4Umf6IdxZIHLHILb8A3EGqMZZGRxlkigZuvZZIfw5clYrb8wfpXqnPLzAGAsB1VEcNaJnTBu3uxDVBapJostpmNjqLMt6XUHqZbE8eiBHXNDMofG1HJp08t51UzX4cqaRWZtCHNuwn9gG2Wu625abvg2dfSAkXaqiLsjhBrfck6mJTEpQHpoIf0Tz6S8ZtdpjR0vXCGPBCrsGii9r8ghmvWekOyUs8X4rZYBZtscWuGTLcw75iKjEXAFp7XdwH5peW6LqKSuhuw3CI3klgNOfsHl1rVmEAzhJeSdulPuVZKL0q75gOTFQXD9xJwXqwJ6WRP3wv9MmHWmV6xrcU7ejtZQLltDBrFSuVslEyL3ssGy1oeVtrgWCkAUivXa5	1995-11-24 15:00:39	2018-10-24 08:26:53	\N	\N
88bc493e-e357-4600-9de7-4a507be5e9fd	CL-260309-0007	深圳市星月翻译有限公司	深圳安翻译	27	9	y9k76mZfmJrtto1	97FJCWGAdnupSbU	比利时	cbTch8jPp5IBmTu	鄂尔多斯市	V0JTj6iI6QhUhUJ	active	2020-02-26 00:00:32	mtkWBAtdWmlJhCCVOn2X59BxgeSLzjeqS9SfUUaghdVCuOSussjNJ8rM1yM4m8dNdJnlH0SPHPDO5xEHeV8euoKs8vrwSQGydrVYHVNLNrXgRIF8vJttcS1CIiKMTCa4ppccIYxbbWwH5jFsedEjaM5uJSTlE5gICx11l03t3l7KJbZwaaHFfEgzvuaxCY7My2o8XrAG6HtEAKIFhuhCP6ZNeqUP3ut2UHMmtOVRmlgIj6648CkfnE697pDKkSqjaosJQbQDdj7ZmJnemUTBSeGwf9mWC6E7nw6aUhm8QTveu0TXwOree72NTrgykfd4YsDdAqT2IK2JJWxUjpVmzpZo6GbLM8gqaiXlev9S6SO3HS2R09N8xF1JmfFvBzK3fahCAmib2ce8Obz4mAzqKZMCRS4nI8BFB3nhIc4VEJpUFkNPxfLchOQF6enhfovlVO3RIJNto2N7lSOsRqQHj3HgI3s1cmL9cFYl9yi2zNRxZhvvyBSiRfBhbwTOwIIg9C9Ahu0773B3U07IjUITZolO5tp62tquaPiuecdwPrRGO5WVraweqvqPsiOSDDAE3Ua4DYTbaDfURMvYZgiQMsJdZWmMDMs9Zt1Q502GwlSShfHHsEyGZzpfLfsAI1K0LGQkZ06QvLM5i3VyWaCSTzSftwvCu8jLxkBuQEaG02jWg4cYaGd2ddSSJLXSaAf	2018-01-11 04:52:23	1985-09-17 04:20:08	\N	\N
4b16bb7d-ce2c-4cc7-9453-3394825e712c	CL-260309-0008	上海唐能翻译咨询有限公司	上海顾翻译	74	33	2ynGBgAbD4PDLrG	c2gAgCowJaigMG9	约旦	GtDripUO92UobIK	重庆市	Tv2Ce2E8E0c4vrT	active	1983-02-12 12:40:04	Bj9c56RkUhf1hkyq1X08yCBSOvlXgRbhbLLGwMyvpBqZImJKh0QMAiTdsoW7GYinjNuQCFJMRXndjHHF8AxutKdrXOLoEMNqxQXqZXQL4X3XqZoZyJdYDSt7SzFQqYPCGvd1KUeNFvh1wtuWGIemfUvst1hdXwTrNGleV1ln4rtzpt2e3HQrKewIb6QekfWSVGncV7fBO8u7N93c6Huag4SaoS5UpcZbZyHPdJ10g49LgtkN2zxCZSGFpBZ6QA6DxpafkzLXTCSf7AMjlYlIPY2EPgAlWnuov7Qf8LstLKlOHdoD63LLmgxOb7kq6A5WeyC8hEWEeZBcXNg8ydkKcqdiOoLnI0r3JjnwyujTTX6bKOZrFGRwGbusoQgQLnDdVmMO1hW80sSQlvRJ83j5agcCFZxLc	1991-08-07 13:05:25	2014-10-30 07:51:03	\N	\N
59e14867-dea0-49d4-bc14-220002a416e7	CL-260309-0002	中翻译	北京中翻译	29	90	EEDCkQ0jtWF49kC	9mspvvp7OMNpGAC	毛里求斯	zGP2E1sfrR1gzoO	重庆市	zZXHMFMMVnuFGCa	active	1985-06-18 15:02:10	BU5VMBVudNlRvhi5XgNwQjhhhJkbjlu2B1EvM22s8mLKocmEuAfUAOHN2pUZdq9FutIapS41ma2sm7snY1yZXZ3bX9Knqp0MGVi55Poq9tKAuAOThnaSWOptjuMOFCsvk3EnF4Jc7LVJJhQTXDSgkuObRSMBTPpmnDulQzroZ1cnOeqrIimNDCgqDgjUdUL6GkBxU2c55jeNYMrO6MS6kTJVDtc2eoA4fKC2xQ98yBbliTgvXDmuXn2dAKfBti0rn553awnrOOKjkzFkte29xMJu4vkJ0vDRWjO1OC6A22h4AkXfp2hbSmy775lzGTa6Wx76mfUHixRxSIIhyme8dCYBS9aATcnO41fSwDz5XvAKBX9hysXhboz2jkFdT7FZhevQ7Be0CB7AMtRneZ2oYR2KBn1Dpm52cZ4hIBTi8TUAoRjJE	1974-06-18 17:49:45	1998-01-16 18:46:07	\N	\N
00df42a2-291a-4917-ac60-0acec68e4c16	CL-260309-0009	吉利汽车研究院	吉利汽车研究院	91	99	oVO3qeid4Bghfnm	CwVfqTx6LESOd4Q	印度尼西亚	89UTfSIJTZqWK2l	宣城市	ZmvsRohCGxwmJGN	active	1987-04-22 17:14:36	W9K48RSB7sPq4WhW9lPTUSXpGJ2chYIgkUJ1AmyaGCR1ndVNVH9eSORo03iNO37mxhiRL08UE2BMix2tJhz2IGxrR1VrOegJwoD0kWGh1oOuokrI4Sgdye0TzFEngFQyHw3tIZAIZIUOaP144Q1pwZeQrlZjuJ3GOfhLrR3OZR8kNwkwhnl6kR1SlAsOMw2k22zwOKSP1OMiVGIzRcA90DN5lOwv1D1xaVjKS8lnh5Mw2	2003-10-07 07:07:03	2024-06-20 00:03:54	\N	\N
2ff609a6-da58-4045-9e52-f6a7bd98cc33	CL-260309-0001	澳门吴	澳门吴翻译	11	34	NTfTJOg1IN31Nt4	dfoUpKmcI0JJEWC	北塞浦路斯*	qTuJnp7aCYzvUUY	海西蒙古族藏族自治州	nukAL6V6FVK9RUD	active	2018-03-17 23:09:12	dbalYUxxZjdwUY5cUsfvfgI2rA8nNtSHuhSofnFbFwLhVwX8mKWoThBiIGdw60Lr0rroUFP7EEZJB2CuadeIvvbUhyfSSiMzvOCF165qdKZh8EVBkGdeyiq1k3FtsNBdeNDJDr6d7eeByjQb7S5nw9jP4CxlFLWRO30R0ptZ5zGERmUeBG6l8lokQVYoxua3nlyAQ0y4HSP1dHMvqLcObXJdGhULhjmxthtln1hCiAMWT3h1wpyYFNugtbI9EItX1g0wNutlRZLQMPRs3eaCjYYKAUgoLF794X1PBgKpeYkQ7DuEtz6NkbwLkLyqGuY3g1MZaHyEU7XRSFE27zr5nMLtGpOVowZ6M7XPMJ5pym8y6BxOHJdqxMQJwHNjq5YF3uNPU95wXMddwgl3gZ9K5yCgL5dlV90z0liM8S9WO4nFtm50zhdsdmHfWrkE3Kn6BBIyxD	1975-01-09 21:43:38	1978-11-15 17:41:15	\N	\N
12a4a437-73e3-4878-9eb2-22959da1df21	CL-260309-0005	网易广州	网易	71	69	IeQa1zgMuLQUb6L	0GlhC363CbF5qf0	约旦	Qhzx8g6VHn0LAri	长治市	MEivLnaqY1mcieI	UMDIqPIZq6r2BUg	1986-09-05 00:25:10	qhxgbmPeAFc0EP0OAHgBao75Vd3ohm1KirzWtNl9YvvEzg2GUb9GriejYhc15wlxm4JijncgN44nDoodKbG0DAmM9TjqWDyFsTt9BDb2WND6Cx8CqVlAFB2wcpbqnVqL0DPJkJT9vjJx6rnJ2wyfQyC2U6GA89qEcauPqB2r3fjR9zp2K62YzFmp7CNylGYOiqAVkIz4Mk6lAFPSKsjQUOfAhVgASv3PVw9RaTF06CvuhBkbRzqbJej2nD2gEWNH9CiMB0NDaKW1TWXv98X9qJswr0BwLpCgbTVX8HaZcBfO8fYvyrT7HYenjrkqtNBOsnccE0Skip6gbYyv5P3JcoxOMUyrXboCRdPJjLHY76Q0mIIpBjyt00QzktsgYwCz9FfkyFsSAsVorpRvAFkMdnF9XZiWWPL5Ri8lyrVSed5U50R2XG2HbPnbjyFlxhjbxnGsIEfAYoudVLbx4v1Iot7Xsf903nTG65tRRe0dHJtlAoYTHQKftODtTqq177siV82nUAPNm46bK5GT6dAXRpwZst11OGHUmAW2FTlyXe1zgO2Dn8OTNZBleFispeh4plAhjOOBJLuZdj7lRMu9P0dBGs0jWJryt94DKvUFOTBdEl4p8mwmQKGVOVF0FgbHwJlp6xCa0Uh3m39hkteFSFB35D774OTaHON2KYqSxgXm3uvHuDelb0ho4gh6AuaB3A2VMslVCN7yyyOFdApdWadojrfe7eNQkWHrKX3yntHt2byvcY0nKaC5Z0wGoLwsoIOQV2qMqQZ8p5	1981-07-04 15:54:34	1990-07-27 08:15:13	\N	\N
4276a053-4cd7-4abc-87b7-a685a3044931	CL-260309-0006	广州中集集装箱有限公司	中集集装箱	12	79	7dSVUJrCJFyfODF	D5fdeq8ajC8ghrH	韩国	exfRTToyxTWJmol	六安市	EVz3Z0sZIpQPjp7	sjixDA9uY2s7np6	1983-10-08 06:19:49	vlhPu3qHelhIWSscPH4TsP5Uus2LaJzPBbyA2Dsf5u5P90D8EguVRvxbzfX7bFcIEHNPZJOrsr8TNBRLlJ1nxJmwOQ7ezWCevBoU7rGpufB4j5fAg8eBVhlmPWzRj36xChnf3OCBNobB6Ga4I3RjveAR7yAwvdrmWNOQMbRQemDFGCC84Funoj46SCk6O5BUXe3hcWp1nt9EJzMB7k6kRYfgBWqFOKaf7Mv4K7oh6yEfD2iEdh0YrbW3GlnziGdoSv35v44vsL4DzUfd359MsnvvtLTzBI0pzXl89Sn4sz9ztfiSUH3ovX0H748YR5IB2YPvCYgwpWH91F4wqrRjAZOzU5OKGS75ysdOj7QAyqOjA3OSISxiS4vucPA0WJLWqIUE67Q8ov5oIWKkubr7rOuUJbbMmrA7of9HSDEKWQf4bWCX52JkXEdHBoXGudoILjYETxKG8JfrXreEnxp30AVe5hkeWAD6mJ7pDOAgcbw8JJy9X5SUYODV8XJboddgUsoDgskA8q0PdMoGjnGXM6ubRYZRgdGvz3MlD1uOJFpgHl11pkOcnzPTcgtSv5GShXLUF6gX4sfbeeAacH9dBtYCLpDuu4FjvZrtnN1GHOPTqohCDgA30R2TxdEXSth4p0ECZZwRDfI5fsBS4Y	2012-11-20 11:34:20	2017-01-07 07:18:36	\N	\N
\.


--
-- Data for Name: client_contact; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.client_contact (id, client_id, client_code, client_name, client_short_name, client_manager, manager_contact, visit_count, visit_date, visit_type, client_attitude, description, follow_up_count, follow_up_date, follow_up_status, remarks, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: consultation; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.consultation (id, consultation_code, client_id, consultation_time, consultation_method, client_source, source_keyword, consultation_description, remarks, customer_service_id, sales_person_id, status, consultation_type, handling_method, editor_id, follow_up_count, follow_up_time, follow_up_status, follow_up_remarks, follow_up_person_id, created_at, updated_at) FROM stdin;
0727c39d-6197-44ff-83c9-e8e403f62a7b	EQ-260309-0001	59e14867-dea0-49d4-bc14-220002a416e7	2026-03-11 17:07:01	phone	other	\N	12312	12312	\N	\N	success	price	\N	\N	0	\N	\N	\N	\N	2026-03-09 16:16:24.780099	2026-03-09 16:16:24.780099
8b99deed-aa94-48cf-8328-1398e75e54df	EQ-260309-0002	4b16bb7d-ce2c-4cc7-9453-3394825e712c	2026-03-09 00:00:00	phone	website	12312	\N	\N	\N	\N	success	\N	\N	\N	0	\N	\N	\N	\N	2026-03-09 16:25:39.843711	2026-03-09 16:25:39.843711
9e1c6bd6-eaeb-4943-ad55-4f56a1a6392c	EQ-260310-0001	88bc493e-e357-4600-9de7-4a507be5e9fd	2026-03-10 00:00:00	phone	website	12312	123123	123132	\N	\N	success	service	\N	\N	0	\N	\N	\N	\N	2026-03-10 16:19:56.396439	2026-03-10 16:19:56.396439
c0122ac4-bd96-4693-b667-47616c34f356	EQ-260312-0001	59e14867-dea0-49d4-bc14-220002a416e7	2026-03-12 00:00:00	\N	\N	\N	\N	\N	1a55179f-026e-44f7-ac5d-c32bed603515	d7116c76-ae7c-4624-9e5b-4bad4418c74d	success	translation	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	1	2026-03-13 00:00:00	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-03-12 09:43:03.565128	2026-03-12 09:43:03.565128
3044ce8d-2cde-447b-b19c-d89171de4e00	EQ-260314-0001	2ff609a6-da58-4045-9e52-f6a7bd98cc33	2026-03-14 00:00:00	\N	\N	\N	\N	\N	\N	\N	following	translation	\N	\N	0	\N	\N	\N	\N	2026-03-14 16:09:30.654112	2026-03-14 16:09:30.654112
\.


--
-- Data for Name: employee_leave; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.employee_leave (id, employee_id, employee_name, start_date, end_date, leave_type, reason, created_at) FROM stdin;
3ade4bbf-8efb-457c-9522-76a51d23b8fb	72cc5448-bb49-42d0-a873-8d22e206eb54	文慧	2026-03-03	2026-03-03	请假	病假	2026-03-03 10:43:38.464477
c69f25b0-2ad6-4a7d-bd2e-efa75f217fe1	e3e45710-2408-45ae-ba6e-54e0691506f5	伟琪	2026-03-31	2026-04-08	调休		2026-03-03 10:44:02.541794
\.


--
-- Data for Name: finance_payment; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.finance_payment (id, finance_id, stage_type, stage_no, planned_amount, actual_amount, payment_time, payment_method, confirmed_by, confirmed_at, created_at, updated_at) FROM stdin;
cc45dbc9-013b-4b51-afb6-51cd5a3d3524	1a82b76a-72a6-445d-b6a1-d1ac9b671628	deposit	1	12312.00	12312.00	2026-03-10 00:00:00	银行汇款	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-03-10 00:00:00	2026-03-12 15:43:26.13997	2026-03-12 15:43:26.13997
5a34dfe4-4efb-43f8-bf69-7eb8ec13bbb3	1a82b76a-72a6-445d-b6a1-d1ac9b671628	mid	1	99999.00	99999.00	2026-03-10 00:00:00		b2c53252-9cb5-476e-b289-13019ad69c78	2026-03-10 00:00:00	2026-03-12 15:43:26.13997	2026-03-12 15:43:26.13997
\.


--
-- Data for Name: finance_record; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.finance_record (id, project_id, sales_person_id, follow_up_person_id, settlement_method, unit_price_excl_tax, unit_price_incl_tax, total_excl_tax, total_incl_tax, invoice_status, remarks, edited_by, created_at, updated_at) FROM stdin;
1a82b76a-72a6-445d-b6a1-d1ac9b671628	1a58dfb0-8324-4cdb-a9ed-994ab0a7da9c	\N	d7116c76-ae7c-4624-9e5b-4bad4418c74d	\N	2131.00	0.00	0.00	0.00	unissued	string	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-03-10 15:22:58.648974	2026-03-12 15:43:15.787323
\.


--
-- Data for Name: project_file; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.project_file (id, translation_project_id, file_name, storage_path, file_type, file_ext, file_size, storage_type, uploaded_by, created_at) FROM stdin;
38e5f21e-7750-47c0-9d89-09575d0baea6	b2b5fc81-163b-4497-a752-c7bff86d2d5e	测试9527	\\\\win-server			\N		\N	2026-03-16 14:55:05.229091
02fb583a-abaf-430f-9310-1b892a0159f8	552d6dbb-4d84-4c78-95e5-db0af4b293d1	测试	\\\\win-server\\服务器资料7\\译员简历（已整理证书）\\阿语-已整理\\母语译员	可编辑		\N		\N	2026-03-16 11:25:00.103936
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
-- Data for Name: sub_client; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sub_client (id, parent_client_id, sub_client_code, client_name, client_short_name, english_name, english_short_name, client_manager, manager_contact, field_level1, field_level2, country, province, city, district, client_status, cooperation_start_date, remarks, created_at, updated_at) FROM stdin;
a556124c-b266-47f3-83a2-5e8ed7fa9c93	c45edd34-2023-4b60-86d2-4ad6c815896e	123	吉利汽车研究院	吉利2	\N	\N	40	89	\N	\N	\N	\N	\N	\N	IYba7aRw7NlZ6T7	\N	\N	2026-03-11 12:04:18.966383	2026-03-11 12:04:18.966383
8e874ea3-f0e3-4ac4-88d8-40514b1c0a8c	2ff609a6-da58-4045-9e52-f6a7bd98cc33	12312	12312	1231231	\N	\N	11	34	\N	\N	\N	\N	\N	\N	A5vG5gU6wy4QDFf	\N	\N	2026-03-11 14:13:37.785295	2026-03-11 14:13:37.785295
\.


--
-- Data for Name: translation_project; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.translation_project (id, order_no, project_name, file_type_secondary, client_id, customer_reception_time, customer_deadline_time, sent_to_client_time, client_feedback, project_status, pm_confirmed_by, translator_id, translator_assignment_time, expected_translator_stats_method, expected_translator_word_count, translator_delivery_progress, pre_review_qc_progress, review1_progress, review2_progress, post_review_qc_progress, layout_progress, consolidation_progress, created_by, created_at, updated_at, language_pair, priority, word_count, network_file_path) FROM stdin;
9d869ebf-3d55-477d-a4db-0ec4e9c1488c	TP-260228-0027	直插测试项目批次 673	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	fb5c69c5-e422-48e7-9214-025aacee74b0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	fb5c69c5-e422-48e7-9214-025aacee74b0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
e95e6db2-3b58-4311-8525-e6691448829b	TP-260228-0014	直插测试项目批次 115	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
c3cc69e8-f65b-42c3-bb7a-1628215a73e9	TP-260228-0016	直插测试项目批次 165	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	74c04077-ea7c-4978-9735-10413dc62aa3	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
8bacd012-a839-411c-9020-dd85d35d5c7d	TP-260228-0017	直插测试项目批次 525	\N	c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
efed205d-a908-4bb2-955a-0e1eb2c3c81b	TP-260228-0018	直插测试项目批次 805	\N	59e14867-dea0-49d4-bc14-220002a416e7	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
a3bb5bb9-11a1-4dc2-9b21-640848ed716a	TP-260228-0019	直插测试项目批次 483	\N	12a4a437-73e3-4878-9eb2-22959da1df21	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
be8e9dcd-8ba9-410f-ba19-64aa51c99dd0	TP-260302-0002	测试翻译项目批次 856	\N	621ae0b3-4237-4e80-947e-1649b57b2253	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:45:34.372763	2026-03-02 11:45:34.372763	\N	\N	\N	\N
858c1e78-ad24-4ffb-9c5b-6bd645a6fc55	TP-260228-0013	直插测试项目批次 771	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	74c04077-ea7c-4978-9735-10413dc62aa3	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
12eb4bfd-8bd6-4a34-8010-5045d2c4fd6b	TP-260302-0001	测试翻译项目批次 254	\N	4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:43:26.146969	2026-03-02 11:43:26.146969	\N	\N	\N	\N
c3730723-a1e9-4be0-8a17-1082355a74c8	TP-260228-0001	测试翻译项目批次 239	测试	59e14867-dea0-49d4-bc14-220002a416e7	\N	\N	\N	\N	进行中	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N		\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:02:11.714498	2026-02-28 16:02:11.714498	\N	\N	\N	\N
7b50514a-672d-49a6-9254-c2a470c91b29	TP-260302-0004	测试翻译项目批次 683	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	b2c53252-9cb5-476e-b289-13019ad69c78	2026-03-02 11:45:34.397776	2026-03-02 11:45:34.397776	\N	\N	\N	\N
bed7e3f0-d977-4fe9-b9ea-b079d55cde6d	TP-260302-0006	测试翻译项目批次 547	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	5eb624c1-5fc6-4587-b469-6f75c9b2ce37	2026-03-02 11:45:34.410117	2026-03-02 11:45:34.410117	\N	\N	\N	\N
1cd973e9-9210-41f8-ba6c-0b54bd9f8c95	TP-260302-0007	测试翻译项目批次 757	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	d7116c76-ae7c-4624-9e5b-4bad4418c74d	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-03-02 11:45:34.416105	2026-03-02 11:45:34.416105	\N	\N	\N	\N
d120d9f7-b0ab-46b1-9b03-e85a67666490	TP-260302-0008	测试翻译项目批次 726	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.422296	2026-03-02 11:45:34.422296	\N	\N	\N	\N
04d91a87-f7a0-4bf6-a899-557ec5ce2c36	TP-260302-0009	测试翻译项目批次 809	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.428856	2026-03-02 11:45:34.428856	\N	\N	\N	\N
3e50a26e-61a6-4bbe-9c80-0e05ad4d10ea	TP-260302-0010	测试翻译项目批次 508	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-03-02 11:45:34.434834	2026-03-02 11:45:34.434834	\N	\N	\N	\N
4ee5ca74-8e91-4f15-a388-9d820a7f84f4	TP-260302-0011	测试翻译项目批次 342	\N	4276a053-4cd7-4abc-87b7-a685a3044931	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-03-02 11:45:34.441294	2026-03-02 11:45:34.441294	\N	\N	\N	\N
42d2955b-d66a-4568-938e-896b2ba4cff7	TP-260228-0210	直插测试项目批次 312	\N	621ae0b3-4237-4e80-947e-1649b57b2253	\N	\N	\N	\N	pending	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	\N	\N
cc1c7817-b53d-472d-bfad-6051a0fbc323	TP-260302-0013	测试翻译项目批次 610		ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:13:15.630647	2026-03-02 20:13:15.630647	\N	\N	\N	\N
87d986e8-bb24-4e89-8407-3b6af6d8547f	TP-260228-0006	测试翻译项目批次 531		4276a053-4cd7-4abc-87b7-a685a3044931	\N	\N	\N		pending	1a55179f-026e-44f7-ac5d-c32bed603515	\N	\N	\N	\N								1a55179f-026e-44f7-ac5d-c32bed603515	2026-02-28 16:02:11.772405	2026-02-28 16:02:11.772405			0	\N
68644150-264c-4d8b-b040-47bf0498e0ec	TP-260228-0007	测试翻译项目批次 296		88bc493e-e357-4600-9de7-4a507be5e9fd	\N	\N	\N		pending	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	\N								b2c53252-9cb5-476e-b289-13019ad69c78	2026-02-28 16:02:11.780904	2026-02-28 16:02:11.780904			0	\N
ac6b248a-48aa-48ff-805f-c5e8d2852dbf	TP-260228-0005	测试翻译项目批次 363		c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N		pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N								e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.765485	2026-02-28 16:02:11.765485			0	\N
92c71151-584c-4d70-a657-f85c472c9390	TP-260302-0005	测试翻译项目批次 950	PDF	ce50afb4-ec6d-416e-91b7-b527f7a07abd	2026-03-11 00:00:00	2026-03-11 00:00:00	\N		paused	74c04077-ea7c-4978-9735-10413dc62aa3	\N	\N	\N	\N								74c04077-ea7c-4978-9735-10413dc62aa3	2026-03-02 11:45:34.403402	2026-03-02 11:45:34.403402	中译英		9999	\N
1c984f07-d318-473d-9fe2-921c3bec1dad	TP-260228-0003	测试翻译项目批次 840		4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	2026-03-12 00:00:00	\N		已暂停	fb5c69c5-e422-48e7-9214-025aacee74b0	\N	\N	\N	\N								fb5c69c5-e422-48e7-9214-025aacee74b0	2026-02-28 16:02:11.750898	2026-02-28 16:02:11.750898			0	\N
1a58dfb0-8324-4cdb-a9ed-994ab0a7da9c	TP-260302-0014	测试翻译项目批次 610		ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N		in_progress	\N	\N	\N	\N	\N								\N	2026-03-02 20:13:27.625592	2026-03-02 20:13:27.625592			0	\N
f3f59a1d-d792-4722-971d-63ebe9fd06cb	TP-260302-0003	测试翻译项目批次 267	\N	2ff609a6-da58-4045-9e52-f6a7bd98cc33	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	ba92e52a-f517-48a4-a422-1688f2afe067	2026-03-02 11:45:34.389738	2026-03-02 11:45:34.389738	\N	\N	\N	\N
b2b5fc81-163b-4497-a752-c7bff86d2d5e	TP-260228-0015	直插测试项目批次 314	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	in_progress	b2c53252-9cb5-476e-b289-13019ad69c78	\N	\N	\N	0	\N	\N	\N	\N	\N	\N	\N	b2c53252-9cb5-476e-b289-13019ad69c78	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N	0	\N
552d6dbb-4d84-4c78-95e5-db0af4b293d1	TP-260311-0003	游戏翻译项目	\N	88bc493e-e357-4600-9de7-4a507be5e9fd	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-03-11 19:51:21.83703	2026-03-11 19:51:21.83703	\N	\N	\N	\N
f2e1ba83-141b-4c0a-a460-a2265ea96788	TP-260228-0008	测试翻译项目批次 533	\N	00df42a2-291a-4917-ac60-0acec68e4c16	\N	\N	\N	\N	pending	d7116c76-ae7c-4624-9e5b-4bad4418c74d	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	d7116c76-ae7c-4624-9e5b-4bad4418c74d	2026-02-28 16:02:11.788583	2026-02-28 16:02:11.788583	\N	\N	\N	\N
edc19c21-49dd-4118-b066-daa4dd728411	TP-260228-0009	测试翻译项目批次 610	\N	ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.795767	2026-02-28 16:02:11.795767	\N	\N	\N	\N
29a286f7-3309-4dc6-b5cf-04c36ef7e0b0	TP-260314-0001	测试10086	\N	59e14867-dea0-49d4-bc14-220002a416e7	2026-03-12 00:00:00	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	1a55179f-026e-44f7-ac5d-c32bed603515	2026-03-14 13:01:10.890457	2026-03-14 13:01:10.890457	\N	\N	\N	\N
2de21aed-d67d-4e02-9f8b-a978973bfc6f	TP-260228-0031	直插测试项目批次 422	\N	c45edd34-2023-4b60-86d2-4ad6c815896e	\N	\N	\N		in_progress	ba92e52a-f517-48a4-a422-1688f2afe067	\N	2026-03-14 00:00:00	\N	\N	进行中							ba92e52a-f517-48a4-a422-1688f2afe067	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N		\N	\N
c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012	吉利		\N	2026-03-02 00:00:00	2026-03-04 00:00:00	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:09:43.396552	2026-03-02 20:09:43.396552	\N	\N	\N	\N
c9fcc0e2-256a-4455-8917-a9b5e4daed5e	TP-260302-0015	1231231		\N	\N	\N	\N		pending	\N	\N	\N	\N	\N								\N	2026-03-02 20:33:30.95642	2026-03-02 20:33:30.95642	\N	\N	\N	\N
185e9769-af62-473a-be28-bdb777f7eaa6	TP-260228-0004	测试翻译项目批次 490		ce50afb4-ec6d-416e-91b7-b527f7a07abd	\N	\N	\N		pending	1a55179f-026e-44f7-ac5d-c32bed603515	\N	\N	\N	\N								1a55179f-026e-44f7-ac5d-c32bed603515	2026-02-28 16:02:11.7579	2026-02-28 16:02:11.7579			0	\N
d82e59de-f57f-4c13-a225-7c4637e44627	TP-260228-0002	测试翻译项目批次 603		4b16bb7d-ce2c-4cc7-9453-3394825e712c	\N	\N	\N	\N	进行中	e228c697-4885-41a3-a02f-ef389defedd0	\N	2026-03-03 00:00:00	\N	\N	进行中	\N	\N	\N	\N		\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.739266	2026-02-28 16:02:11.739266	\N	\N	\N	\N
a383da7c-6457-4a13-a837-ea8a5e00a805	TP-260228-0010	测试翻译项目批次 170	\N	88bc493e-e357-4600-9de7-4a507be5e9fd	\N	\N	\N	\N	pending	e228c697-4885-41a3-a02f-ef389defedd0	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	e228c697-4885-41a3-a02f-ef389defedd0	2026-02-28 16:02:11.802266	2026-02-28 16:02:11.802266	\N	\N	\N	\N
\.


--
-- Data for Name: translation_sub_order; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.translation_sub_order (id, parent_project_id, sub_order_no, sub_project_name, language_pair, word_count, translator_id, translator_assignment_time, status, translator_delivery_progress, review_progress, layout_progress, network_file_path, remarks, created_at, updated_at, file_type_secondary, priority, customer_deadline_time, sent_to_client_time, client_feedback, expected_translator_stats_method, expected_translator_word_count, pre_review_qc_progress, review1_progress, review2_progress, post_review_qc_progress, consolidation_progress, created_by) FROM stdin;
6c9fb189-efcd-4131-83ce-8afa8c3e6f73	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0001	吉利	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 10:35:00.962471	2026-03-11 10:35:00.962471	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
7ef1f7a5-792c-4030-8f33-2d3154e12833	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0002	子订单2	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 11:59:01.811866	2026-03-11 11:59:01.811866	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
693f1819-f975-417b-baea-a9f51f0162d0	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0003	3	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:09:31.486153	2026-03-11 14:09:31.486153	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
93c86193-bac5-4e2f-a2a9-81873ebc7833	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0004	吉利-子订单04	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:32.866737	2026-03-11 14:23:32.866737	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
d9df8744-e538-4f40-804e-bee66217b2c4	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0005	吉利-子订单05	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:44.459159	2026-03-11 14:23:44.459159	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
957cdd40-31db-4e9f-be25-c4e48ff3dc7c	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0006	吉利-子订单06	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:44.783093	2026-03-11 14:23:44.783093	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
80e3493b-af85-4a51-8527-9571ab7f3fd3	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0007	吉利-子订单07	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:45.029961	2026-03-11 14:23:45.029961	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
53e6a741-380c-4a56-8d01-d0c1823705eb	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0008	吉利-子订单08	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:45.106209	2026-03-11 14:23:45.106209	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
a7759910-9491-46ac-a9ad-3c8b26ce51de	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0009	吉利-子订单09	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:23:45.352525	2026-03-11 14:23:45.352525	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
b3088e35-6291-44a5-bddb-553632e69ac6	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0010	吉利-子订单09	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:10.457371	2026-03-11 14:24:10.457371	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
c4470660-f1e3-4866-8b5d-fcfffdb16e91	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0011	吉利-子订单10	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:10.721639	2026-03-11 14:24:10.721639	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
348198cc-3f2e-406f-8ea7-8fb487cb8d4c	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0012	吉利-子订单11	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:10.768796	2026-03-11 14:24:10.768796	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
9cb0ec88-4d0b-4d8e-9714-f7dfed8ac241	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0013	吉利-子订单12	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.034445	2026-03-11 14:24:11.034445	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
0959b297-43b0-4730-b49b-74bcc704bae5	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0014	吉利-子订单13	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.080092	2026-03-11 14:24:11.080092	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
206a430b-07b3-4439-bbf7-ef525c22557f	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0015	吉利-子订单14	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.344199	2026-03-11 14:24:11.344199	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
67640eeb-d2d4-4cba-9c80-d6a87b021145	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0016	吉利-子订单15	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.390598	2026-03-11 14:24:11.390598	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
5ae68b0f-c24a-4489-b34e-0233c1afc42f	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0017	吉利-子订单16	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.668491	2026-03-11 14:24:11.668491	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
7b458f32-5999-4c31-9f83-f26b4fb228a0	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0018	吉利-子订单17	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.699687	2026-03-11 14:24:11.699687	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
4a0a9171-693c-43ec-b597-bd5f1e83aafc	c1cff36a-a800-4836-bcb7-2f4c7ca3bd43	TP-260302-0012.0019	吉利-子订单18	\N	0	\N	\N	pending	\N	\N	\N	\N	\N	2026-03-11 14:24:11.982582	2026-03-11 14:24:11.982582	\N	\N	2026-03-04 00:00:00	\N	\N	\N	0	\N	\N	\N	\N	\N	\N
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

COPY public.workflow_instance (id, translation_project_id, difficulty, file_editable, current_stage_key, current_assignee_id, project_status, stage_notes, stage_data, created_at, updated_at, group_assign_role, sub_order_id) FROM stdin;
b68b1897-1139-4317-80c8-2489edb2e988	185e9769-af62-473a-be28-bdb777f7eaa6	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.762264	2026-02-28 16:02:11.762264	\N	\N
3ef92b8e-c8b6-4873-a18f-2c56aff44f60	ac6b248a-48aa-48ff-805f-c5e8d2852dbf	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.769358	2026-02-28 16:02:11.769358	\N	\N
69563a01-6092-44b5-b687-d2238b05fd5a	87d986e8-bb24-4e89-8407-3b6af6d8547f	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.776867	2026-02-28 16:02:11.776867	\N	\N
534f8e68-dc5c-4528-a46f-606f46611728	68644150-264c-4d8b-b040-47bf0498e0ec	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.785409	2026-02-28 16:02:11.785409	\N	\N
2de2024e-52c0-4537-b963-be9f7fa3626b	f2e1ba83-141b-4c0a-a460-a2265ea96788	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.792893	2026-02-28 16:02:11.792893	\N	\N
e554de75-65b3-4f9b-aae2-99306410b37b	edc19c21-49dd-4118-b066-daa4dd728411	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.799714	2026-02-28 16:02:11.799714	\N	\N
23e7a18c-a9d2-4e13-8954-2157e0516996	a383da7c-6457-4a13-a837-ea8a5e00a805	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:02:11.806859	2026-02-28 16:02:11.806859	\N	\N
8a6aaec1-faaf-4551-a252-32abc60c8180	858c1e78-ad24-4ffb-9c5b-6bd645a6fc55	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
8eb8946e-bcfe-4431-9ab7-f9888be9cb56	9d869ebf-3d55-477d-a4db-0ec4e9c1488c	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
02bc9842-d57e-443e-b212-76d005323904	e95e6db2-3b58-4311-8525-e6691448829b	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
32c69615-b5a6-4f32-a192-ac66a079c60a	b2b5fc81-163b-4497-a752-c7bff86d2d5e	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
78698395-06be-4898-980b-bbeb117f469b	c3cc69e8-f65b-42c3-bb7a-1628215a73e9	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
9ffb21ce-99b4-4c97-95c3-65497b91f698	8bacd012-a839-411c-9020-dd85d35d5c7d	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
22d46333-abca-4ab5-b51e-959716c0cbd9	efed205d-a908-4bb2-955a-0e1eb2c3c81b	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
ed986155-421c-45b9-a76c-fdf8258e6941	a3bb5bb9-11a1-4dc2-9b21-640848ed716a	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
9969eadf-44bc-4f48-a69a-94c32b0ac3f8	42d2955b-d66a-4568-938e-896b2ba4cff7	\N	\N	reception	\N	pending	{}	{}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
fa30ce83-e2da-44eb-a2b1-92eb8c040ccb	7b50514a-672d-49a6-9254-c2a470c91b29	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.400821	2026-03-02 11:45:34.400821	\N	\N
d2806189-51d6-404c-b7ce-a60e53d03d6a	bed7e3f0-d977-4fe9-b9ea-b079d55cde6d	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.413611	2026-03-02 11:45:34.413611	\N	\N
1e1f83a2-5278-406c-bccd-15fc493f76a5	1cd973e9-9210-41f8-ba6c-0b54bd9f8c95	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.41965	2026-03-02 11:45:34.41965	\N	\N
2b2c3a80-8051-4a47-8199-3921616e7d99	d120d9f7-b0ab-46b1-9b03-e85a67666490	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.426502	2026-03-02 11:45:34.426502	\N	\N
4e9b57dd-5ffd-488b-8346-9dd7657a06ae	04d91a87-f7a0-4bf6-a899-557ec5ce2c36	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.432493	2026-03-02 11:45:34.432493	\N	\N
37055887-4922-4d78-8d17-77363acd7d31	3e50a26e-61a6-4bbe-9c80-0e05ad4d10ea	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.438714	2026-03-02 11:45:34.438714	\N	\N
ce155bfd-fee9-4642-aa6c-4f8b782eda3d	4ee5ca74-8e91-4f15-a388-9d820a7f84f4	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.445152	2026-03-02 11:45:34.445152	\N	\N
4c8ef8aa-3a05-436b-996e-7c86faf354e8	d82e59de-f57f-4c13-a225-7c4637e44627	simple	t	completed	\N	completed	{"layout": "这个直接给客户专员交稿", "reception": "（无备注）", "special_qc": "直接排版", "project_assistant": "直接去专检", "project_specialist": "这是HR处理的阶段"}	{"layout": {"actualTime": "2026-03-03 09:29:01", "layoutNote": "", "estimatedTime": "", "projectStatus": "进行中", "layoutProgress": ""}, "reception": {"fileType": "", "wordCount": "", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": ""}, "special_qc": {"actualTime": "2026-03-03 09:27:31", "estimatedTime": "", "projectStatus": "进行中", "specialQcNote": "", "specialQcResult": ""}, "project_assistant": {"actualTime": "2", "estimatedTime": "1", "projectStatus": "进行中", "translatorAssignee": "孙红艳", "translatorAssignmentTime": "2026-03-03 00:00:00", "translatorDeliveryProgress": "进行中"}, "project_specialist": {"actualTime": "2026-03-03 09:23:54", "languagePair": "", "estimatedTime": "", "projectStatus": "进行中", "fileTypeSecondary": ""}}	2026-02-28 16:02:11.747316	2026-02-28 16:02:11.747316	\N	\N
533d9a5c-30a5-4c89-990f-684ac14c62ad	f3f59a1d-d792-4722-971d-63ebe9fd06cb	simple	t	project_assistant	f174bde7-af8b-4c28-b94e-4d2c07bab29c	in_progress	{"reception": "（无备注）"}	{"reception": {"wordCount": "", "languagePair": "", "projectStatus": "", "fileTypeSecondary": "", "customerDeadlineTime": "", "customerReceptionTime": ""}}	2026-03-02 11:45:34.395095	2026-03-02 11:45:34.395095	\N	\N
c54ef09d-4918-4ec6-b3b5-a7515be25858	12eb4bfd-8bd6-4a34-8010-5045d2c4fd6b	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:43:26.160876	2026-03-02 11:43:26.160876	\N	\N
66bb4de4-01aa-458e-bfc9-fefde720875d	c3730723-a1e9-4be0-8a17-1082355a74c8	simple	t	project_assistant	e228c697-4885-41a3-a02f-ef389defedd0	in_progress	{"reception": "下一步", "project_specialist": "无问题"}	{"reception": {"fileType": "", "wordCount": "这是一个测试", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": "2026-03-02 00:00:00"}, "project_assistant": {"actualTime": "", "estimatedTime": "", "projectStatus": "进行中", "translatorAssignee": "", "translatorAssignmentTime": "", "translatorDeliveryProgress": ""}, "project_specialist": {"actualTime": "测试", "languagePair": "测试", "estimatedTime": "测试", "projectStatus": "已暂停", "fileTypeSecondary": "测试"}}	2026-02-28 16:02:11.731746	2026-02-28 16:02:11.731746	\N	\N
0b1e670a-d91e-42c6-b33a-46545aee8ca4	be8e9dcd-8ba9-410f-ba19-64aa51c99dd0	\N	\N	reception	\N	pending	{}	{}	2026-03-02 11:45:34.383733	2026-03-02 11:45:34.383733	\N	\N
87a1b169-1e1e-4c42-b086-c1b26718ff46	92c71151-584c-4d70-a657-f85c472c9390	\N	\N	reception	\N	pending	{}	{"reception": {"wordCount": "9999", "languagePair": "中译英", "projectStatus": "terminated", "fileTypeSecondary": "PDF", "customerDeadlineTime": "2026-03-11 00:00:00", "customerReceptionTime": "2026-03-11 00:00:00"}}	2026-03-02 11:45:34.407333	2026-03-02 11:45:34.407333	\N	\N
12d400f9-0127-4f3b-af41-02454375793c	1c984f07-d318-473d-9fe2-921c3bec1dad	complex	f	project_manager	74c04077-ea7c-4978-9735-10413dc62aa3	in_progress	{"reception": "（无备注）", "layout_assign": "（无备注）"}	{"reception": {"fileType": "", "wordCount": "", "clientShortName": "", "customerDeadlineTime": "", "translationDirection": "", "customerReceptionTime": ""}, "layout_assign": {"actualTime": "2026-03-04 18:03:29", "estimatedTime": "", "projectStatus": "进行中", "layoutAssignNote": ""}, "project_manager": {"priority": "", "wordCount": "", "actualTime": "", "estimatedTime": "", "projectStatus": "已暂停"}}	2026-02-28 16:02:11.755339	2026-02-28 16:02:11.755339	\N	\N
f1a09290-0618-4752-a33e-6fa9111c7106	29a286f7-3309-4dc6-b5cf-04c36ef7e0b0	\N	\N	reception	\N	pending	{}	{}	2026-03-14 13:01:10.890457	2026-03-14 13:01:10.890457	\N	\N
99d41139-ef4c-4291-8119-fc0911cbf50a	\N	\N	\N	reception	\N	pending	{}	{}	2026-03-16 14:52:46.319832	2026-03-16 14:52:46.319832	\N	4a0a9171-693c-43ec-b597-bd5f1e83aafc
4072ba0a-306d-4055-9674-beec3a805e2a	2de21aed-d67d-4e02-9f8b-a978973bfc6f	simple	t	special_qc	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	in_progress	{"reception": "（无备注）", "project_assistant": "（无备注）"}	{"reception": {"wordCount": "", "languagePair": "", "projectStatus": "", "fileTypeSecondary": "", "customerDeadlineTime": "", "customerReceptionTime": null}, "project_assistant": {"actualTime": "2026-03-14 14:25:51", "estimatedTime": "30min", "projectStatus": "in_progress", "translatorAssignee": "", "translatorAssignmentTime": "2026-03-14 00:00:00", "translatorDeliveryProgress": "进行中"}}	2026-02-28 16:33:35.934747	2026-02-28 16:33:35.934747	\N	\N
149deea2-df23-4f46-9908-d72f8073e1d3	\N	\N	\N	reception	\N	pending	{}	{}	2026-03-16 15:02:21.568276	2026-03-16 15:02:21.568276	\N	d9df8744-e538-4f40-804e-bee66217b2c4
243a658f-98b9-409b-b070-cfccad8965c7	\N	\N	\N	reception	\N	pending	{}	{}	2026-03-16 15:02:24.228829	2026-03-16 15:02:24.228829	\N	a7759910-9491-46ac-a9ad-3c8b26ce51de
0da9fb3d-3ed5-4607-957c-9834a6adbd25	552d6dbb-4d84-4c78-95e5-db0af4b293d1	\N	\N	reception	\N	pending	{}	{"reception": {"wordCount": "", "languagePair": "", "projectStatus": "", "fileTypeSecondary": "", "customerDeadlineTime": "", "customerReceptionTime": ""}}	2026-03-16 15:01:54.142625	2026-03-16 15:01:54.142625	\N	\N
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
1d0a3696-cc17-4502-8851-8c8b90922f18	f1a09290-0618-4752-a33e-6fa9111c7106	\N		reception	forward	进入接稿（客户专员）	系统自动初始化	\N	2026-03-14 13:01:10.890457
35fe6780-070b-4d3f-acdd-40e24e255afb	4072ba0a-306d-4055-9674-beec3a805e2a	74c04077-ea7c-4978-9735-10413dc62aa3	reception	project_assistant	forward	Difficulty set to simple; moved to project_assistant. Assigned to 翠珍.	（无备注）	f174bde7-af8b-4c28-b94e-4d2c07bab29c	2026-03-14 14:23:27.38884
fb046ce3-d692-46ef-be8f-b31a0220c373	4072ba0a-306d-4055-9674-beec3a805e2a	f174bde7-af8b-4c28-b94e-4d2c07bab29c	project_assistant	special_qc	forward	Moved from project_assistant to special_qc, assigned to 楚翘.	（无备注）	27d39bdb-4d1a-4348-9a0f-7b5e1441dd4f	2026-03-14 14:25:51.488808
65348fa2-173c-44d2-8717-fe1da3bea071	533d9a5c-30a5-4c89-990f-684ac14c62ad	1a55179f-026e-44f7-ac5d-c32bed603515	reception	project_assistant	forward	Difficulty set to simple; moved to project_assistant. Assigned to 翠珍.	（无备注）	f174bde7-af8b-4c28-b94e-4d2c07bab29c	2026-03-14 18:15:04.169465
ca688141-66f0-4833-90e2-e267dca017cc	99d41139-ef4c-4291-8119-fc0911cbf50a	\N		reception	forward	Workflow initialized at reception stage.	System initialization	\N	2026-03-16 14:52:46.319832
4957de2d-a4e8-4f95-ade7-5122902c870e	0da9fb3d-3ed5-4607-957c-9834a6adbd25	\N		reception	forward	Workflow initialized at reception stage.	System initialization	\N	2026-03-16 15:01:54.142625
6cbe9203-f687-4dd5-8125-b925eee087f1	149deea2-df23-4f46-9908-d72f8073e1d3	\N		reception	forward	Workflow initialized at reception stage.	System initialization	\N	2026-03-16 15:02:21.568276
5f7ce749-f724-4330-a067-040fae1ae45c	243a658f-98b9-409b-b070-cfccad8965c7	\N		reception	forward	Workflow initialized at reception stage.	System initialization	\N	2026-03-16 15:02:24.228829
\.


--
-- Name: app_notification app_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_notification
    ADD CONSTRAINT app_notification_pkey PRIMARY KEY (id);


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
-- Name: chat_project_enabled chat_project_enabled_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_enabled
    ADD CONSTRAINT chat_project_enabled_pkey PRIMARY KEY (id);


--
-- Name: chat_project_mention chat_project_mention_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_mention
    ADD CONSTRAINT chat_project_mention_pkey PRIMARY KEY (id);


--
-- Name: chat_project_message chat_project_message_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_message
    ADD CONSTRAINT chat_project_message_pkey PRIMARY KEY (id);


--
-- Name: client client_client_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT client_client_code_key UNIQUE (client_code);


--
-- Name: client_contact client_contact_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client_contact
    ADD CONSTRAINT client_contact_pkey PRIMARY KEY (id);


--
-- Name: client client_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT client_pkey PRIMARY KEY (id);


--
-- Name: consultation consultation_consultation_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT consultation_consultation_code_key UNIQUE (consultation_code);


--
-- Name: consultation consultation_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT consultation_pkey PRIMARY KEY (id);


--
-- Name: employee_leave employee_leave_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_leave
    ADD CONSTRAINT employee_leave_pkey PRIMARY KEY (id);


--
-- Name: finance_payment finance_payment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_payment
    ADD CONSTRAINT finance_payment_pkey PRIMARY KEY (id);


--
-- Name: finance_record finance_record_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT finance_record_pkey PRIMARY KEY (id);


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
-- Name: sub_client sub_client_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sub_client
    ADD CONSTRAINT sub_client_code_key UNIQUE (sub_client_code);


--
-- Name: sub_client sub_client_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sub_client
    ADD CONSTRAINT sub_client_pkey PRIMARY KEY (id);


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
-- Name: translation_sub_order translation_sub_order_no_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_sub_order
    ADD CONSTRAINT translation_sub_order_no_key UNIQUE (sub_order_no);


--
-- Name: translation_sub_order translation_sub_order_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_sub_order
    ADD CONSTRAINT translation_sub_order_pkey PRIMARY KEY (id);


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
-- Name: chat_project_enabled uq_chat_project_enabled_project; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_enabled
    ADD CONSTRAINT uq_chat_project_enabled_project UNIQUE (project_id);


--
-- Name: chat_project_mention uq_chat_project_mention_message_user; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_mention
    ADD CONSTRAINT uq_chat_project_mention_message_user UNIQUE (message_id, mentioned_user_id);


--
-- Name: finance_payment uq_finance_payment_stage; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_payment
    ADD CONSTRAINT uq_finance_payment_stage UNIQUE (finance_id, stage_type, stage_no);


--
-- Name: finance_record uq_finance_record_project; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT uq_finance_record_project UNIQUE (project_id);


--
-- Name: user_role uq_user_role; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_role
    ADD CONSTRAINT uq_user_role UNIQUE (user_id, role_id);


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
-- Name: idx_consultation_client_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_consultation_client_id ON public.consultation USING btree (client_id);


--
-- Name: idx_consultation_consultation_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_consultation_consultation_code ON public.consultation USING btree (consultation_code);


--
-- Name: idx_consultation_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_consultation_status ON public.consultation USING btree (status);


--
-- Name: idx_finance_payment_confirmed_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_payment_confirmed_by ON public.finance_payment USING btree (confirmed_by);


--
-- Name: idx_finance_payment_finance; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_payment_finance ON public.finance_payment USING btree (finance_id);


--
-- Name: idx_finance_payment_payment_time; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_payment_payment_time ON public.finance_payment USING btree (payment_time);


--
-- Name: idx_finance_record_follow_up_person; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_record_follow_up_person ON public.finance_record USING btree (follow_up_person_id);


--
-- Name: idx_finance_record_invoice_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_record_invoice_status ON public.finance_record USING btree (invoice_status);


--
-- Name: idx_finance_record_sales_person; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_finance_record_sales_person ON public.finance_record USING btree (sales_person_id);


--
-- Name: ix_chat_project_mention_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_chat_project_mention_user_id ON public.chat_project_mention USING btree (mentioned_user_id);


--
-- Name: ix_chat_project_message_project_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_chat_project_message_project_created_at ON public.chat_project_message USING btree (project_id, created_at);


--
-- Name: ix_chat_project_message_sender_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_chat_project_message_sender_user_id ON public.chat_project_message USING btree (sender_user_id);


--
-- Name: uq_workflow_project; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_workflow_project ON public.workflow_instance USING btree (translation_project_id) WHERE (translation_project_id IS NOT NULL);


--
-- Name: uq_workflow_suborder; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_workflow_suborder ON public.workflow_instance USING btree (sub_order_id) WHERE (sub_order_id IS NOT NULL);


--
-- Name: finance_payment trg_finance_payment_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_finance_payment_updated_at BEFORE UPDATE ON public.finance_payment FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: finance_record trg_finance_record_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_finance_record_updated_at BEFORE UPDATE ON public.finance_record FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: app_notification fk_app_notification_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_notification
    ADD CONSTRAINT fk_app_notification_project FOREIGN KEY (related_project_id) REFERENCES public.translation_project(id) ON DELETE SET NULL;


--
-- Name: app_notification fk_app_notification_recipient; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.app_notification
    ADD CONSTRAINT fk_app_notification_recipient FOREIGN KEY (recipient_user_id) REFERENCES public.app_user(id) ON DELETE CASCADE;


--
-- Name: chat_project_enabled fk_chat_project_enabled_operator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_enabled
    ADD CONSTRAINT fk_chat_project_enabled_operator FOREIGN KEY (enabled_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: chat_project_enabled fk_chat_project_enabled_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_enabled
    ADD CONSTRAINT fk_chat_project_enabled_project FOREIGN KEY (project_id) REFERENCES public.translation_project(id) ON DELETE CASCADE;


--
-- Name: chat_project_mention fk_chat_project_mention_message; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_mention
    ADD CONSTRAINT fk_chat_project_mention_message FOREIGN KEY (message_id) REFERENCES public.chat_project_message(id) ON DELETE CASCADE;


--
-- Name: chat_project_mention fk_chat_project_mention_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_mention
    ADD CONSTRAINT fk_chat_project_mention_user FOREIGN KEY (mentioned_user_id) REFERENCES public.app_user(id) ON DELETE CASCADE;


--
-- Name: chat_project_message fk_chat_project_message_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_message
    ADD CONSTRAINT fk_chat_project_message_project FOREIGN KEY (project_id) REFERENCES public.translation_project(id) ON DELETE CASCADE;


--
-- Name: chat_project_message fk_chat_project_message_sender; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chat_project_message
    ADD CONSTRAINT fk_chat_project_message_sender FOREIGN KEY (sender_user_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: client_contact fk_client_contact_client; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.client_contact
    ADD CONSTRAINT fk_client_contact_client FOREIGN KEY (client_id) REFERENCES public.client(id) ON DELETE SET NULL;


--
-- Name: consultation fk_consultation_client; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT fk_consultation_client FOREIGN KEY (client_id) REFERENCES public.client(id) ON DELETE SET NULL;


--
-- Name: consultation fk_consultation_customer_service; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT fk_consultation_customer_service FOREIGN KEY (customer_service_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: consultation fk_consultation_editor; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT fk_consultation_editor FOREIGN KEY (editor_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: consultation fk_consultation_follow_up_person; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT fk_consultation_follow_up_person FOREIGN KEY (follow_up_person_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: consultation fk_consultation_sales_person; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.consultation
    ADD CONSTRAINT fk_consultation_sales_person FOREIGN KEY (sales_person_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: finance_payment fk_finance_payment_confirmed_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_payment
    ADD CONSTRAINT fk_finance_payment_confirmed_by FOREIGN KEY (confirmed_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: finance_payment fk_finance_payment_finance; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_payment
    ADD CONSTRAINT fk_finance_payment_finance FOREIGN KEY (finance_id) REFERENCES public.finance_record(id) ON DELETE CASCADE;


--
-- Name: finance_record fk_finance_record_edited_by; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT fk_finance_record_edited_by FOREIGN KEY (edited_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: finance_record fk_finance_record_follow_up_person; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT fk_finance_record_follow_up_person FOREIGN KEY (follow_up_person_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: finance_record fk_finance_record_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT fk_finance_record_project FOREIGN KEY (project_id) REFERENCES public.translation_project(id) ON DELETE RESTRICT;


--
-- Name: finance_record fk_finance_record_sales_person; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.finance_record
    ADD CONSTRAINT fk_finance_record_sales_person FOREIGN KEY (sales_person_id) REFERENCES public.app_user(id) ON DELETE SET NULL;


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
-- Name: sub_client fk_sub_client_parent; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sub_client
    ADD CONSTRAINT fk_sub_client_parent FOREIGN KEY (parent_client_id) REFERENCES public.client(id) ON DELETE CASCADE;


--
-- Name: translation_sub_order fk_sub_order_creator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_sub_order
    ADD CONSTRAINT fk_sub_order_creator FOREIGN KEY (created_by) REFERENCES public.app_user(id) ON DELETE SET NULL;


--
-- Name: translation_sub_order fk_sub_order_parent_project; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_sub_order
    ADD CONSTRAINT fk_sub_order_parent_project FOREIGN KEY (parent_project_id) REFERENCES public.translation_project(id) ON DELETE CASCADE;


--
-- Name: translation_sub_order fk_sub_order_translator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.translation_sub_order
    ADD CONSTRAINT fk_sub_order_translator FOREIGN KEY (translator_id) REFERENCES public.translator(id) ON DELETE SET NULL;


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
-- Name: workflow_instance workflow_instance_sub_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.workflow_instance
    ADD CONSTRAINT workflow_instance_sub_order_id_fkey FOREIGN KEY (sub_order_id) REFERENCES public.translation_sub_order(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict F1QRRfVu4NtJt24967bB1hIHQTZlkWMkpukCIvODUAs4qpLmpkhsawG2hBuLuia

