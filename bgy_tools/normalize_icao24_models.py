"""
bgy_tools/normalize_icao24_models.py
Normalizza i modelli in aircraft_icao24_db verso i canonici di aircraft_models.

Uso:
    py -3.12 -m bgy_tools.normalize_icao24_models            # dry-run
    py -3.12 -m bgy_tools.normalize_icao24_models --apply    # applica

Rollback: UPDATE aircraft_icao24_db SET model = model_raw WHERE model_raw IS NOT NULL;
"""
import os
import re
import sys

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db

RULES = [
    # === MICTRONICS (formati con trattino tra A e numero, senza sottotipo) ===
    (r'^AIRBUS A-?220', 'Airbus A220-300'),
    (r'^AIRBUS A-?319', 'Airbus A319-100'),
    (r'^AIRBUS A-?320neo', 'Airbus A320neo'),
    (r'^AIRBUS A-?320', 'Airbus A320-200'),
    (r'^AIRBUS A-?321neo', 'Airbus A321neo'),
    (r'^AIRBUS A-?321', 'Airbus A321-200'),
    (r'^AIRBUS A-?330-?200', 'Airbus A330-200'),
    (r'^AIRBUS A-?330', 'Airbus A330-300'),
    (r'^AIRBUS A-?350-?1000', 'Airbus A350-1000'),
    (r'^AIRBUS A-?350', 'Airbus A350-900'),
    (r'^AIRBUS A-?380', 'Airbus A380-800'),
    (r'\bA220[- ]?300\b|\bCS300\b|BD-500-1A11|A220-330|C Series 300|Bombardier C Series 300|Airbus A220-300', 'Airbus A220-300'),
    (r'\bCS100\b|BD-500-1A10|C Series 100', 'Airbus A220-300'),
    (r'A300.*F\b|A300F|A300 B4-622|A300B4-622R|A300 F4-622RF|A300F4-622R|A300 B4-622RF', 'Airbus A300-600F'),
    (r'\bA319[- ]?\d{3}|AIRBUS A319|Airbus A319|ACJ319|A319[- ]?1\d{2}|Airbus A319-100', 'Airbus A319-100'),
    (r'\bA320[- ]?(25[01]N|27[01]N)|A-320neo|A320 ?Neo|320-25[01]N|320-27[01]N|A320-2\d{2}N|Airbus A320-251N|AIRBUS A320-251N|Airbus A320-271N|Airbus 320-251N|Airbus 320-271N|A320-251N|A320-271N|A320neo', 'Airbus A320neo'),
    (r'\bA320[- ]?\d{3}|AIRBUS A320|Airbus A320|ACJ320|^320[- ]\d{3}|^A320$|Airbus 320-214|A320-214|A320-232|A320-216|A320-211|A320-231|A320 214|A320 214SL|A320 232|A320 232SL|A320 216|A320 216SL|A320 211|A320 231|A320 251NSL|A320 271NSL|A320 251N|A320 271N|AIRBUS A320-214|AIRBUS A320-232|A320-200|Airbus A320-200', 'Airbus A320-200'),
    (r'\bA321[- ]?(2\d{2}N[X]?|3\d{2}NX)|A-321neo|A321 ?Neo|321-2\d{2}NX|A321-271NX|A321-251NX|A321 251N|A321 271NX|A321 271NXSL|Airbus A321-271NX|Airbus 321-271NX|321-251NX|A321-253NX|A321-272NX|A321neo', 'Airbus A321neo'),
    (r'\bA321[- ]?\d{3}|AIRBUS A321|Airbus A321|^A321$|A321 231|A321 231SL|A321-231|A321 131|A321-131|A321 211|A321-211|A321-212|A321 212|A321 213|A321-213|A321 111|A321-111|Airbus A321 231SL|Airbus A321 231|Airbus A321 131|A321-231SL|A321-200|Airbus A321-200', 'Airbus A321-200'),
    (r'A330[- ]?9\d{2}|A330-941|A330 941', 'Airbus A330-900neo'),
    (r'A330[- ]?2\d{2}|A330-2\d{2}|A330 203|A330 223|A330 243|A330-223|A330-243|A330-243F|A330-223F|A330 243F', 'Airbus A330-200'),
    (r'A330[- ]?3\d{2}|Airbus A330|A330-343|A330 343|A330-743L|Beluga|A330 303|A330 343E|A330 343X|A330-343X|A330-343(P2F)|A330-343E|A330-343E(F)|Airbus A330-343E|Airbus A330 343E|Airbus A330 303|A330-300|Airbus A330-300', 'Airbus A330-300'),
    (r'A350[- ]?10\d{2}', 'Airbus A350-1000'),
    (r'A350[- ]?9\d{2}|Airbus A350|A350-941|A350 941|Airbus A350-941|Airbus A350 941|A350-900|Airbus A350-900', 'Airbus A350-900'),
    (r'A380[- ]?\d{3}|Airbus A380|A380 861|A380-842|A380 842|Airbus A380 861|A380-800|Airbus A380-800', 'Airbus A380-800'),
    (r'737[- ]?MAX[- ]?8|737-8-200 MAX|737-8 MAX|B38M|737MAX|737 8 MAX|737-8 2000|Boeing 737 MAX 8|BOEING 737 MAX 8|Boeing 737 MAX 8-200', 'Boeing 737 MAX 8-200'),
    (r'737.*(SF|BCF)\b|737-4\d{2}(SF)?|737-43QSF|737-4Y0SF|737-46JSF|737-448SF|737-86Q.*F|737-800F|737-8AS.*(BCF)', 'Boeing 737-800F'),
    (r'737[- ]?8[0-9A-Z]{2}|737NG.*|Boeing 737-8|BOEING 737-8|737-8AS|737-8JP|737-8K5|737-8U3|737-8MG|737-8HX|737-8HC|737-86Q|737-86J|737-89P|737-8AL|737-8B6|737-8KN|737-800|B737-800|737-809|BOEING 737-800|Boeing 737-800|737NG 800|737NG 7ZX|737-8AS(WL)|737-8AS (W)|737-8JP (W)|737-8KN (W)|737-8MG(WL)|737-8U3 (W)|Boeing 737-8JP (W)|Boeing 737-8AS|Boeing 737-8AS (W)|Boeing 737-8K5|Boeing 737-8B6|Boeing 737-8JP|737-800WL|738-8AS|737-8$|737-800', 'Boeing 737-800'),
    (r'737[- ]?4\d{2}|737-43Q|737-4Y0|737-46J|737-490|737-4K5|737-436|737-448|737-4R7|737-4J6|737 4K5|737 436', 'Boeing 737-400'),
    (r'737[- ]?7\d{2}|737-700|Boeing 737-700|737NG 7ZX', 'Boeing 737-700'),
    (r'747[- ]?8\d{2}|747-8B5|B747-8|747 8KZ|747 830|Boeing 747-8|747-8KZF|747 8B5F|747-8B5F|747 8KZF', 'Boeing 747-8F'),
    (r'747[- ]?[4-8]\d{2}|Boeing 747|747-412|747 467|747-4R7|747 4J6|747-4R7F|747-4J6|747-48E|747-467ER(F)|747-48EF|747-48E(F)|747-48E(BDSF)|747 4R7F|747 467ERF|747 48EF|747 48EFSCD|747 83QF|747-83QF|Boeing 747-48EF|Boeing 747-867F|Boeing 747-4R7F|Boeing 747-48EFSCD|Boeing 747 48EFSCD|Boeing 747 83QF|Boeing 747-48E(F)|Boeing 747-467ER(F)|Boeing 747-48E(BDSF)|747-4R7(F)', 'Boeing 747-400'),
    (r'757[- ]?\d{3}|Boeing 757|BOEING 757|757 2|757-223PCF|757-23NPCF/W|757 208/W|757-2Q8|Boeing 757-200(F)|BOEING 757-236', 'Boeing 757-200'),
    (r'767[- ]?4\d{2}|767-424ER|767-432ER', 'Boeing 767-400'),
    (r'767[- ]?[23]\d{2}.*F\b|767-3S2F|767-332|767-322|767-346|767-304|767-381|767-300F|Boeing 767-300F|Boeing 767-300ER SF', 'Boeing 767-300F'),
    (r'767[- ]?[23]\d{2}|Boeing 767|767-332|767-322|767-346|767-304|767-381|767-3S2|Boeing 767-300|Boeing 767', 'Boeing 767-300'),
    (r'777[- ]?[23]\d{2}.*F\b|777F|777-F|Boeing 777-F|777 FB5|777 FDZ|777 FFX|777 FZN|777FHT|777-FS2|777 F|Boeing 777-FB5|Boeing 777-F28|Boeing 777-FDZ', 'Boeing 777F'),
    (r'777[- ]?3\d{2}|777-300|777 3|777 300|Boeing 777-3|B777-300|777-31H|777-31H(ER)|777 31HER|777-3DZ(ER)|777-3F2(ER)|777-3B5(ER)|777 3B5ER|777-3DZER|777 3DZER|777-367(ER)|777 367ER|777-328(ER)|777 328ER|777-35EER|777 35EER|777-300(ER)|777 300ER|Boeing 777-300(ER)|Boeing 777-300ER|Boeing 777-31H(ER)|Boeing 777-3F2(ER)|Boeing 777-3FX(ER)|Boeing 777-3B5(ER)|Boeing 777-31HER|B777-300ER|777-337ER|777 337ER|777 3F2ER|777 3FXER|777 3ALER|777 32WER', 'Boeing 777-300ER'),
    (r'777[- ]?2\d{2}|777-2|777 2|777-224|777 224|777-222|777 222|777 258ER|777 228ER|777-258ER|777-228ER', 'Boeing 777-200'),
    (r'787[- ]?10|787 10|787-10|Boeing 787-10|B787-10', 'Boeing 787-10'),
    (r'787[- ]?9|787 9|Boeing 787-9|B787-9|BOEING 787-9|787-9 Dreamliner|B787-9 Dreamliner', 'Boeing 787-9'),
    (r'787[- ]?8|787 8|Boeing 787-8|B787-8|787-8 (Boeing)', 'Boeing 787-8'),
    (r'EMB[- ]?195|E195|ERJ[- ]?195|E195LR|E195AR|Embraer E195AR|ERJ-195AR', 'Embraer E195'),
    (r'EMB[- ]?190|E190|ERJ[- ]?190|Embraer 190|Embraer ERJ-190|E190STD|E190-E2|Embraer 190STD|ERJ-190STD|EMB-190 AR|EMB-190 LR|EMB-190 STD|EMB-190 100|ERJ 190-100|ERJ 190-100 LR|ERJ 190-100 ECJ|ERJ 190-100 SR', 'Embraer ERJ-190'),
    (r'EMB[- ]?175|E175|ERJ[- ]?175|EMB-175 LR|EMB-175 SD', 'Embraer E175'),
    (r'EMB[- ]?170|E170|ERJ[- ]?170|EMB-170 STD', 'Embraer E170'),
    (r'ERJ[- ]?145|ERJ 145|ERJ-145 LU', 'Embraer ERJ-145'),
    (r'EMB[- ]?135|Legacy (600|650)|EMB-135BJ Legacy 600|EMB-135BJ Legacy 650|Legacy 600|Legacy 650|Legacy 500', 'Embraer Legacy 600/650'),
    (r'Phenom 300|EMB[- ]?505|EMB-505 Phenom 300|Phenom 300E', 'Embraer Phenom 300'),
    (r'Phenom 100', 'Embraer Phenom 100'),
    (r'ATR[- ]?42|ATR 42-500|ATR-42-500', 'ATR 42-500'),
    (r'ATR[- ]?72|ATR 72-600|ATR-72-600', 'ATR 72-600'),
    (r'DHC[- ]?8|Dash 8|Q400|DHC-8 402|DHC-8 402 NG|DHC-8-400|De Havilland Canada Dash 8 Q400|De Havilland Canada Dash 8-400', 'De Havilland Canada Dash 8-400'),
    (r'Saab 340|SAAB Fairchild 340|340 ?A\b|340A|SAAB Fairchild 340 A', 'Saab 340'),
    (r'Fokker F100|Fokker 100', 'Fokker 100'),
    (r'Challenger 300|Challenger 350|BD-100-1A10|BD-100-1A10 Challenger 350|Bombardier Challenger 300|Bombardier Challenger 350', 'Bombardier Challenger 300'),
    (r'Challenger 600|Challenger 601|Challenger 604|Challenger 605|Challenger 850|CL-600|Canadair Challenger|BD-700|Global (5000|6000|7500|Express)|CL-600-2B16|CL-600-2B19|CL-600-2D24|Global Express XRS|Global 5000|Global 6000|Global 7500|BD-700-2A12|BD-700-1A10|BD-700-2A12 Global 7500|BD-700-1A10 (Bombardier)|Bombardier Global 5000|Bombardier Global 6000|Bombardier Global Express XRS|Bombardier Challenger 604|Bombardier Challenger 605|Bombardier Challenger 850|Bombardier Challenger 600|Bombardier CRJ 1000 NG|CRJ 1000 NG|CRJ-1000|CL-600-2D24 CRJ-900|CL-600-2B19 CRJ-200|CL-600-2B16(CL-604)|CL-600-2B16 (604 Variant)|Canadair Challenger 601', 'Bombardier Challenger 600'),
    (r'Citation Mustang|510 Citation|Cessna 510|Cessna Citation Mustang', 'Cessna Citation Mustang'),
    (r'Citation XLS|560XL|Citation Excel|Citation Bravo|Citation Encore|560XL Citation XLS|560XL Citation XLS+|Cessna Citation XLS|Cessna Citation XLS+|550|560|Citation Encore', 'Cessna Citation XLS+'),
    (r'Citation CJ1|Citation CJ2|Citation CJ3|Citation M2|Cessna Citation CJ|Citation CJ1+|Citation CJ2+|Citation M2|525|525A|Cessna Citation CJ1|Cessna Citation CJ2|Cessna Citation CJ2+|Cessna Citation CJ3', 'Cessna Citation CJ2+'),
    (r'Citation|525|550|560|680|680A|Cessna Citation|Cessna Citation VII|Cessna Citation VI|Citation III|Citation X|Citation Sovereign|Citation Sovereign+|Citation Latitude|680 Citation Latitude|680A Citation Latitude', 'Cessna Citation (generico)'),
    (r'Falcon 7X|Falcon 8X|Dassault Falcon 7X|FALCON 7X', 'Dassault Falcon 7X/8X'),
    (r'Falcon 2000|Falcon 2000LX|Falcon 2000LX S|Dassault Falcon 2000LX|Dassault Falcon 2000LX S|FALCON 2000', 'Dassault Falcon 2000'),
    (r'Falcon 900|Mystere Falcon 900|Dassault Falcon 900EX|Dassault Falcon 900LX|Dassault Falcon 900EX EASy|MYSTERE FALCON 900|FALCON 900EX', 'Dassault Falcon 900'),
    (r'Falcon 50', 'Dassault Falcon 50'),
    (r'GVI|G650|Gulfstream.*G650|G650|GVI (G650ER)|Gulfstream Aerospace G650 ER', 'Gulfstream G650'),
    (r'GV-SP|G550|G500|G-V$|Gulfstream.*G550|GV-SP (G550)|GV-SP (G500)|G-V|Gulfstream Aerospace G550', 'Gulfstream G550'),
    (r'GIV-X|G350|Gulfstream IV|GIV-X (G350)', 'Gulfstream IV'),
    (r'G280|Gulfstream.*G280|G200|G100|1126 Galaxy|1125 Astra|G280|G200|G100|Gulfstream Aerospace G200|Gulfstream Aerospace G100|Gulfstream Aerospace G280|1125 Astra SPX|1126 Galaxy', 'Gulfstream G280'),
    (r'Learjet 40|Learjet 45|Learjet 60|Learjet 35|Learjet 60 XR|Learjet 35 A', 'Learjet 45'),
    (r'Hawker 400XP|400 XP|Hawker 400XP', 'Hawker 400XP'),
    (r'Hawker|125 (800|850)|Premier I|Raytheon|Hawker 900XP|125 800XP|125 850XP|Hawker Beechcraft Corp Hawker 750|Raytheon Aircraft Company Premier I|Raytheon Aircraft Company 125 800XP|Premier I|400 A|400 XP', 'Hawker 800/900XP'),
    (r'H145|H135|H125|H130|BK ?117|EC135|EC130|AW\.?169|A109|AS\.?350|Squirrel|Jet ?Ranger|AB\.?206|Robinson|R44|R66|MBB-BK 117|AW.169|EC130 B4|EC135 T2|A109C|Squirrel AS.350 B3|AB.206B Jet Ranger III|MBB-BK 117 D-2 (H145)|MBB-BK 117 D-2 Style (H145)', 'Elicottero'),
    (r'KC-135|C-130|C-21|C-26|C-40|C-295|An-12|An-124|A400M|Do 328|UC-12|UC-35|TH-13|T-6|P-180|P180|C-27|KC-135R|C-130J-30 Hercules|C-21A|C-26D Metro|C-40A|C-295 M|An-12 BP|An-12 BK|An-124 100|Do 328 110|UC-12M Huron|UC-12W Huron|UC-35A Citation|TH-13T Sioux|P-180 Avanti|P-180 Avanti II|Boeing KC-135R|Boeing KC-135T', 'Militare (generico)'),
    (r'KODIAK|Skyvan|Merlin|EuroFox|LC41|Baron|Bonanza|V35B|ROBIN|DR ?400|Mirage|Malibu|Navajo|Seneca|Arrow|Warrior|Super Cub|Stationair|T207|U206|KODIAK 100|Skyvan SL|Skyvan 3-100|Merlin IVC|LC41-550FG|Baron 58P|ROBIN DR 400/180|PA-46 350P Malibu Mirage|PA-46 310P Malibu|PA-31 350 Navajo Chieftain|PA-34 200 Seneca|PA-28R 201 Arrow III|PA-28R T-201 Arrow IV|PA-28 161 Warrior II|PA-18 150 Super Cub|U206F Stationair|T207A Turbo Skywagon|P210N|P2010 TDI', 'Aviazione generale (generico)'),
    (r'PA-28', 'Piper PA-28'),
    (r'PA-34', 'Piper PA-34'),
    (r'PA-46', 'Piper PA-46'),
    (r'PA-31', 'Piper PA-31'),
    (r'PA-18', 'Piper PA-18'),
    (r'SR22|SR20|SR22T|Cirrus SR22', 'Cirrus SR22'),
    (r'DA40|Diamond Star|Diamond Star DA40D', 'Diamond DA40'),
    (r'DA42|Twin Star|DA-42 Twin Star|Twin Star DA42', 'Diamond DA42'),
    (r'P2008|P-2008|P2008JC|Tecnam P-2008JC', 'Tecnam P2008'),
    (r'P2010|P-2010|P2010 TDI', 'Tecnam P2010'),
    (r'TBM ?(700|850|900|930|940)|TBM 700|TBM 930|TBM 700/930', 'TBM 700/930'),
    (r'M\.20|Mooney|M.20K Model 231', 'Mooney M20'),
    (r'PC-12|PC12|PC-XII|Pilatus PC|PC-12/45|PC-12/47E NG|PC-12/47E NGX|PC-XII 45|PC-XII 47|PC-XII 47E|PC-XII NG 47E|Pilatus PC-XII 45|Pilatus PC-XII 47|Pilatus PC-12', 'Pilatus PC-12'),
    (r'PC-24|Pilatus PC-24', 'Pilatus PC-24'),
    (r'King Air (200|B200)|BEECH B200|King Air 200GT|King Air B200|Beech King Air B200|BEECH B200 Super Kingair', 'Beechcraft King Air 200'),
    (r'King Air (350|B350)|BEECH B300|King Air B350|Beech King Air B350|BEECH B300 Super Kingair 350', 'Beechcraft King Air 350'),
    (r'King Air (90|C90)|King Air C90|King Air C90A|King Air C90GT', 'Beechcraft King Air 90'),
    (r'Beech 1900|Beechcraft 1900|Beech 1900 D', 'Beechcraft 1900'),
    (r'^152$|F152', 'Cessna 152'),
    (r'^172|Skyhawk|172S Skyhawk SP|172RG', 'Cessna 172'),
    (r'^182|Skylane|182K Skylane|182H Skylane', 'Cessna 182'),
    (r'^208|Caravan|208B|Cessna 208 Caravan', 'Cessna 208 Caravan'),
    (r'.*', 'Aviazione generale (generico)'),
]


def normalize(raw):
    if not raw or raw.strip() == '':
        return 'N/D'
    raw = raw.strip()
    for pattern, canonical in RULES:
        if re.search(pattern, raw, re.IGNORECASE):
            return canonical
    return 'Aviazione generale (generico)'


def main():
    apply = '--apply' in sys.argv

    ok, rows = bgy_db.execute_query(
        "SELECT COALESCE(model, '') AS model, COUNT(*) AS n "
        "FROM aircraft_icao24_db GROUP BY COALESCE(model, '') ORDER BY n DESC"
    )
    if not ok:
        print("ERRORE query:", rows)
        return

    mapping = {}
    total = 0
    for raw, n in rows:
        canon = normalize(raw)
        mapping.setdefault(canon, []).append((raw, n))
        total += n

    ok, rows_models = bgy_db.execute_query("SELECT model FROM aircraft_models")
    existing = {r[0] for r in rows_models} if ok else set()
    missing = sorted(set(mapping.keys()) - existing)

    print("\n" + "=" * 70)
    print("NORMALIZZAZIONE aircraft_icao24_db — " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 70)
    print("Modelli distinti (inclusi blank): " + str(len(rows)))
    print("Record totali: " + str(total))
    print("Modelli canonici: " + str(len(mapping)) + "\n")

    for canon in sorted(mapping, key=lambda c: -sum(n for _, n in mapping[c])):
        variants = mapping[canon]
        tot = sum(n for _, n in variants)
        print("  " + canon.ljust(42) + " " + str(tot).rjust(5) + "  (" + str(len(variants)) + " varianti)")
        if len(variants) <= 2:
            for raw, n in variants:
                print("      <- '" + raw + "' (" + str(n) + ")")

    if missing:
        print("\nERRORE: " + str(len(missing)) + " canonici non esistono in aircraft_models:")
        for m in missing:
            print("  - " + m)
        print("\nAggiungerli prima di procedere.")
        return

    if not apply:
        print("\nDRY-RUN: nessuna modifica. Rilancia con --apply per applicare.")
        return

    print("\nApplicazione in corso...")
    bgy_db.execute_query("ALTER TABLE aircraft_icao24_db ADD COLUMN IF NOT EXISTS model_raw TEXT")
    bgy_db.execute_query("BEGIN")
    updated = 0
    for raw, n in rows:
        canon = normalize(raw)
        if raw == canon:
            continue
        ok, cnt = bgy_db.execute_query(
            "UPDATE aircraft_icao24_db SET model_raw = COALESCE(model_raw, model), model = %s "
            "WHERE model = %s AND model_raw IS NULL",
            (canon, raw)
        )
        if ok:
            updated += cnt
        else:
            print("  ERRORE su '" + raw + "': " + str(cnt))
            bgy_db.execute_query("ROLLBACK")
            return
    bgy_db.execute_query("COMMIT")
    print("OK: " + str(updated) + " record aggiornati.")
    print("Rollback: UPDATE aircraft_icao24_db SET model = model_raw WHERE model_raw IS NOT NULL;")


if __name__ == '__main__':
    main()