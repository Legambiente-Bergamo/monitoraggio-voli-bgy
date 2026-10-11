--
-- PostgreSQL database dump
--

\restrict fQXSqK4FIjde1GI58eit1acrKPwkADgwI6UFYOog7zrYtpfpiBbfgxukanfFg4R

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: aircraft_by_code; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.aircraft_by_code (
    code character varying(10) NOT NULL,
    model character varying(100)
);


ALTER TABLE public.aircraft_by_code OWNER TO bgy_user;

--
-- Name: aircraft_models; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.aircraft_models (
    model character varying(100) NOT NULL,
    seats_2class integer,
    seats_max integer,
    seats_default integer,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.aircraft_models OWNER TO bgy_user;

--
-- Name: airlines; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.airlines (
    code character varying(10) NOT NULL,
    name character varying(200) NOT NULL,
    is_cargo boolean DEFAULT false,
    is_charter boolean DEFAULT false,
    source character varying(20) DEFAULT 'config'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.airlines OWNER TO bgy_user;

--
-- Name: alert_messages; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.alert_messages (
    key character varying(50) NOT NULL,
    subject character varying(300),
    body text,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.alert_messages OWNER TO bgy_user;

--
-- Name: assaeroporti_stats; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.assaeroporti_stats (
    year integer NOT NULL,
    passengers bigint,
    movements integer,
    cargo_ton integer,
    source character varying(50),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.assaeroporti_stats OWNER TO bgy_user;

--
-- Name: callsign_airline_patterns; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.callsign_airline_patterns (
    pattern character varying(10) NOT NULL,
    airline_iata character varying(3) NOT NULL,
    note text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.callsign_airline_patterns OWNER TO bgy_user;

--
-- Name: callsign_classifications; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.callsign_classifications (
    callsign character varying(10) NOT NULL,
    categoria character varying(30) NOT NULL,
    nome_compagnia character varying(100),
    note text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.callsign_classifications OWNER TO bgy_user;

--
-- Name: config_settings; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.config_settings (
    key character varying(100) NOT NULL,
    value text,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.config_settings OWNER TO bgy_user;

--
-- Name: countries; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.countries (
    destination character varying(200) NOT NULL,
    country character varying(100) NOT NULL,
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.countries OWNER TO bgy_user;

--
-- Name: iata_to_icao; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.iata_to_icao (
    iata character varying(3) NOT NULL,
    icao character varying(4) NOT NULL
);


ALTER TABLE public.iata_to_icao OWNER TO bgy_user;

--
-- Name: load_factors; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.load_factors (
    code character varying(10) NOT NULL,
    load_factor numeric(4,3) NOT NULL
);


ALTER TABLE public.load_factors OWNER TO bgy_user;

--
-- Name: noise_curves; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.noise_curves (
    id integer NOT NULL,
    aircraft_model character varying(100) NOT NULL,
    phase character varying(50) NOT NULL,
    distance_m integer NOT NULL,
    noise_db numeric(5,1) NOT NULL
);


ALTER TABLE public.noise_curves OWNER TO bgy_user;

--
-- Name: noise_curves_id_seq; Type: SEQUENCE; Schema: public; Owner: bgy_user
--

CREATE SEQUENCE public.noise_curves_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.noise_curves_id_seq OWNER TO bgy_user;

--
-- Name: noise_curves_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bgy_user
--

ALTER SEQUENCE public.noise_curves_id_seq OWNED BY public.noise_curves.id;


--
-- Name: noise_stations; Type: TABLE; Schema: public; Owner: bgy_user
--

CREATE TABLE public.noise_stations (
    name character varying(200) NOT NULL,
    lat numeric(10,6),
    lon numeric(10,6)
);


ALTER TABLE public.noise_stations OWNER TO bgy_user;

--
-- Name: noise_curves id; Type: DEFAULT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.noise_curves ALTER COLUMN id SET DEFAULT nextval('public.noise_curves_id_seq'::regclass);


--
-- Name: aircraft_by_code aircraft_by_code_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.aircraft_by_code
    ADD CONSTRAINT aircraft_by_code_pkey PRIMARY KEY (code);


--
-- Name: aircraft_models aircraft_models_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.aircraft_models
    ADD CONSTRAINT aircraft_models_pkey PRIMARY KEY (model);


--
-- Name: airlines airlines_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.airlines
    ADD CONSTRAINT airlines_pkey PRIMARY KEY (code);


--
-- Name: alert_messages alert_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.alert_messages
    ADD CONSTRAINT alert_messages_pkey PRIMARY KEY (key);


--
-- Name: assaeroporti_stats assaeroporti_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.assaeroporti_stats
    ADD CONSTRAINT assaeroporti_stats_pkey PRIMARY KEY (year);


--
-- Name: callsign_airline_patterns callsign_airline_patterns_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.callsign_airline_patterns
    ADD CONSTRAINT callsign_airline_patterns_pkey PRIMARY KEY (pattern);


--
-- Name: callsign_classifications callsign_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.callsign_classifications
    ADD CONSTRAINT callsign_classifications_pkey PRIMARY KEY (callsign);


--
-- Name: config_settings config_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.config_settings
    ADD CONSTRAINT config_settings_pkey PRIMARY KEY (key);


--
-- Name: countries countries_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.countries
    ADD CONSTRAINT countries_pkey PRIMARY KEY (destination);


--
-- Name: iata_to_icao iata_to_icao_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.iata_to_icao
    ADD CONSTRAINT iata_to_icao_pkey PRIMARY KEY (iata);


--
-- Name: load_factors load_factors_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.load_factors
    ADD CONSTRAINT load_factors_pkey PRIMARY KEY (code);


--
-- Name: noise_curves noise_curves_aircraft_model_phase_distance_m_key; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.noise_curves
    ADD CONSTRAINT noise_curves_aircraft_model_phase_distance_m_key UNIQUE (aircraft_model, phase, distance_m);


--
-- Name: noise_curves noise_curves_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.noise_curves
    ADD CONSTRAINT noise_curves_pkey PRIMARY KEY (id);


--
-- Name: noise_stations noise_stations_pkey; Type: CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.noise_stations
    ADD CONSTRAINT noise_stations_pkey PRIMARY KEY (name);


--
-- Name: idx_airlines_flags; Type: INDEX; Schema: public; Owner: bgy_user
--

CREATE INDEX idx_airlines_flags ON public.airlines USING btree (is_cargo, is_charter);


--
-- Name: idx_airlines_name; Type: INDEX; Schema: public; Owner: bgy_user
--

CREATE INDEX idx_airlines_name ON public.airlines USING btree (name);


--
-- Name: idx_countries_country; Type: INDEX; Schema: public; Owner: bgy_user
--

CREATE INDEX idx_countries_country ON public.countries USING btree (country);


--
-- Name: idx_noise_curves_model; Type: INDEX; Schema: public; Owner: bgy_user
--

CREATE INDEX idx_noise_curves_model ON public.noise_curves USING btree (aircraft_model);


--
-- Name: aircraft_by_code aircraft_by_code_model_fkey; Type: FK CONSTRAINT; Schema: public; Owner: bgy_user
--

ALTER TABLE ONLY public.aircraft_by_code
    ADD CONSTRAINT aircraft_by_code_model_fkey FOREIGN KEY (model) REFERENCES public.aircraft_models(model) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict fQXSqK4FIjde1GI58eit1acrKPwkADgwI6UFYOog7zrYtpfpiBbfgxukanfFg4R

