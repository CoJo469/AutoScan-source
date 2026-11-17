
import streamlit as st
import sqlite3
import pandas as pd
import urllib.request
import os
import re
import unicodedata
from pathlib import Path

# =========================================================
# CONFIGURARE
# =========================================================

st.set_page_config(
    page_title="Auto Diagnosis Pro",
    page_icon="🔧",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DTC_DB_PATH = DATA_DIR / "dtc_codes.db"
DIAGNOSIS_DB_PATH = DATA_DIR / "diagnosis.db"
VEHICLES_DB_PATH = DATA_DIR / "vehicles.db"
ENGINES_DB_PATH = DATA_DIR / "engines.db"

VEHICLES_URL = (
    "https://github.com/vehiclesdb/vehiclesdb/"
    "releases/latest/download/catalog.sqlite"
)

ENGINES_URL = (
    "https://github.com/gor3a/vehicle-makes-models/"
    "releases/latest/download/vehicles.sqlite"
)

VEHICLES_SOURCE = "https://github.com/vehiclesdb/vehiclesdb"
ENGINES_SOURCE = "https://github.com/gor3a/vehicle-makes-models"

# =========================================================
# DESIGN
# =========================================================

st.markdown("""
<style>
.main-title {
    font-size: 32px;
    font-weight: bold;
    color: #2196F3;
}
div[data-testid="stMetric"] {
    background-color: rgba(128,128,128,0.08);
    padding: 14px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# FUNCTII GENERALE BAZE DE DATE
# =========================================================

def table_names(conn):
    rows = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
    """).fetchall()
    return {row[0] for row in rows}


def column_names(conn, table):
    if table not in table_names(conn):
        return set()

    rows = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    return {row[1] for row in rows}


def validate_sqlite(path, required_tables):

    if not path.exists():
        return False, "Fișierul nu există."

    try:
        if path.stat().st_size < 1000:
            return False, "Fișierul este prea mic."

        with open(path, "rb") as f:
            header = f.read(16)

        if header != b"SQLite format 3\x00":
            return False, "Fișierul nu este o bază SQLite."

        conn = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True
        )

        check = conn.execute(
            "PRAGMA quick_check"
        ).fetchone()

        if not check or check[0] != "ok":
            conn.close()
            return False, "Verificarea integrității a eșuat."

        available = table_names(conn)
        missing = set(required_tables) - available

        conn.close()

        if missing:
            return False, (
                "Lipsesc tabele: "
                + ", ".join(sorted(missing))
            )

        return True, "OK"

    except Exception as e:
        return False, str(e)


def download_sqlite(url, destination, required_tables):

    temp_path = destination.with_suffix(".download")

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AutoDiagnosisPro/1.0"}
        )

        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:

            with open(temp_path, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

        valid, message = validate_sqlite(
            temp_path,
            required_tables
        )

        if not valid:
            raise RuntimeError(message)

        os.replace(temp_path, destination)

        return True, "Descărcare reușită."

    except Exception as e:

        if temp_path.exists():
            temp_path.unlink()

        return False, str(e)


def prepare_database(path, url, required_tables, label):

    valid, message = validate_sqlite(
        path,
        required_tables
    )

    if valid:
        return True, f"{label}: baza locală este validă."

    success, download_message = download_sqlite(
        url,
        path,
        required_tables
    )

    if success:
        return True, f"{label}: baza a fost descărcată."

    return False, (
        f"{label}: nu s-a putut pregăti baza. "
        f"{download_message}"
    )


# Descărcarea bazelor se face numai dacă lipsesc
# sau dacă fișierele existente nu trec validarea.

vehicles_ready, vehicles_status = prepare_database(
    VEHICLES_DB_PATH,
    VEHICLES_URL,
    ["makes", "models", "availability", "popularity", "meta"],
    "VehiclesDB"
)

engines_ready, engines_status = prepare_database(
    ENGINES_DB_PATH,
    ENGINES_URL,
    ["makes", "models", "generations", "engines", "engine_specs"],
    "Baza de motorizări"
)


# =========================================================
# CONEXIUNI
# =========================================================

@st.cache_resource
def readonly_connection(path_string):

    path = Path(path_string)

    if not path.exists():
        return None

    try:
        return sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
            check_same_thread=False
        )
    except sqlite3.Error:
        return None


def get_dtc_connection():
    return readonly_connection(str(DTC_DB_PATH))


def get_vehicles_connection():

    if not vehicles_ready:
        return None

    return readonly_connection(str(VEHICLES_DB_PATH))


def get_engines_connection():

    if not engines_ready:
        return None

    return readonly_connection(str(ENGINES_DB_PATH))


# =========================================================
# BAZA LOCALA DE DIAGNOSTIC
# =========================================================

def get_diagnosis_connection():

    conn = sqlite3.connect(
        DIAGNOSIS_DB_PATH,
        check_same_thread=False
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dtc_code TEXT UNIQUE NOT NULL,
            title TEXT,
            symptoms TEXT,
            causes TEXT,
            checks TEXT,
            repair TEXT,
            notes TEXT
        )
    """)

    conn.commit()

    seed_diagnosis(conn)

    return conn


def seed_diagnosis(conn):

    records = [

        (
            "P0300",
            "Random / Multiple Cylinder Misfire Detected",
            "Motor neregulat; vibrații la ralanti; pierdere de putere; pornire dificilă.",
            "Bujii uzate; bobină defectă; injector cu probleme; presiune combustibil incorectă; pierderi de vacuum; compresie scăzută.",
            "Verifică freeze-frame; misfire counters; bujii; bobine; injectoare; presiunea combustibilului; vacuumul; compresia.",
            "Remediază cauza confirmată prin teste. Nu înlocui componente fără verificări.",
            "Codul P0300 nu identifică singur cilindrul sau piesa defectă."
        ),

        (
            "P0171",
            "System Too Lean - Bank 1",
            "Ralanti instabil; ezitări la accelerație; pierdere de putere; consum anormal.",
            "Pierderi de vacuum; furtun admisie fisurat; MAF contaminat; presiune combustibil insuficientă; injector cu debit redus; probleme PCV.",
            "Verifică STFT și LTFT; admisia; pierderile de vacuum; valorile MAF; presiunea combustibilului; injectoarele.",
            "Remediază pierderile de aer și verifică alimentarea. Înlocuiește senzorii numai după confirmarea defectului.",
            "Interpretează fuel trims în condiții de funcționare cunoscute."
        ),

        (
            "P0420",
            "Catalyst System Efficiency Below Threshold - Bank 1",
            "Martor Check Engine; uneori fără simptome evidente; posibil consum crescut sau miros neobișnuit al gazelor.",
            "Catalizator degradat; senzor O2 defect; scăpări pe evacuare; misfire repetat; amestec incorect; consum de ulei.",
            "Verifică alte coduri; misfire; fuel trims; evacuarea; semnalele senzorilor O2 și datele live.",
            "Identifică mai întâi cauza. Înlocuiește catalizatorul numai dacă testele confirmă degradarea.",
            "P0420 nu înseamnă automat catalizator defect."
        ),

        (
            "P0128",
            "Coolant Thermostat Below Regulating Temperature",
            "Motorul ajunge greu la temperatura normală; temperatura rămâne prea scăzută; încălzire slabă în habitaclu.",
            "Termostat blocat deschis; senzor ECT defect; nivel scăzut de lichid; probleme de cablaj.",
            "Verifică temperatura live; nivelul lichidului; termostatul; senzorul ECT și cablajul.",
            "Înlocuiește termostatul sau senzorul numai după verificări.",
            "Ține cont de temperatura ambientală și de timpul de încălzire."
        ),

        (
            "P0101",
            "Mass Air Flow Circuit Range / Performance",
            "Ralanti instabil; ezitare la accelerație; pierdere de putere; consum crescut.",
            "MAF contaminat sau defect; filtru de aer murdar; pierdere de aer după MAF; probleme PCV sau cablaj.",
            "Verifică admisia după MAF; filtrul; valorile live; alimentarea; masa; mufa și cablajul.",
            "Remediază pierderile de aer. Curăță MAF cu produs adecvat. Înlocuiește-l doar dacă testele confirmă defectul.",
            "Nu înlocui MAF doar pe baza codului."
        )
    ]

    conn.executemany("""
        INSERT OR IGNORE INTO diagnosis (
            dtc_code, title, symptoms, causes,
            checks, repair, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, records)

    conn.commit()


# =========================================================
# FUNCTII DTC
# =========================================================

def search_dtc(code):

    conn = get_dtc_connection()

    if conn is None:
        return pd.DataFrame()

    columns = column_names(
        conn,
        "dtc_definitions"
    )

    required = {
        "code",
        "manufacturer",
        "description"
    }

    if not required.issubset(columns):
        return pd.DataFrame()

    optional = [
        col for col in
        ["type", "locale", "is_generic"]
        if col in columns
    ]

    selected = [
        "code",
        "manufacturer",
        "description"
    ] + optional

    sql_columns = ", ".join(
        f'"{col}"' for col in selected
    )

    try:
        return pd.read_sql_query(
            f"""
            SELECT {sql_columns}
            FROM dtc_definitions
            WHERE UPPER(code) = ?
            ORDER BY manufacturer
            """,
            conn,
            params=(code.strip().upper(),)
        )

    except Exception:
        return pd.DataFrame()


def search_dtc_text(term, manufacturer=None):

    conn = get_dtc_connection()

    if conn is None:
        return pd.DataFrame()

    columns = column_names(
        conn,
        "dtc_definitions"
    )

    required = {
        "code",
        "manufacturer",
        "description"
    }

    if not required.issubset(columns):
        return pd.DataFrame()

    optional = [
        col for col in
        ["type", "locale", "is_generic"]
        if col in columns
    ]

    selected = [
        "code",
        "manufacturer",
        "description"
    ] + optional

    sql_columns = ", ".join(
        f'"{col}"' for col in selected
    )

    sql = f"""
        SELECT {sql_columns}
        FROM dtc_definitions
        WHERE (
            UPPER(code) LIKE ?
            OR LOWER(description) LIKE ?
            OR LOWER(manufacturer) LIKE ?
        )
    """

    value = term.strip()

    params = [
        f"%{value.upper()}%",
        f"%{value.lower()}%",
        f"%{value.lower()}%"
    ]

    if manufacturer and manufacturer != "Toți producătorii":
        sql += " AND manufacturer = ?"
        params.append(manufacturer)

    sql += " ORDER BY code"

    try:
        return pd.read_sql_query(
            sql,
            conn,
            params=params
        )
    except Exception:
        return pd.DataFrame()


def get_diagnosis(code):

    conn = get_diagnosis_connection()

    row = conn.execute("""
        SELECT
            dtc_code, title, symptoms, causes,
            checks, repair, notes
        FROM diagnosis
        WHERE UPPER(dtc_code) = ?
        LIMIT 1
    """, (code.strip().upper(),)).fetchone()

    if not row:
        return None

    keys = [
        "dtc_code", "title", "symptoms",
        "causes", "checks", "repair", "notes"
    ]

    return dict(zip(keys, row))


def get_dtc_statistics():

    conn = get_dtc_connection()

    if conn is None:
        return 0, 0

    try:
        row = conn.execute("""
            SELECT
                COUNT(*),
                COUNT(DISTINCT code)
            FROM dtc_definitions
        """).fetchone()

        return row[0], row[1]

    except Exception:
        return 0, 0


def get_manufacturers():

    conn = get_dtc_connection()

    if conn is None:
        return []

    try:
        return [
            row[0]
            for row in conn.execute("""
                SELECT DISTINCT manufacturer
                FROM dtc_definitions
                WHERE manufacturer IS NOT NULL
                ORDER BY manufacturer
            """).fetchall()
        ]
    except Exception:
        return []

# =========================================================
# FUNCTII VEHICLESDB
# =========================================================

def normalize_name(value):

    value = unicodedata.normalize(
        "NFKD",
        str(value or "")
    )

    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )

    return re.sub(
        r"[^a-z0-9]",
        "",
        value.lower()
    )


def get_vehicle_statistics():

    conn = get_vehicles_connection()

    if conn is None:
        return 0, 0

    try:
        makes = conn.execute(
            "SELECT COUNT(*) FROM makes"
        ).fetchone()[0]

        models = conn.execute(
            "SELECT COUNT(*) FROM models"
        ).fetchone()[0]

        return makes, models

    except Exception:
        return 0, 0


def get_vehicle_kinds():

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        return [
            row[0]
            for row in conn.execute("""
                SELECT DISTINCT kind
                FROM models
                ORDER BY kind
            """).fetchall()
        ]

    except Exception:
        return []


def get_vehicle_makes(kind):

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        return [
            row[0]
            for row in conn.execute("""
                SELECT DISTINCT mk.name
                FROM makes mk
                JOIN models mo
                    ON mo.make_id = mk.id
                WHERE mo.kind = ?
                ORDER BY mk.name
            """, (kind,)).fetchall()
        ]

    except Exception:
        return []


def search_vehicles(
    kind,
    make="Toate mărcile",
    search_text="",
    selected_year=0
):

    conn = get_vehicles_connection()

    if conn is None:
        return pd.DataFrame()

    model_columns = column_names(
        conn,
        "models"
    )

    make_columns = column_names(
        conn,
        "makes"
    )

    optional_model_fields = [
        "body_types",
        "regions",
        "year_start",
        "year_end",
        "lifecycle_status",
        "global_popularity_decile",
        "mass_popularity_decile"
    ]

    selected_fields = [
        f'mo."{field}"'
        for field in optional_model_fields
        if field in model_columns
    ]

    sql = """
        SELECT
            mo.id AS model_id,
            mo.kind AS category,
            mk.name AS make,
            mo.name AS model
    """

    if selected_fields:
        sql += ", " + ", ".join(selected_fields)

    if "country" in make_columns:
        sql += ", mk.country AS make_country"

    sql += """
        FROM models mo
        JOIN makes mk
            ON mk.id = mo.make_id
        WHERE mo.kind = ?
    """

    params = [kind]

    if make != "Toate mărcile":
        sql += " AND mk.name = ?"
        params.append(make)

    if search_text.strip():
        sql += " AND LOWER(mo.name) LIKE ?"
        params.append(
            f"%{search_text.strip().lower()}%"
        )

    sql += " ORDER BY mk.name, mo.name"

    try:
        df = pd.read_sql_query(
            sql,
            conn,
            params=params
        )

        if df.empty:
            return df

        # Disponibilitate pe țări.
        if "availability" in table_names(conn):

            availability = pd.read_sql_query("""
                SELECT
                    model_id,
                    kind,
                    GROUP_CONCAT(
                        DISTINCT country
                    ) AS countries
                FROM availability
                GROUP BY model_id, kind
            """, conn)

            df = df.merge(
                availability,
                left_on=["model_id", "category"],
                right_on=["model_id", "kind"],
                how="left"
            )

            if "kind" in df.columns:
                df = df.drop(columns=["kind"])

        else:
            df["countries"] = None

        # Eticheta anilor de fabricație.
        if (
            "year_start" in df.columns
            and "year_end" in df.columns
        ):

            start = pd.to_numeric(
                df["year_start"],
                errors="coerce"
            )

            end = pd.to_numeric(
                df["year_end"],
                errors="coerce"
            )

            def years_label(index):

                a = start.loc[index]
                b = end.loc[index]

                if pd.isna(a) and pd.isna(b):
                    return "Nespecificat"

                a_text = (
                    str(int(a))
                    if pd.notna(a)
                    else "?"
                )

                b_text = (
                    str(int(b))
                    if pd.notna(b)
                    else "În curs / necunoscut"
                )

                return f"{a_text} – {b_text}"

            df["Ani în catalog"] = [
                years_label(i)
                for i in df.index
            ]

            if selected_year > 0:

                df = df[
                    (
                        start.isna()
                        | (start <= selected_year)
                    )
                    &
                    (
                        end.isna()
                        | (end == 0)
                        | (end >= selected_year)
                    )
                ]

        else:
            df["Ani în catalog"] = "Nespecificat"

        # Aliasurile și popularitatea, dacă există.
        return df.reset_index(drop=True)

    except Exception as e:

        st.error(
            f"Eroare la căutarea vehiculelor: {e}"
        )

        return pd.DataFrame()


# =========================================================
# FUNCTII BAZA DE MOTORIZARI
# =========================================================

def get_engine_statistics():

    conn = get_engines_connection()

    if conn is None:
        return 0, 0, 0

    try:
        makes = conn.execute(
            "SELECT COUNT(*) FROM makes"
        ).fetchone()[0]

        models = conn.execute(
            "SELECT COUNT(*) FROM models"
        ).fetchone()[0]

        engines = conn.execute(
            "SELECT COUNT(*) FROM engines"
        ).fetchone()[0]

        return makes, models, engines

    except Exception:
        return 0, 0, 0


def find_engine_models(make, model):

    conn = get_engines_connection()

    if conn is None:
        return pd.DataFrame()

    try:
        df = pd.read_sql_query("""
            SELECT
                mo.id AS model_id,
                mk.name AS make,
                mo.name AS model,
                mo.year_start AS model_year_start,
                mo.year_end AS model_year_end
            FROM models mo
            JOIN makes mk
                ON mk.id = mo.make_id
        """, conn)

        wanted_make = normalize_name(make)
        wanted_model = normalize_name(model)

        df["_make_key"] = df["make"].map(
            normalize_name
        )

        df["_model_key"] = df["model"].map(
            normalize_name
        )

        result = df[
            (df["_make_key"] == wanted_make)
            &
            (df["_model_key"] == wanted_model)
        ].copy()

        return result.drop(
            columns=["_make_key", "_model_key"]
        )

    except Exception:
        return pd.DataFrame()


def get_model_generations_and_engines(
    make,
    model
):

    conn = get_engines_connection()

    empty = pd.DataFrame(), pd.DataFrame()

    if conn is None:
        return empty

    matches = find_engine_models(
        make,
        model
    )

    if matches.empty:
        return empty

    model_ids = [
        int(x)
        for x in matches["model_id"].tolist()
    ]

    placeholders = ",".join(
        ["?"] * len(model_ids)
    )

    try:
        generations = pd.read_sql_query(
            f"""
            SELECT
                id AS generation_id,
                model_id,
                name AS generation,
                year_start,
                year_end,
                body_type
            FROM generations
            WHERE model_id IN ({placeholders})
            ORDER BY year_start, name
            """,
            conn,
            params=model_ids
        )

        engines = pd.read_sql_query(
            f"""
            SELECT
                mk.name AS make,
                mo.name AS model,
                g.name AS generation,
                g.year_start AS generation_year_start,
                g.year_end AS generation_year_end,
                g.body_type,
                e.id AS engine_id,
                e.label AS engine,
                e.fuel_type,
                e.cylinders,
                e.displacement_cc,
                e.power_hp,
                e.torque_nm,
                e.transmission,
                e.drivetrain,
                e.zero_to_100_s,
                e.top_speed_kmh,
                e.fuel_economy_combined_l100,
                e.length_mm,
                e.width_mm,
                e.height_mm,
                e.wheelbase_mm,
                e.curb_weight_kg
            FROM engines e
            JOIN generations g
                ON g.id = e.generation_id
            JOIN models mo
                ON mo.id = g.model_id
            JOIN makes mk
                ON mk.id = mo.make_id
            WHERE g.model_id IN ({placeholders})
            ORDER BY
                g.year_start,
                e.power_hp,
                e.label
            """,
            conn,
            params=model_ids
        )

        return generations, engines

    except Exception as e:

        st.warning(
            f"Nu am putut citi generațiile sau motoarele: {e}"
        )

        return empty


# =========================================================
# SPECIFICATII SUPLIMENTARE MOTOR
# =========================================================

def get_engine_raw_specs(engine_id):

    conn = get_engines_connection()

    if conn is None:
        return pd.DataFrame()

    try:
        return pd.read_sql_query("""
            SELECT
                key AS Specificație,
                value AS Valoare
            FROM engine_specs
            WHERE engine_id = ?
            ORDER BY key
        """, conn, params=(int(engine_id),))

    except Exception:
        return pd.DataFrame()


# =========================================================
# FORMATARE AFISARE
# =========================================================

def display_value(value):

    if value is None:
        return "Nespecificat"

    try:
        if pd.isna(value):
            return "Nespecificat"
    except (TypeError, ValueError):
        pass

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def format_generation_years(row):

    start = row.get("year_start")
    end = row.get("year_end")

    if pd.isna(start) and pd.isna(end):
        return "Ani nespecificați"

    start_text = display_value(start)
    end_text = display_value(end)

    return f"{start_text} – {end_text}"


def get_manufacturer_names():

    return get_manufacturers()

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🔧 Auto Diagnosis Pro")

page = st.sidebar.radio(
    "MENIU PRINCIPAL",
    [
        "Dashboard",
        "DTC Diagnosis",
        "DTC Search",
        "Vehicle Search",
        "Repair Cases",
        "Database"
    ]
)

st.sidebar.markdown("---")

if DTC_DB_PATH.exists():
    st.sidebar.success("DTC Database: OK")
else:
    st.sidebar.error("DTC Database: Missing")

st.sidebar.success("Diagnosis Database: OK")

if vehicles_ready:
    st.sidebar.success("Vehicle Database: OK")
else:
    st.sidebar.warning("Vehicle Database: indisponibilă")

if engines_ready:
    st.sidebar.success("Engine Database: OK")
else:
    st.sidebar.warning("Engine Database: indisponibilă")


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.markdown(
        '<div class="main-title">🔧 Auto Diagnosis Pro</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Platformă de informații auto și diagnosticare."
    )

    dtc_definitions, dtc_codes = get_dtc_statistics()

    vehicle_makes, vehicle_models = (
        get_vehicle_statistics()
    )

    engine_makes, engine_models, engine_count = (
        get_engine_statistics()
    )

    diagnosis_conn = get_diagnosis_connection()

    diagnosis_count = diagnosis_conn.execute(
        "SELECT COUNT(*) FROM diagnosis"
    ).fetchone()[0]

    st.subheader("Statistici generale")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Coduri DTC unice",
        f"{dtc_codes:,}"
    )

    c2.metric(
        "Definiții DTC",
        f"{dtc_definitions:,}"
    )

    c3.metric(
        "Fișe de diagnostic",
        f"{diagnosis_count:,}"
    )

    st.markdown("---")

    st.subheader("Catalog vehicule")

    v1, v2, v3 = st.columns(3)

    v1.metric(
        "Mărci",
        f"{vehicle_makes:,}"
    )

    v2.metric(
        "Modele",
        f"{vehicle_models:,}"
    )

    v3.metric(
        "Bază catalog",
        "Disponibilă" if vehicles_ready else "Indisponibilă"
    )

    st.markdown("---")

    st.subheader("Baza de motorizări")

    e1, e2, e3 = st.columns(3)

    e1.metric("Mărci", f"{engine_makes:,}")
    e2.metric("Modele", f"{engine_models:,}")
    e3.metric("Variante motor", f"{engine_count:,}")

    if not engines_ready:
        st.warning(engines_status)

    st.markdown("---")

    st.subheader("Module")

    c1, c2, c3 = st.columns(3)

    c1.info(
        "**DTC Diagnosis**\n\n"
        "Cauze, simptome și verificări."
    )

    c2.info(
        "**DTC Search**\n\n"
        "Căutare în baza de coduri."
    )

    c3.info(
        "**Vehicle Search**\n\n"
        "Mărci, modele, ani și motoare."
    )

    c4, c5, c6 = st.columns(3)

    c4.info(
        "**Repair Cases**\n\n"
        "Modul pregătit pentru cazuri de service."
    )

    c5.info(
        "**Database**\n\n"
        "Statistici și starea bazelor."
    )

    c6.info(
        "**Diagnosis Library**\n\n"
        "Bibliotecă de fișe DTC."
    )


# =========================================================
# DTC DIAGNOSIS
# =========================================================

elif page == "DTC Diagnosis":

    st.title("🔍 DTC Diagnosis")

    st.write(
        "Introdu codul de eroare pentru a vedea informațiile disponibile."
    )

    code_input = st.text_input(
        "Cod DTC",
        placeholder="Exemplu: P0300"
    ).strip().upper()

    manufacturers = get_manufacturer_names()

    manufacturer = st.selectbox(
        "Producător",
        ["Toți producătorii"] + manufacturers
    )

    if st.button(
        "Caută codul",
        type="primary"
    ) and code_input:

        st.session_state["diagnosis_code"] = code_input

    code = st.session_state.get(
        "diagnosis_code",
        ""
    )

    if code:

        dtc_results = search_dtc(code)
        diagnosis = get_diagnosis(code)

        if (
            manufacturer != "Toți producătorii"
            and not dtc_results.empty
        ):

            dtc_results = dtc_results[
                dtc_results["manufacturer"] == manufacturer
            ]

        st.markdown("---")

        if dtc_results.empty:

            st.warning(
                "Nu am găsit codul în baza DTC "
                "pentru producătorul selectat."
            )

        else:

            st.success(
                f"Codul {code} a fost găsit."
            )

            st.dataframe(
                dtc_results,
                use_container_width=True,
                hide_index=True
            )

        if diagnosis:

            st.markdown("---")
            st.subheader(diagnosis["title"])

            st.markdown("### Simptome")
            st.write(diagnosis["symptoms"])

            st.markdown("### Cauze posibile")
            st.write(diagnosis["causes"])

            st.markdown("### Verificări recomandate")
            st.write(diagnosis["checks"])

            st.markdown("### Reparație")
            st.write(diagnosis["repair"])

            st.info(diagnosis["notes"])

        elif not dtc_results.empty:

            st.info(
                "Codul există în baza DTC, dar nu are încă "
                "o fișă extinsă în biblioteca locală."
            )


# =========================================================
# DTC SEARCH
# =========================================================

elif page == "DTC Search":

    st.title("🔎 DTC Search")

    search_term = st.text_input(
        "Caută după cod, descriere sau producător",
        placeholder="Exemplu: P0300, misfire, Toyota..."
    )

    manufacturers = get_manufacturers()

    manufacturer = st.selectbox(
        "Producător",
        ["Toți producătorii"] + manufacturers
    )

    if search_term.strip():

        results = search_dtc_text(
            search_term,
            manufacturer
        )

        st.success(
            f"{len(results):,} rezultate găsite."
        )

        if results.empty:

            st.info("Nu există rezultate.")

        else:

            st.dataframe(
                results,
                use_container_width=True,
                hide_index=True,
                height=550
            )

            csv_data = results.to_csv(
                index=False
            ).encode("utf-8-sig")

            st.download_button(
                "📥 Descarcă rezultatele CSV",
                data=csv_data,
                file_name="dtc_search_results.csv",
                mime="text/csv"
            )


# =========================================================
# VEHICLE SEARCH
# =========================================================

elif page == "Vehicle Search":

    st.title("🚗 Vehicle Search")

    st.write(
        "Caută vehicule după categorie, marcă, model și an."
    )

    if not vehicles_ready:

        st.error(vehicles_status)

        if st.button("Reîncarcă aplicația"):
            st.cache_resource.clear()
            st.rerun()

    else:

        kinds = get_vehicle_kinds()

        kind_labels = {
            "car": "Autoturisme",
            "motorcycle": "Motociclete",
            "moped": "Mopede",
            "van": "Autoutilitare",
            "truck": "Camioane",
            "bus": "Autobuze"
        }

        if not kinds:

            st.warning(
                "Nu au fost găsite categorii în catalog."
            )

        else:

            selected_kind = st.selectbox(
                "Categorie",
                kinds,
                format_func=lambda value: kind_labels.get(
                    value,
                    value.capitalize()
                )
            )

            makes = get_vehicle_makes(
                selected_kind
            )

            selected_make = st.selectbox(
                "Marcă",
                ["Toate mărcile"] + makes
            )

            model_text = st.text_input(
                "Model",
                placeholder="Exemplu: Golf, Corolla, Focus..."
            )

            selected_year = st.number_input(
                "An (0 = fără filtru)",
                min_value=0,
                max_value=2100,
                value=0,
                step=1
            )

            if st.button(
                "🔎 Caută vehicule",
                type="primary"
            ):

                results = search_vehicles(
                    selected_kind,
                    selected_make,
                    model_text,
                    int(selected_year)
                )

                st.session_state["vehicle_results"] = results

            results = st.session_state.get(
                "vehicle_results",
                pd.DataFrame()
            )

            if not results.empty:

                st.markdown("---")

                st.success(
                    f"{len(results):,} modele găsite."
                )

                display_columns = [
                    "category",
                    "make",
                    "model",
                    "Ani în catalog"
                ]

                for optional in [
                    "body_types",
                    "countries",
                    "regions",
                    "lifecycle_status"
                ]:
                    if optional in results.columns:
                        display_columns.append(optional)

                display = results[
                    display_columns
                ].copy()

                display = display.rename(
                    columns={
                        "category": "Categorie",
                        "make": "Marcă",
                        "model": "Model",
                        "body_types": "Caroserie",
                        "countries": "Țări",
                        "regions": "Regiuni",
                        "lifecycle_status": "Stare model"
                    }
                )

                st.dataframe(
                    display,
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )

                csv_data = display.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    "📥 Descarcă modelele CSV",
                    data=csv_data,
                    file_name="vehicle_models.csv",
                    mime="text/csv"
                )

                st.markdown("---")

                st.subheader(
                    "Generații și motorizări"
                )

                choices = [
                    f"{row['make']} — {row['model']}"
                    for _, row in results.iterrows()
                ]

                selected_vehicle = st.selectbox(
                    "Selectează modelul",
                    choices,
                    key="vehicle_engine_selection"
                )

                selected_index = choices.index(
                    selected_vehicle
                )

                selected_row = results.iloc[
                    selected_index
                ]

                if selected_kind != "car":

                    st.info(
                        "Baza suplimentară de motorizări "
                        "este destinată autoturismelor. "
                        "Pentru această categorie nu afișăm "
                        "motoare care nu au fost confirmate."
                    )

                elif not engines_ready:

                    st.warning(engines_status)

                else:

                    generations, engines = (
                        get_model_generations_and_engines(
                            selected_row["make"],
                            selected_row["model"]
                        )
                    )

                    if engines.empty:

                        st.warning(
                            "Nu a fost găsită o potrivire exactă "
                            "în baza suplimentară de motorizări."
                        )

                    else:

                        st.success(
                            f"{len(engines):,} variante de motor găsite."
                        )

                        if not generations.empty:

                            generation_display = generations.copy()

                            generation_display[
                                "Ani generație"
                            ] = generation_display.apply(
                                format_generation_years,
                                axis=1
                            )

                            generation_display = (
                                generation_display.rename(
                                    columns={
                                        "generation": "Generație",
                                        "body_type": "Caroserie"
                                    }
                                )
                            )

                            st.markdown("### Generații")

                            st.dataframe(
                                generation_display[
                                    [
                                        "Generație",
                                        "Ani generație",
                                        "Caroserie"
                                    ]
                                ],
                                use_container_width=True,
                                hide_index=True
                            )

                        st.markdown("### Variante de motorizare")

                        engine_display = engines.rename(
                            columns={
                                "make": "Marcă",
                                "model": "Model",
                                "generation": "Generație",
                                "generation_year_start": "An început",
                                "generation_year_end": "An sfârșit",
                                "body_type": "Caroserie",
                                "engine": "Motorizare",
                                "fuel_type": "Combustibil",
                                "cylinders": "Cilindri",
                                "displacement_cc": "Cilindree cc",
                                "power_hp": "Putere CP",
                                "torque_nm": "Cuplu Nm",
                                "transmission": "Transmisie",
                                "drivetrain": "Tracțiune",
                                "zero_to_100_s": "0–100 km/h sec",
                                "top_speed_kmh": "Viteză maximă km/h",
                                "fuel_economy_combined_l100": "Consum mixt",
                                "length_mm": "Lungime mm",
                                "width_mm": "Lățime mm",
                                "height_mm": "Înălțime mm",
                                "wheelbase_mm": "Ampatament mm",
                                "curb_weight_kg": "Masă kg"
                            }
                        )

                        preferred_columns = [
                            "Generație",
                            "An început",
                            "An sfârșit",
                            "Motorizare",
                            "Combustibil",
                            "Cilindri",
                            "Cilindree cc",
                            "Putere CP",
                            "Cuplu Nm",
                            "Transmisie",
                            "Tracțiune",
                            "0–100 km/h sec",
                            "Viteză maximă km/h",
                            "Consum mixt"
                        ]

                        visible_columns = [
                            c for c in preferred_columns
                            if c in engine_display.columns
                        ]

                        st.dataframe(
                            engine_display[visible_columns],
                            use_container_width=True,
                            hide_index=True,
                            height=450
                        )

                        engine_csv = engines.to_csv(
                            index=False
                        ).encode("utf-8-sig")

                        st.download_button(
                            "📥 Descarcă motorizările CSV",
                            data=engine_csv,
                            file_name="vehicle_engines.csv",
                            mime="text/csv"
                        )

                        st.markdown("---")

                        st.subheader(
                            "Specificații tehnice suplimentare"
                        )

                        engine_options = {
                            f"{row['generation']} — {row['engine']} — "
                            f"{display_value(row['power_hp'])} CP": int(row["engine_id"])
                            for _, row in engines.iterrows()
                        }

                        selected_engine_label = st.selectbox(
                            "Selectează motorizarea",
                            list(engine_options.keys())
                        )

                        selected_engine_id = engine_options[
                            selected_engine_label
                        ]

                        raw_specs = get_engine_raw_specs(
                            selected_engine_id
                        )

                        if raw_specs.empty:

                            st.caption(
                                "Nu există specificații suplimentare "
                                "înregistrate pentru acest motor."
                            )

                        else:

                            st.dataframe(
                                raw_specs,
                                use_container_width=True,
                                hide_index=True
                            )

                            raw_csv = raw_specs.to_csv(
                                index=False
                            ).encode("utf-8-sig")

                            st.download_button(
                                "📥 Descarcă specificațiile suplimentare",
                                data=raw_csv,
                                file_name="engine_extra_specs.csv",
                                mime="text/csv"
                            )

            else:

                st.caption(
                    "Alege filtrele și apasă butonul de căutare."
                )

    st.markdown("---")

    st.markdown(
        f"[Sursa catalogului de vehicule]({VEHICLES_SOURCE})"
    )

    st.markdown(
        f"[Sursa generațiilor și motorizărilor]({ENGINES_SOURCE})"
    )

    st.caption(
        "VehiclesDB: CC BY 4.0. "
        "vehicle-makes-models: ODbL 1.0. "
        "Datele despre generații și motorizări pot avea "
        "acoperire diferită între mărci și modele."
    )


# =========================================================
# REPAIR CASES
# =========================================================

elif page == "Repair Cases":

    st.title("🛠️ Repair Cases")

    st.info(
        "Modulul de cazuri reale de service este pregătit "
        "pentru dezvoltarea următoare."
    )

    st.markdown("""
    Funcții planificate:

    - Înregistrare vehicul și motorizare
    - Coduri DTC întâlnite
    - Simptome constatate
    - Cauză confirmată
    - Reparație efectuată
    - Fotografii și documente
    - Rezultat după reparație
    """)

    st.warning(
        "Salvarea cazurilor de reparație nu este activată în această versiune."
    )


# =========================================================
# DATABASE MANAGEMENT
# =========================================================

elif page == "Database":

    st.title("🗄️ Database Management")

    st.subheader("DTC Database")

    definitions, codes = get_dtc_statistics()

    d1, d2 = st.columns(2)

    d1.metric("Definiții DTC", f"{definitions:,}")
    d2.metric("Coduri unice", f"{codes:,}")

    if DTC_DB_PATH.exists():
        st.success("Fișier dtc_codes.db găsit.")
    else:
        st.error(
            "Fișierul dtc_codes.db lipsește din folderul data."
        )

    st.markdown("---")

    st.subheader("Diagnosis Database")

    diagnosis_conn = get_diagnosis_connection()

    diagnosis_count = diagnosis_conn.execute(
        "SELECT COUNT(*) FROM diagnosis"
    ).fetchone()[0]

    st.metric(
        "Fișe de diagnostic",
        diagnosis_count
    )

    diagnosis_list = pd.read_sql_query("""
        SELECT dtc_code, title
        FROM diagnosis
        ORDER BY dtc_code
    """, diagnosis_conn)

    st.dataframe(
        diagnosis_list,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    st.subheader("VehiclesDB")

    if vehicles_ready:

        makes, models = get_vehicle_statistics()

        c1, c2 = st.columns(2)

        c1.metric("Mărci", f"{makes:,}")
        c2.metric("Modele", f"{models:,}")

        st.success(vehicles_status)

        st.caption(
            f"Fișier local: {VEHICLES_DB_PATH.name}"
        )

        st.markdown(
            f"[Sursa VehiclesDB]({VEHICLES_SOURCE})"
        )

    else:

        st.error(vehicles_status)

    st.markdown("---")

    st.subheader("Engine Database")

    if engines_ready:

        makes, models, engine_count = (
            get_engine_statistics()
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Mărci", f"{makes:,}")
        c2.metric("Modele", f"{models:,}")
        c3.metric("Variante motor", f"{engine_count:,}")

        engine_conn = get_engines_connection()

        generation_count = engine_conn.execute(
            "SELECT COUNT(*) FROM generations"
        ).fetchone()[0]

        st.metric(
            "Generații",
            f"{generation_count:,}"
        )

        st.success(engines_status)

        st.caption(
            f"Fișier local: {ENGINES_DB_PATH.name}"
        )

        st.markdown(
            f"[Sursa bazei de motorizări]({ENGINES_SOURCE})"
        )

    else:

        st.warning(engines_status)

    st.markdown("---")

    st.subheader("Informații despre licențe")

    st.markdown("""
    - VehiclesDB: CC BY 4.0 — trebuie păstrată atribuirea sursei.
    - vehicle-makes-models: ODbL 1.0 — trebuie respectate atribuirea
      și obligațiile Share-Alike aplicabile bazei de date.
    """)

    st.caption(
        "Bazele de date sunt păstrate separat. "
        "Aplicația nu modifică fișierele originale descărcate."
    )


# =========================================================
# FINAL
# =========================================================

st.sidebar.markdown("---")
st.sidebar.caption("Auto Diagnosis Pro")
st.sidebar.caption("Vehicle & Diagnostic Database")
