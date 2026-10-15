--
-- PostgreSQL database dump
--

\restrict HgvaHLgl7G7KuSTii7lQBZ8jHnfVKEqOLo4zSBsJXTJRoSr1tixMbvwwdLy6mzd

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

--
-- Data for Name: aircraft_models; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Boeing 737-800', 170, 189, 175, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Boeing 737-700', 130, 149, 140, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Boeing 777-300ER', 350, 425, 380, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Airbus A320-200', 165, 180, 170, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Airbus A319-100', 140, 150, 145, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Airbus A321-200', 200, 226, 210, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Embraer E190', 104, 108, 105, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('ATR 72-600', 72, 78, 74, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Dash 8-400', 76, 90, 78, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('N/D', 0, 0, 0, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_models (model, seats_2class, seats_max, seats_default, updated_at) VALUES ('Boeing 757-200', NULL, NULL, NULL, '2026-09-24 13:26:39.039202') ON CONFLICT DO NOTHING;


--
-- Data for Name: aircraft_by_code; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.aircraft_by_code (code, model) VALUES ('RYR', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('FR', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('WZZ', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('W6', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('W4', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EJU', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EZY', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AZ', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AZA', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('ITY', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('DHL', 'Boeing 757-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EK', 'Boeing 777-300ER') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('FZ', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('VF', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('DN', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('D8', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('PC', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('BAW', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AFR', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('KLM', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('SWR', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('DLH', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TUI', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EXS', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('NAX', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TOM', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TCX', 'Airbus A321-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('MON', 'Boeing 737-700') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EWG', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EIN', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('SAS', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('IBE', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('VY', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('U2', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('LS', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('WUK', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('WMT', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('BMS', 'Boeing 737-700') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('0B', 'Boeing 737-700') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('XZ', 'Dash 8-400') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('LDA', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('MAL', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EW', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AB', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('4U', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('GWI', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('BA', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('LH', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('LX', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TK', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AT', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TP', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('OS', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('SN', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('LO', 'Embraer E190') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('OK', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('RO', 'Boeing 737-700') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('FB', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('A3', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('CY', 'Airbus A319-100') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('RJ', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('MS', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('TU', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('AH', 'Boeing 737-700') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('SV', 'Boeing 777-300ER') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('QR', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('EY', 'Boeing 777-300ER') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('GF', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('KU', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('WY', 'Boeing 737-800') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('IR', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('G9', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('3O', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('SM', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('J2', 'Embraer E190') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('KC', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('HY', 'Airbus A320-200') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('YW', 'ATR 72-600') ON CONFLICT DO NOTHING;
INSERT INTO public.aircraft_by_code (code, model) VALUES ('F3', 'Airbus A320-200') ON CONFLICT DO NOTHING;


--
-- Data for Name: airlines; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IVL', 'Compagnia IVL', false, false, 'auto', '2026-09-24 14:02:21.948772', '2026-09-24 14:02:21.948772') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('P4O', 'Privato (P4-OWL)', false, false, 'manual', '2026-09-24 14:01:53.30002', '2026-09-24 20:52:04.429811') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BBG', 'Bluebird Airways (BZ)', false, false, 'auto', '2026-09-25 06:30:02.151868', '2026-09-25 06:30:02.151868') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('N94', 'Compagnia N94', false, false, 'auto', '2026-10-02 19:20:23.794905', '2026-10-02 19:20:23.794905') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('PGT', 'Pegasus Airlines', false, false, 'auto', '2026-10-02 19:20:24.546754', '2026-10-02 19:20:24.546754') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AOM', 'AOM French Airlines', false, false, 'auto', '2026-10-02 19:20:24.947822', '2026-10-02 19:20:24.947822') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NSZ', 'Norwegian Air Sweden', false, false, 'manual', '2026-10-02 19:20:23.41512', '2026-10-04 10:37:12.264068') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AGR', 'United States Department Of Agriculture', false, false, 'auto', '2026-10-05 06:30:00.652582', '2026-10-05 06:30:00.652582') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BN', 'Luxwing', false, false, 'manual', '2026-10-06 09:09:33.705006', '2026-10-06 09:09:33.705006') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('H7', 'HiSky', false, false, 'manual', '2026-10-06 09:09:33.988152', '2026-10-06 09:09:33.988152') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ZQ', 'German Airways', false, false, 'manual', '2026-10-06 09:09:34.25669', '2026-10-06 09:09:34.25669') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MV', 'Air Mediterranean', false, false, 'manual', '2026-10-06 09:09:34.502262', '2026-10-06 09:09:34.502262') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('C3', 'Trade Air', false, false, 'manual', '2026-09-25 06:30:01.303564', '2026-09-25 17:24:31.738228') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GH', 'Georgian Airlines', false, false, 'manual', '2026-10-07 11:40:58.966822', '2026-10-07 14:08:50.933682') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SSR', 'Sardinian Sky Service', false, true, 'manual', '2026-10-05 06:30:10.06622', '2026-10-07 22:11:12.765126') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ABY', 'Air Arabia Abu Dhabi', false, false, 'manual', '2026-10-08 17:13:37.234818', '2026-10-08 17:13:37.234818') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TCV', 'TACV', false, false, 'auto', '2026-10-11 06:30:07.80046', '2026-10-11 06:30:07.80046') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AEH', 'Aviaexpress', false, false, 'auto', '2026-09-24 14:01:58.645652', '2026-09-24 14:01:58.645652') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SPM', 'Air Saint Pierre', false, false, 'auto', '2026-09-27 06:30:01.545494', '2026-09-27 06:30:01.545494') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AP', 'AlbaStar', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-10-02 18:21:08.074295') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('PVR', 'Compagnia PVR', false, false, 'auto', '2026-10-02 19:20:23.568968', '2026-10-02 19:20:23.568968') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FHL', 'Fast Helicopters', false, false, 'auto', '2026-10-02 19:20:23.92648', '2026-10-02 19:20:23.92648') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ILM', 'Compagnia ILM', false, false, 'auto', '2026-10-02 19:20:24.297316', '2026-10-02 19:20:24.297316') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FCA', 'First Choice Airways', false, false, 'auto', '2026-10-02 19:20:24.683477', '2026-10-02 19:20:24.683477') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TGZ', 'Georgian Airways', false, false, 'auto', '2026-10-02 19:33:38.129781', '2026-10-02 19:33:38.129781') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RM', 'Aircompany Armenia', false, false, 'manual', '2026-10-06 09:09:33.587174', '2026-10-06 09:09:33.587174') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('H4', 'HiSky Europe', false, false, 'manual', '2026-10-06 09:09:33.837849', '2026-10-06 09:09:33.837849') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('UJ', 'Almasria Universal', false, false, 'manual', '2026-10-06 09:09:34.126608', '2026-10-06 09:09:34.126608') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('H6', 'European Air Charter', false, false, 'manual', '2026-10-06 09:09:34.375161', '2026-10-06 09:09:34.375161') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SE', 'Sky Vision Airlines', false, false, 'manual', '2026-10-06 09:09:34.62586', '2026-10-06 09:09:34.62586') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VND', 'Avionord', false, false, 'manual', '2026-09-24 14:02:35.633568', '2026-10-06 09:48:34.264773') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IMV', 'Compagnia IMV', false, false, 'auto', '2026-10-10 06:30:12.820082', '2026-10-10 06:30:12.820082') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('0B', 'Blue Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('3F', 'FlyOne', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('3O', 'Air Arabia Maroc', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('4U', 'Eurowings', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('A3', 'Aegean Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('A9', 'Georgian Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AAR', 'Asiana Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AB', 'Air Berlin', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ABX', 'ABX Air', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AEE', 'Aegean Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AEG', 'Aegean Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AFR', 'Air France', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AH', 'Air Algérie', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AIC', 'Air India', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ANE', 'Air Nostrum', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AT', 'Royal Air Maroc', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AZ', 'ITA Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AZA', 'ITA Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BA', 'British Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BAW', 'British Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BCS', 'European Air Transport (DHL)', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BER', 'Air Berlin', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BMS', 'Blue Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BOX', 'AeroLogic', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BQ', 'Sky Alps', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BZ', 'Blue Bird Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CAO', 'Air China Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CCA', 'Air China', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CFG', 'Condor', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CKS', 'Kalitta Air', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CLX', 'Cargolux', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CPA', 'Cathay Pacific Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CSH', 'Shanghai Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('CY', 'Cyprus Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('D8', 'Norwegian Air International', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DHK', 'DHL Air', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DHL', 'DHL Aviation', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DHX', 'DHL Aviation', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DLH', 'Lufthansa', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DN', 'Norwegian Air Shuttle', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DY', 'Norwegian Air Shuttle', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('E5', 'Air Arabia Egypt', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EIN', 'Aer Lingus', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EJU', 'EasyJet Europe', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EK', 'Emirates', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ENT', 'Enter Air', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ETD', 'Etihad Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ETH', 'Ethiopian Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EW', 'Eurowings', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EWG', 'Eurowings', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EXS', 'Jet2.com', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EY', 'Etihad Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EZS', 'easyJet Switzerland', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('EZY', 'EasyJet', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('F3', 'Flyadeal', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FB', 'Bulgaria Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FDX', 'FedEx Express', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FIA', 'Fly One', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FIE', 'FlyOne Armenia', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FIN', 'Finnair', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FJO', 'Flexjet Operations Malta', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FR', 'Ryanair', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FZ', 'flydubai', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('G9', 'Air Arabia', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GAV', 'Global Reach Aviation', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GEC', 'Lufthansa Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GF', 'Gulf Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GTI', 'Atlas Air', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('GWI', 'Germanwings', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('HAT', 'Air Taxi', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('HBF', 'Privato (HB-FXE)', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('HY', 'Uzbekistan Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IBE', 'Iberia', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IBR', 'Ibertour Servicios Aereos', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ICV', 'Cargolux Italia', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IGT', 'Georgian Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IR', 'Iran Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ITY', 'ITA Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('J2', 'Azerbaijan Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('KAL', 'Korean Air Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('KC', 'Air Astana', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('KLM', 'KLM Royal Dutch Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('KU', 'Kuwait Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LDA', 'Lauda Europe', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LH', 'Lufthansa', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LO', 'LOT Polish Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LS', 'Jet2.com', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LTG', 'LATAM Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LWG', 'Luxwing', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LX', 'Swiss', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MAC', 'Malta Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MAL', 'Malta Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MAS', 'Privato (M-ASBA)', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MMO', 'Malta MedAir', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MON', 'Monarch Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MS', 'EgyptAir', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('MT', 'Malta Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NAX', 'Norwegian Air Shuttle', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NCR', 'National Airlines', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NIA', 'Nile Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NL', 'Amelia International', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NO', 'Neos', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NOS', 'Neos', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('NP', 'Nile Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('OK', 'Czech Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('OS', 'Austrian Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('PC', 'Pegasus Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('QNT', 'Qanot Sharq', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('QR', 'Qatar Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('QTR', 'Qatar Airways Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RAM', 'Royal Air Maroc', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RBG', 'Air Arabia Egypt', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RJ', 'Royal Jordanian', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RK', 'Ryanair UK', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RO', 'TAROM Romanian Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RUK', 'Ryanair UK', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RUN', 'ACT Airlines', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RYA', 'Ryanair', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('RYR', 'Ryanair', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SAS', 'SAS Scandinavian Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SM', 'Air Cairo', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SN', 'Brussels Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SOO', 'Southern Air', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SV', 'Saudia', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SWN', 'West Atlantic', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SWR', 'Swiss', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SWU', 'SkyAlps', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TAY', 'ASL Airlines', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TCX', 'Thomas Cook Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TDR', 'Trade Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('THY', 'Turkish Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TK', 'Turkish Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TOM', 'TUI Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TP', 'TAP Air Portugal', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TU', 'Tunisair', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TUI', 'TUI Airways', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TUS', 'ABSA Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TVS', 'Smartwings', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('TWY', 'Solairus Aviation', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('U2', 'EasyJet', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('UAE', 'Emirates SkyCargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('UNK', 'Non identificato', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('UPS', 'UPS Airlines', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('V7', 'Volotea', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VAS', 'ATRAN Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VF', 'Vueling', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VOE', 'Volotea', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VR', 'Cabo Verde Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('VY', 'Vueling', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('W4', 'Wizz Air Malta', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('W6', 'Wizz Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('WMT', 'Wizz Air Malta', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('WUK', 'Wizz Air UK', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('WY', 'Oman Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('WZZ', 'Wizz Air', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('XZ', 'SkyAlps', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('YW', 'Air Nostrum', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('ZZZ', 'Zabaykalskii Airlines', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('BOH', 'Bournemouth Air', false, false, 'manual', '2026-09-24 14:01:58.769804', '2026-09-24 20:52:04.291613') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('SRR', 'Maersk Air Cargo', true, false, 'config', '2026-09-24 13:26:38.236335', '2026-10-02 18:21:07.616391') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('DJ', 'Maersk Air Cargo', true, false, 'config', '2026-10-02 18:21:07.811156', '2026-10-02 18:21:07.811156') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('LAV', 'AlbaStar', false, true, 'config', '2026-09-24 13:26:38.236335', '2026-10-02 18:21:07.956981') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('FSF', 'Compagnia FSF', false, false, 'auto', '2026-10-02 19:20:23.67956', '2026-10-02 19:20:23.67956') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IST', 'Istanbul Airlines', false, false, 'auto', '2026-10-02 19:20:24.053725', '2026-10-02 19:20:24.053725') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('IPG', 'Compagnia IPG', false, false, 'auto', '2026-10-02 19:20:24.409921', '2026-10-02 19:20:24.409921') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('AEZ', 'Aerial Transit Company', false, false, 'auto', '2026-10-02 19:20:24.829355', '2026-10-02 19:20:24.829355') ON CONFLICT DO NOTHING;
INSERT INTO public.airlines (code, name, is_cargo, is_charter, source, created_at, updated_at) VALUES ('JU', 'Compagnia JU', false, false, 'config', '2026-09-24 13:26:38.236335', '2026-09-24 13:26:38.236335') ON CONFLICT DO NOTHING;


--
-- Data for Name: alert_messages; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('sacbo_missing', '⚠️ NESSUNA SCANSIONE DEL TABELLONE SACBO', 'La suite non trova file di scansione del tabellone voli dell''aeroporto.
Senza questi dati, il report giornaliero diurno non può essere generato.

Cosa controllare:
  1. Lo scanner diurno è attivo? (bgy_scanner_day.py)
  2. Il sito SACBO è raggiungibile?
     https://www.milanbergamoairport.it/it/voli-tempo-reale/
  3. Ci sono errori nel log di oggi?

Se il problema persiste, il report giornaliero di domani mattina
sarà incompleto o assente.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('sacbo_stale', '⚠️ SCANSIONE SACBO FERMA DA TROPPO TEMPO', 'L''ultima scansione del tabellone SACBO è più vecchia della soglia
di allarme. Questo può indicare che lo scanner diurno non sta girando
regolarmente.

Dettaglio:
  • Ultima scansione: {ultimo_file}
  • Età: {eta_ore} ore
  • Soglia configurata: {soglia_ore} ore

Lo scanner dovrebbe girare 4 volte al giorno (00:00, 06:00, 12:00, 18:00).
Se l''ultima scansione è più vecchia della soglia, probabilmente una
scansione prevista non è stata eseguita.

Cosa controllare:
  1. Lo scheduler è attivo?
  2. Ci sono errori nel log tra un orario di scansione e il successivo?
  3. Il computer era spento in uno degli orari di scansione?', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('radar_missing', '⚠️ FILE RADAR NOTTURNO MANCANTE', 'La suite non trova il file che raccoglie i rilevamenti radar della notte.
Senza questo file, il report notturno non può includere i voli rilevati
dal radar (né la stima rumore).

Dettaglio:
  • Sessione: {sessione} (iniziata ieri sera alle 23:00)
  • File atteso: {file_atteso}
  • Cartella: bgy_data/bgy_raw/

Cosa controllare:
  1. Lo scanner notturno è attivo durante la fascia 23:00-05:59?
  2. Ci sono errori nel log dell''ultima notte?
  3. Il computer è rimasto acceso durante la notte?', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('radar_stale_scanner_ok', 'ℹ️ RADAR TEMPORANEAMENTE FERMO', 'Il file radar non viene aggiornato da qualche minuto, ma lo scanner
notturno risulta attivo nei log.

Questo succede normalmente quando non ci sono aerei nell''area attorno
a BGY per un certo periodo. Non è un problema: la prossima scansione
che rileva un aereo aggiornerà il file automaticamente.

Nessuna azione richiesta.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('radar_stale', '⚠️ RADAR FERMO E SCANNER NON ATTIVO', 'Il file radar non si aggiorna da troppi minuti e lo scanner notturno
non risulta attivo. Questo indica che il processo che raccoglie i dati
radar si è fermato o è in errore.

Dettaglio:
  • File radar fermo da: {minuti_fermo} minuti
  • Ultimo aggiornamento: {ultimo_aggiornamento}
  • Scanner notturno: NON attivo

Cosa succede:
  • I voli della fascia oraria successiva non saranno rilevati dal radar
  • Il report notturno conterà solo i voli SACBO, senza radar
  • La stima del rumore non sarà calcolata

Cosa controllare:
  1. Lo scheduler è attivo? (il watchdog tenta un riavvio automatico)
  2. Ci sono errori OpenSky nel log?
  3. La connessione internet funziona?', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('opensky_429', '⚠️ OPENSKY CI STA RALLENTANDO', 'OpenSky Network ha un limite al numero di richieste al giorno. Quando
lo superiamo, il servizio risponde con il codice di errore HTTP 429
("Too Many Requests") e ci chiede di aspettare prima di fare nuove
richieste.

Nell''ultimo periodo:
  • Errori 429 negli ultimi {finestra_min} minuti: {errori}
  • Soglia di allarme configurata: {soglia}

Cosa significa questo per la suite:
  • Qualche errore 429 è normale e gestito automaticamente: la suite
    passa alle fonti di fallback (adsb.lol, adsb.fi)
  • Se gli errori sono molti e ripetuti, la copertura radar notturna
    potrebbe risultare ridotta

Cosa fare:
  1. Verifica che il radar giri SOLO di notte (23:00-05:59).
     Nella configurazione attuale è così.
  2. Se gli errori continuano, valuta di allungare l''intervallo tra
     le scansioni radar. Attualmente è {intervallo} minuti.
     Modifica: bgy_config/config_data.json → night_scan_interval_minutes
  3. Verifica che le credenziali OpenSky siano configurate in
     bgy_config/config_opensky.json (gli account registrati hanno
     10 volte più crediti di quelli anonimi).', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('scheduler_restart', '🔧 SCHEDULER RIAVVIATO AUTOMATICAMENTE', 'Il processo che gestisce le scansioni e i report automatici non era
attivo. Il watchdog lo ha riavviato per garantire la continuità del
monitoraggio.

Dettaglio:
  • Ora del riavvio: {ora_riavvio}
  • Motivo: il processo scheduler non era attivo

Cosa verificare (se succede spesso):
  1. Ci sono errori nel log subito prima del riavvio?
  2. Il computer è andato in sospensione?
  3. Ci sono stati aggiornamenti di Windows che hanno chiuso i processi?

Se il riavvio è un caso isolato, non serve fare nulla.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('scheduler_dead', '❌ SCHEDULER MORTO - INTERVENTO MANUALE RICHIESTO', 'Il processo scheduler non è attivo e il riavvio automatico è fallito.
Senza lo scheduler, non vengono eseguite scansioni automatiche né
report programmati.

Dettaglio:
  • Ora: {ora}
  • Azione tentata: riavvio automatico
  • Esito: FALLITO

Cosa fare:
  1. Verifica che il file bgy_scheduler.py esista in:
     C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5\
  2. Controlla il log di oggi per errori relativi al riavvio
  3. Avvia manualmente lo scheduler:
     cd "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
     py -3.12 bgy_scheduler.py

Se lo scheduler parte correttamente, il watchdog riprenderà a
monitorarlo automaticamente.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('scheduler_blocked', '🔧 SCHEDULER BLOCCATO E RIAVVIATO', 'Il processo scheduler risulta attivo, ma non scrive log da troppo tempo.
Questo indica che è in uno stato di blocco (probabilmente in attesa di
una risorsa o in un loop infinito). Il watchdog lo ha riavviato.

Dettaglio:
  • Log fermo da: {minuti_fermi} minuti
  • Soglia configurata: {soglia} minuti
  • Azione: riavvio forzato

Cosa verificare:
  1. Ci sono errori nel log immediatamente prima del blocco?
  2. La scansione in corso al momento del blocco è terminata?
  3. Ci sono file di lock (es. .git/index.lock) che bloccano
     altre operazioni?', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('scheduler_blocked_fail', '❌ SCHEDULER BLOCCATO - RIAVVIO FALLITO', 'Il processo scheduler risulta bloccato (log fermo da troppo tempo) e
il riavvio automatico è fallito.

Dettaglio:
  • Log fermo da: {minuti_fermi} minuti
  • Soglia configurata: {soglia} minuti
  • Azione tentata: riavvio forzato
  • Esito: FALLITO

Cosa fare:
  1. Termina manualmente eventuali scheduler attivi:
     Get-WmiObject Win32_Process -Filter "Name=''python.exe'' OR Name=''pythonw.exe''" | Where-Object {{ $_.CommandLine -like ''*bgy_scheduler*'' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
  2. Riavvia lo scheduler manualmente:
     cd "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
     py -3.12 bgy_scheduler.py

Questa notifica è critica: il monitoraggio automatico è fermo
finché non intervieni manualmente.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('github_sync_failed', '⚠️ SYNC GITHUB FALLITO', 'La sincronizzazione automatica verso GitHub non è riuscita.
Questo significa che gli ultimi dati raccolti non sono ancora
visibili sul repository pubblico.

Causa probabile:
  • Token GitHub scaduto o revocato
  • Connessione internet assente
  • Configurazione remote errata in bgy_config/config_github.json

Cosa fare:
  1. Verifica che il token in bgy_config/config_github.json sia valido
  2. Verifica che il repository sia raggiungibile da browser
  3. Controlla il log di oggi per errori git specifici

Il prossimo tentativo di sync avverrà domani mattina alle 06:30.', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('github_push_failed', '⚠️ PUSH GITHUB FALLITO', 'Il commit locale è stato creato, ma il push verso GitHub non è
riuscito. I dati sono al sicuro in locale, ma non ancora sul repository
pubblico.

Causa probabile:
  • Token GitHub scaduto o revocato
  • Conflitto con modifiche remote (qualcuno ha pushato dopo l''ultimo pull)
  • Connessione internet instabile
  • Repository remoto pieno o archiviato

Cosa fare:
  1. Verifica il token in bgy_config/config_github.json
  2. Verifica lo stato del repository su GitHub
  3. Se il problema persiste, esegui manualmente:
     cd "C:\Users\ncremaschi\Desktop\Monitoraggio BGY 2.5"
     git status
     git push origin main', '2026-09-24 13:26:40.225062') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('db_down', '🚨 BGY - Database irraggiungibile', 'Il database PostgreSQL non è raggiungibile da {down_min} minuti.
Stato servizio: {status}
Dettaglio: {db_msg}', '2026-09-29 12:41:45.707899') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('db_restarted', '✅ BGY - Database riavviato', 'Il database è stato riavviato automaticamente dopo {down_min} minuti di down.
Dettagli: {dettagli}', '2026-09-29 12:41:45.842597') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('db_down_no_admin', '❌ BGY - Database down (richiesti privilegi admin)', 'Il database è down da {down_min} minuti.
Il riavvio automatico è fallito: la suite non ha privilegi amministrativi.
Avvia la suite con ''Avvia BGY.bat'' (UAC).
Stato servizio: {status}', '2026-09-29 12:41:45.950424') ON CONFLICT DO NOTHING;
INSERT INTO public.alert_messages (key, subject, body, updated_at) VALUES ('db_down_restart_failed', '❌ BGY - Database down (riavvio fallito)', 'Il database è down da {down_min} minuti.
Tentativo di riavvio fallito: {restart_msg}
Stato servizio: {status}', '2026-09-29 12:41:46.041838') ON CONFLICT DO NOTHING;


--
-- Data for Name: assaeroporti_stats; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.assaeroporti_stats (year, passengers, movements, cargo_ton, source, updated_at) VALUES (2024, 17300000, 120000, 23000, 'manuale', '2026-09-24 13:26:40.475758') ON CONFLICT DO NOTHING;
INSERT INTO public.assaeroporti_stats (year, passengers, movements, cargo_ton, source, updated_at) VALUES (2025, 16900000, 115000, 24531, 'manuale', '2026-09-24 13:26:40.475758') ON CONFLICT DO NOTHING;


--
-- Data for Name: callsign_airline_patterns; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.callsign_airline_patterns (pattern, airline_iata, note, created_at) VALUES ('MAC', '3O', 'Malta Air opera per Air Arabia Maroc', '2026-10-03 15:38:01.913629') ON CONFLICT DO NOTHING;
INSERT INTO public.callsign_airline_patterns (pattern, airline_iata, note, created_at) VALUES ('MMO', 'MT', 'Malta MedAir', '2026-10-03 15:38:01.913629') ON CONFLICT DO NOTHING;
INSERT INTO public.callsign_airline_patterns (pattern, airline_iata, note, created_at) VALUES ('FIE', '3F', 'FlyOne Armenia', '2026-10-03 15:38:01.913629') ON CONFLICT DO NOTHING;


--
-- Data for Name: callsign_classifications; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.callsign_classifications (callsign, categoria, nome_compagnia, note, created_at, updated_at) VALUES ('IMVRK', 'Elicottero - Escluso', 'AREU Lombardia (HORUS 3)', 'Elisoccorso HEMS, base Villa Guardia. AgustaWestland AW139.', '2026-10-10 14:14:46.098822', '2026-10-10 14:14:46.098822') ON CONFLICT DO NOTHING;


--
-- Data for Name: config_settings; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.config_settings (key, value, updated_at) VALUES ('load_factor_default', '0.85', '2026-09-24 13:26:39.344724') ON CONFLICT DO NOTHING;


--
-- Data for Name: countries; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.countries (destination, country, updated_at) VALUES ('COMISO', 'DA CLASSIFICARE', '2026-09-28 06:30:01.66669') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SHARM EL-SHEIKH', 'DA CLASSIFICARE', '2026-10-07 11:38:51.315181') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KERKYRA', 'DA CLASSIFICARE', '2026-10-07 11:41:06.624188') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BREST', 'DA CLASSIFICARE', '2026-10-03 06:30:00.659454') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BOLZANO/BOZEN', 'DA CLASSIFICARE', '2026-10-07 11:40:27.124049') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TURKMENABAT', 'DA CLASSIFICARE', '2026-10-07 11:41:06.737308') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('REPUBLIC OF MOLDOVA', 'Moldova', '2026-10-06 09:33:16.854195') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ANCONA', 'DA CLASSIFICARE', '2026-10-07 11:40:27.232944') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LONDRA', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LONDON', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LONDON STANSTED', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LONDON GATWICK', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LONDON LUTON', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MANCHESTER', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BIRMINGHAM', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('EDINBURGH', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRISTOL', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BELFAST', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GLASGOW', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NEWCASTLE', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LEEDS', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LIVERPOOL', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('United Kingdom', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('UK', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('U.K.', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PARIS', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PARIGI', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BEAUVAIS', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NICE', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LYON', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TOULOUSE', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MARSEILLE', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BORDEAUX', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LOURDES', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('France', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BARCELONA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BARCELONA EL PRAT', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MADRID', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ALICANTE', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MALAGA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PALMA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PALMA DE MALLORCA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('IBIZA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MENORCA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FUERTEVENTURA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LANZAROTE', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TENERIFE', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GRAN CANARIA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SEVILLA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VALENCIA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BILBAO', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SANTIAGO', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CASTELLON DE LA PLANA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VITORIA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZARAGOZA', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ASTURIAS', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Spain', 'Spagna', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BERLIN', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BERLINO', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FRANKFURT', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MUNICH', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('COLONIA', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('COLOGNE', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DUSSELDORF', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('HAMBURG', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('STUTTGART', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NORIMBERGA', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Germany', 'Germania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('AMSTERDAM', 'Paesi Bassi', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('EINDHOVEN', 'Paesi Bassi', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Netherlands', 'Paesi Bassi', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRUXELLES', 'Belgio', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRUXELLES CHARLEROI', 'Belgio', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CHARLEROI', 'Belgio', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRUSSELS', 'Belgio', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Belgium', 'Belgio', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DUBLINO', 'Irlanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DUBLIN', 'Irlanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KNOCK', 'Irlanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CORK', 'Irlanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Ireland', 'Irlanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ROMA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MILANO', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BERGAMO', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VENICE', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VENEZIA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NAPOLI', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BARI', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CATANIA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PALERMO', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CAGLIARI', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('OLBIA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ALGHERO', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PISA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FIRENZE', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BOLOGNA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VERONA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TRIESTE', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRINDISI', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LAMEZIA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LAMEZIA TERME', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TRAPANI', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CROTONE', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FOGGIA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SALERNO', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LAMPEDUSA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PESCARA', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Italy', 'Italia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ATHENS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ATENE', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('THESSALONIKI', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CORFU', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('RHODES', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SKIATHOS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KOS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SANTORINI', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SANTORINI / THIRA', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZAKINTHOS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KARPATHOS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('HERAKLION', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CHANIA', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LEMNOS', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PREVEZA', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KALAMATA', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CEFALONIA', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Greece', 'Grecia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SOFIA', 'Bulgaria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VARNA', 'Bulgaria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Bulgaria', 'Bulgaria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BUCHAREST', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BUCAREST', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BUCHAREST OTOPENI', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CLUJ', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CLUJ-NAPOCA', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CRAIOVA', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BACAU', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ORADEA', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TIRGU MURES', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TIMISOARA', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('IASI', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SUCEAVA', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Romania', 'Romania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('WARSAW', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VARSOVIA', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VARSAVIA MODLIN', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KRAKOW', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('POZNAN', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GDANSK', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GDANSK - DANZICA', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('WROCLAW', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('WROCLAW - BRESLAVIA', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KATOWICE', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LODZ', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Poland', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PRAGUE', 'Repubblica Ceca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PRAGA', 'Repubblica Ceca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRNO', 'Repubblica Ceca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Czech Republic', 'Repubblica Ceca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Czechia', 'Repubblica Ceca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VIENNA', 'Austria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Austria', 'Austria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BUDAPEST', 'Ungheria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Hungary', 'Ungheria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ISTANBUL', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ISTANBUL S. GOKCEN', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ANTALYA', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ANKARA', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('IZMIR', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Turkey', 'Turchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SHARM EL SHEIKH', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('HURGHADA', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CAIRO', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MARSA ALAM', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ALEXANDRIA', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Egypt', 'Egitto', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MARRAKECH', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('AGADIR', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FES', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TANGIER', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CASABLANCA', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('RABAT', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BENI MELLAL', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FEZ', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Morocco', 'Marocco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TUNISI', 'Tunisia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MONASTIR', 'Tunisia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DJERBA', 'Tunisia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Tunisia', 'Tunisia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ALGERI', 'Algeria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Algeria', 'Algeria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Libya', 'Libia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('AMMAN', 'Giordania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Jordan', 'Giordania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BEIRUT', 'Libano', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Lebanon', 'Libano', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Syria', 'Siria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TEL AVIV', 'Israele', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Israel', 'Israele', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DUBAI', 'Emirati Arabi Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ABU DHABI', 'Emirati Arabi Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SHARJAH', 'Emirati Arabi Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('United Arab Emirates', 'Emirati Arabi Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('UAE', 'Emirati Arabi Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DOHA', 'Qatar', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Qatar', 'Qatar', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KUWAIT', 'Kuwait', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Kuwait', 'Kuwait', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Bahrain', 'Bahrain', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MUSCAT', 'Oman', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Oman', 'Oman', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('RIYADH', 'Arabia Saudita', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('JEDDAH', 'Arabia Saudita', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Saudi Arabia', 'Arabia Saudita', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TEHRAN', 'Iran', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Iran', 'Iran', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Iraq', 'Iraq', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BAKU', 'Azerbaijan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Azerbaijan', 'Azerbaijan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TBILISI', 'Georgia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Georgia', 'Georgia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('YEREVAN', 'Armenia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Armenia', 'Armenia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ASTANA', 'Kazakistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Kazakhstan', 'Kazakistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TASHKENT', 'Uzbekistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Uzbekistan', 'Uzbekistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Turkmenistan', 'Turkmenistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Kyrgyzstan', 'Kirghizistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Tajikistan', 'Tagikistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MOSCOW', 'Russia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MOSCA', 'Russia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ST PETERSBURG', 'Russia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Russia', 'Russia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KYIV', 'Ucraina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Ukraine', 'Ucraina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Belarus', 'Bielorussia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CHISINAU', 'Moldova', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Moldova', 'Moldova', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LISBON', 'Portogallo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LISBONA', 'Portogallo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PORTO', 'Portogallo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('FARO', 'Portogallo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Portugal', 'Portogallo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MALTA', 'Malta', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Malta', 'Malta', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PAPHOS', 'Cipro', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LARNACA', 'Cipro', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Cyprus', 'Cipro', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZURICH', 'Svizzera', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZURIGO', 'Svizzera', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GENEVA', 'Svizzera', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GINEVRA', 'Svizzera', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Switzerland', 'Svizzera', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Monaco', 'Monaco', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('COPENHAGEN', 'Danimarca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BILLUND', 'Danimarca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Denmark', 'Danimarca', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('OSLO', 'Norvegia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('OSLO TORP', 'Norvegia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Norway', 'Norvegia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('STOCKHOLM', 'Svezia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('GOTEBORG', 'Svezia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Sweden', 'Svezia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('HELSINKI', 'Finlandia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ROVANIEMI', 'Finlandia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Finland', 'Finlandia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Iceland', 'Islanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('VILNIUS', 'Lituania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Lithuania', 'Lituania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('RIGA', 'Lettonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Latvia', 'Lettonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TALLINN', 'Estonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Estonia', 'Estonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TIRANA', 'Albania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Albania', 'Albania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SKOPJE', 'Macedonia del Nord', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('North Macedonia', 'Macedonia del Nord', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BELGRADE', 'Serbia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Serbia', 'Serbia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZAGREB', 'Croazia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SPLIT', 'Croazia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DUBROVNIK', 'Croazia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ZADAR', 'Croazia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Croatia', 'Croazia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BRATISLAVA', 'Slovacchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Slovakia', 'Slovacchia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LJUBLJANA', 'Slovenia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Slovenia', 'Slovenia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('MOSTAR', 'Bosnia ed Erzegovina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Bosnia and Herzegovina', 'Bosnia ed Erzegovina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LUXEMBOURG', 'Lussemburgo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Luxembourg', 'Lussemburgo', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('United States', 'Stati Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('USA', 'Stati Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('U.S.A.', 'Stati Uniti', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Canada', 'Canada', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Mexico', 'Messico', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Brazil', 'Brasile', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Argentina', 'Argentina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Chile', 'Cile', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Peru', 'Perù', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Colombia', 'Colombia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Venezuela', 'Venezuela', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('China', 'Cina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Japan', 'Giappone', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('South Korea', 'Corea del Sud', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('India', 'India', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Thailand', 'Thailandia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Singapore', 'Singapore', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Malaysia', 'Malaysia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Indonesia', 'Indonesia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Australia', 'Australia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('New Zealand', 'Nuova Zelanda', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('South Africa', 'Sudafrica', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Kenya', 'Kenya', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Ethiopia', 'Etiopia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Nigeria', 'Nigeria', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Ghana', 'Ghana', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Senegal', 'Senegal', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Cape Verde', 'Capo Verde', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Mauritius', 'Mauritius', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Seychelles', 'Seychelles', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Maldives', 'Maldive', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Sri Lanka', 'Sri Lanka', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Nepal', 'Nepal', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Pakistan', 'Pakistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Bangladesh', 'Bangladesh', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('Afghanistan', 'Afghanistan', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KAUNAS', 'Lituania', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('TRIPOLI', 'Libia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('CAMBODIA', 'Cambogia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('REPUBLIC OF KOREA', 'Corea del Sud', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('LUBLIN', 'Polonia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('N/D', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BIARRITZ - BAYONA', 'Francia', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SARAJEVO', 'Bosnia ed Erzegovina', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NANTES', 'FRANCIA', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('NOTTINGHAM EAST MIDLANDS', 'Regno Unito', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BOAVISTA/SAL - CABOVERDE', 'Capo Verde', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('STAVANGER', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('BERGEN', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('DAKAR', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('PANTELLERIA', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('RIMINI/MARSA MATRUH', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('KINGDOM OF THE NETHERLANDS', 'DA CLASSIFICARE', '2026-09-24 13:26:38.48457') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('SAL ISLAND', 'DA CLASSIFICARE', '2026-10-07 11:23:16.702029') ON CONFLICT DO NOTHING;
INSERT INTO public.countries (destination, country, updated_at) VALUES ('ROME', 'DA CLASSIFICARE', '2026-10-07 11:40:48.847061') ON CONFLICT DO NOTHING;


--
-- Data for Name: iata_to_icao; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.iata_to_icao (iata, icao) VALUES ('FR', 'RYR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('W4', 'WMT') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('W6', 'WZZ') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('U2', 'EJU') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('VY', 'VLG') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('AZ', 'ITY') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('LS', 'EXS') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('PC', 'PGT') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('TK', 'THY') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('FZ', 'FDB') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('EK', 'UAE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('BA', 'BAW') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('AF', 'AFR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('KL', 'KLM') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('LH', 'DLH') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('LX', 'SWR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('OS', 'AUA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('SN', 'BEL') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('TP', 'TAP') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('IB', 'IBE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('A3', 'AEE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('LO', 'LOT') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('OK', 'CSA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('RO', 'ROT') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('FB', 'LZB') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('CY', 'CYP') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('RJ', 'RJA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('MS', 'MSR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('TU', 'TAR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('AH', 'DAH') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('SV', 'SVA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('QR', 'QTR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('EY', 'ETD') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('GF', 'GFA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('KU', 'KAC') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('WY', 'OMA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('IR', 'IRA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('G9', 'ABY') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('SM', 'MSC') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('J2', 'AHY') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('KC', 'KZR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('HY', 'UZB') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('YW', 'ANE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('F3', 'FAD') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('V7', 'VOE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('BQ', 'SWU') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('E5', 'RBG') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('C3', 'TDR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('BZ', 'BBR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('DN', 'DTR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('MT', 'MLO') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('NP', 'NIA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('RK', 'RUK') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('EW', 'EWG') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('EN', 'DLA') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('DY', 'NAX') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('NO', 'NOS') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('VF', 'TKJ') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('XZ', 'AEZ') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('D8', 'NSZ') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('DJ', 'SRR') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('AP', 'LAV') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('3O', 'MAC') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('A9', 'TGZ') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('RM', 'NGT') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('BN', 'LWG') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('3F', 'FIE') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('H4', 'HYS') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('H7', 'HYS') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('UJ', 'LMU') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('VR', 'TCV') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('ZQ', 'GER') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('H6', 'BUC') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('MV', 'MMD') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('SE', 'SVI') ON CONFLICT DO NOTHING;
INSERT INTO public.iata_to_icao (iata, icao) VALUES ('GH', 'IGT') ON CONFLICT DO NOTHING;


--
-- Data for Name: load_factors; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.load_factors (code, load_factor) VALUES ('FR', 0.950) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('RYR', 0.950) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('W6', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('WZZ', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('W4', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('WMT', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('U2', 0.900) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('EJU', 0.900) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('EZY', 0.900) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('LS', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('EXS', 0.880) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('BA', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('BAW', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('AF', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('AFR', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('LH', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('DLH', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('LX', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('SWR', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('OS', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('A3', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('TK', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('PC', 0.850) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('VF', 0.850) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('VY', 0.850) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('IB', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('IBE', 0.820) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('TP', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('AZ', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('AZA', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('ITY', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('KL', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('KLM', 0.800) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('SK', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('SAS', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('AY', 0.780) ON CONFLICT DO NOTHING;
INSERT INTO public.load_factors (code, load_factor) VALUES ('LO', 0.800) ON CONFLICT DO NOTHING;


--
-- Data for Name: noise_curves; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (163, 'Boeing 737-800', 'atterraggio', 200, 95.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (164, 'Boeing 737-800', 'atterraggio', 500, 90.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (165, 'Boeing 737-800', 'atterraggio', 1000, 85.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (166, 'Boeing 737-800', 'atterraggio', 2000, 78.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (167, 'Boeing 737-800', 'atterraggio', 5000, 68.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (168, 'Boeing 737-800', 'atterraggio', 10000, 58.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (169, 'Boeing 737-800', 'decollo', 200, 98.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (170, 'Boeing 737-800', 'decollo', 500, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (171, 'Boeing 737-800', 'decollo', 1000, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (172, 'Boeing 737-800', 'decollo', 2000, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (173, 'Boeing 737-800', 'decollo', 5000, 72.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (174, 'Boeing 737-800', 'decollo', 10000, 62.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (175, 'Boeing 737-800', 'sorvolo', 200, 92.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (176, 'Boeing 737-800', 'sorvolo', 500, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (177, 'Boeing 737-800', 'sorvolo', 1000, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (178, 'Boeing 737-800', 'sorvolo', 2000, 77.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (179, 'Boeing 737-800', 'sorvolo', 5000, 67.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (180, 'Boeing 737-800', 'sorvolo', 10000, 57.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (181, 'Airbus A320-200', 'atterraggio', 200, 94.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (182, 'Airbus A320-200', 'atterraggio', 500, 89.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (183, 'Airbus A320-200', 'atterraggio', 1000, 84.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (184, 'Airbus A320-200', 'atterraggio', 2000, 77.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (185, 'Airbus A320-200', 'atterraggio', 5000, 67.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (186, 'Airbus A320-200', 'atterraggio', 10000, 57.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (187, 'Airbus A320-200', 'decollo', 200, 97.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (188, 'Airbus A320-200', 'decollo', 500, 92.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (189, 'Airbus A320-200', 'decollo', 1000, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (190, 'Airbus A320-200', 'decollo', 2000, 81.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (191, 'Airbus A320-200', 'decollo', 5000, 71.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (192, 'Airbus A320-200', 'decollo', 10000, 61.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (193, 'Airbus A320-200', 'sorvolo', 200, 91.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (194, 'Airbus A320-200', 'sorvolo', 500, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (195, 'Airbus A320-200', 'sorvolo', 1000, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (196, 'Airbus A320-200', 'sorvolo', 2000, 76.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (197, 'Airbus A320-200', 'sorvolo', 5000, 66.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (198, 'Airbus A320-200', 'sorvolo', 10000, 56.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (199, 'Airbus A319-100', 'atterraggio', 200, 92.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (200, 'Airbus A319-100', 'atterraggio', 500, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (201, 'Airbus A319-100', 'atterraggio', 1000, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (202, 'Airbus A319-100', 'atterraggio', 2000, 75.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (203, 'Airbus A319-100', 'atterraggio', 5000, 65.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (204, 'Airbus A319-100', 'atterraggio', 10000, 55.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (205, 'Airbus A319-100', 'decollo', 200, 95.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (206, 'Airbus A319-100', 'decollo', 500, 90.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (207, 'Airbus A319-100', 'decollo', 1000, 85.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (208, 'Airbus A319-100', 'decollo', 2000, 79.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (209, 'Airbus A319-100', 'decollo', 5000, 69.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (210, 'Airbus A319-100', 'decollo', 10000, 59.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (211, 'Airbus A319-100', 'sorvolo', 200, 89.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (212, 'Airbus A319-100', 'sorvolo', 500, 85.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (213, 'Airbus A319-100', 'sorvolo', 1000, 80.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (214, 'Airbus A319-100', 'sorvolo', 2000, 74.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (215, 'Airbus A319-100', 'sorvolo', 5000, 64.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (216, 'Airbus A319-100', 'sorvolo', 10000, 54.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (217, 'Embraer E190', 'atterraggio', 200, 90.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (218, 'Embraer E190', 'atterraggio', 500, 85.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (219, 'Embraer E190', 'atterraggio', 1000, 80.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (220, 'Embraer E190', 'atterraggio', 2000, 73.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (221, 'Embraer E190', 'atterraggio', 5000, 63.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (222, 'Embraer E190', 'atterraggio', 10000, 53.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (223, 'Embraer E190', 'decollo', 200, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (224, 'Embraer E190', 'decollo', 500, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (225, 'Embraer E190', 'decollo', 1000, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (226, 'Embraer E190', 'decollo', 2000, 77.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (227, 'Embraer E190', 'decollo', 5000, 67.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (228, 'Embraer E190', 'decollo', 10000, 57.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (229, 'Embraer E190', 'sorvolo', 200, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (230, 'Embraer E190', 'sorvolo', 500, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (231, 'Embraer E190', 'sorvolo', 1000, 78.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (232, 'Embraer E190', 'sorvolo', 2000, 72.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (233, 'Embraer E190', 'sorvolo', 5000, 62.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (234, 'Embraer E190', 'sorvolo', 10000, 52.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (235, 'ATR 72-600', 'atterraggio', 200, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (236, 'ATR 72-600', 'atterraggio', 500, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (237, 'ATR 72-600', 'atterraggio', 1000, 78.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (238, 'ATR 72-600', 'atterraggio', 2000, 71.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (239, 'ATR 72-600', 'atterraggio', 5000, 61.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (240, 'ATR 72-600', 'atterraggio', 10000, 51.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (241, 'ATR 72-600', 'decollo', 200, 91.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (242, 'ATR 72-600', 'decollo', 500, 86.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (243, 'ATR 72-600', 'decollo', 1000, 81.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (244, 'ATR 72-600', 'decollo', 2000, 75.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (245, 'ATR 72-600', 'decollo', 5000, 65.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (246, 'ATR 72-600', 'decollo', 10000, 55.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (247, 'ATR 72-600', 'sorvolo', 200, 85.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (248, 'ATR 72-600', 'sorvolo', 500, 81.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (249, 'ATR 72-600', 'sorvolo', 1000, 76.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (250, 'ATR 72-600', 'sorvolo', 2000, 70.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (251, 'ATR 72-600', 'sorvolo', 5000, 60.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (252, 'ATR 72-600', 'sorvolo', 10000, 50.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (253, 'Boeing 777-300ER', 'atterraggio', 200, 100.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (254, 'Boeing 777-300ER', 'atterraggio', 500, 95.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (255, 'Boeing 777-300ER', 'atterraggio', 1000, 90.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (256, 'Boeing 777-300ER', 'atterraggio', 2000, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (257, 'Boeing 777-300ER', 'atterraggio', 5000, 73.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (258, 'Boeing 777-300ER', 'atterraggio', 10000, 63.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (259, 'Boeing 777-300ER', 'decollo', 200, 103.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (260, 'Boeing 777-300ER', 'decollo', 500, 98.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (261, 'Boeing 777-300ER', 'decollo', 1000, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (262, 'Boeing 777-300ER', 'decollo', 2000, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (263, 'Boeing 777-300ER', 'decollo', 5000, 77.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (264, 'Boeing 777-300ER', 'decollo', 10000, 67.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (265, 'Boeing 777-300ER', 'sorvolo', 200, 97.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (266, 'Boeing 777-300ER', 'sorvolo', 500, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (267, 'Boeing 777-300ER', 'sorvolo', 1000, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (268, 'Boeing 777-300ER', 'sorvolo', 2000, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (269, 'Boeing 777-300ER', 'sorvolo', 5000, 72.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (270, 'Boeing 777-300ER', 'sorvolo', 10000, 62.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (271, 'Dash 8-400', 'atterraggio', 200, 89.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (272, 'Dash 8-400', 'atterraggio', 500, 84.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (273, 'Dash 8-400', 'atterraggio', 1000, 79.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (274, 'Dash 8-400', 'atterraggio', 2000, 72.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (275, 'Dash 8-400', 'atterraggio', 5000, 62.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (276, 'Dash 8-400', 'atterraggio', 10000, 52.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (277, 'Dash 8-400', 'decollo', 200, 92.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (278, 'Dash 8-400', 'decollo', 500, 87.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (279, 'Dash 8-400', 'decollo', 1000, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (280, 'Dash 8-400', 'decollo', 2000, 76.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (281, 'Dash 8-400', 'decollo', 5000, 66.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (282, 'Dash 8-400', 'decollo', 10000, 56.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (283, 'Dash 8-400', 'sorvolo', 200, 86.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (284, 'Dash 8-400', 'sorvolo', 500, 82.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (285, 'Dash 8-400', 'sorvolo', 1000, 77.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (286, 'Dash 8-400', 'sorvolo', 2000, 71.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (287, 'Dash 8-400', 'sorvolo', 5000, 61.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (288, 'Dash 8-400', 'sorvolo', 10000, 51.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (289, 'Airbus A321-200', 'atterraggio', 200, 96.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (290, 'Airbus A321-200', 'atterraggio', 500, 91.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (291, 'Airbus A321-200', 'atterraggio', 1000, 86.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (292, 'Airbus A321-200', 'atterraggio', 2000, 79.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (293, 'Airbus A321-200', 'atterraggio', 5000, 69.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (294, 'Airbus A321-200', 'atterraggio', 10000, 59.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (295, 'Airbus A321-200', 'decollo', 200, 99.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (296, 'Airbus A321-200', 'decollo', 500, 94.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (297, 'Airbus A321-200', 'decollo', 1000, 89.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (298, 'Airbus A321-200', 'decollo', 2000, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (299, 'Airbus A321-200', 'decollo', 5000, 73.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (300, 'Airbus A321-200', 'decollo', 10000, 63.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (301, 'Airbus A321-200', 'sorvolo', 200, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (302, 'Airbus A321-200', 'sorvolo', 500, 89.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (303, 'Airbus A321-200', 'sorvolo', 1000, 84.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (304, 'Airbus A321-200', 'sorvolo', 2000, 78.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (305, 'Airbus A321-200', 'sorvolo', 5000, 68.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (306, 'Airbus A321-200', 'sorvolo', 10000, 58.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (307, '_default', 'atterraggio', 200, 93.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (308, '_default', 'atterraggio', 500, 88.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (309, '_default', 'atterraggio', 1000, 83.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (310, '_default', 'atterraggio', 2000, 76.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (311, '_default', 'atterraggio', 5000, 66.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (312, '_default', 'atterraggio', 10000, 56.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (313, '_default', 'decollo', 200, 96.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (314, '_default', 'decollo', 500, 91.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (315, '_default', 'decollo', 1000, 86.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (316, '_default', 'decollo', 2000, 80.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (317, '_default', 'decollo', 5000, 70.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (318, '_default', 'decollo', 10000, 60.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (319, '_default', 'sorvolo', 200, 90.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (320, '_default', 'sorvolo', 500, 86.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (321, '_default', 'sorvolo', 1000, 81.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (322, '_default', 'sorvolo', 2000, 75.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (323, '_default', 'sorvolo', 5000, 65.0) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_curves (id, aircraft_model, phase, distance_m, noise_db) VALUES (324, '_default', 'sorvolo', 10000, 55.0) ON CONFLICT DO NOTHING;


--
-- Data for Name: noise_stations; Type: TABLE DATA; Schema: public; Owner: bgy_user
--

INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Azzano S. Paolo - via XXIV Maggio', 45.643600, 9.678200) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Bagnatica - via delle Groane', 45.666500, 9.793000) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Bergamo - via Colognola ai Colli', 45.689000, 9.657000) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Bergamo - via Linneo', 45.695500, 9.672000) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Bergamo - via Quasimodo', 45.680000, 9.685000) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Grassobbio - via Lombardia', 45.655000, 9.710000) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Orio al Serio - largo XXV Aprile', 45.673900, 9.704200) ON CONFLICT DO NOTHING;
INSERT INTO public.noise_stations (name, lat, lon) VALUES ('Seriate (Cassinone) - via Basse', 45.678000, 9.732000) ON CONFLICT DO NOTHING;


--
-- Name: noise_curves_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bgy_user
--

SELECT pg_catalog.setval('public.noise_curves_id_seq', 324, true);


--
-- PostgreSQL database dump complete
--

\unrestrict HgvaHLgl7G7KuSTii7lQBZ8jHnfVKEqOLo4zSBsJXTJRoSr1tixMbvwwdLy6mzd

