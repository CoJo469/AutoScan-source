
# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 1 DIN 4 – BAZA APLICATIEI SI BAZELE DE DATE
# ============================================================

import os
import re
import csv
import json
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st


# ============================================================
# 1. CONFIGURARE GENERALA
# ============================================================

st.set_page_config(
    page_title="Auto Diagnosis Pro",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_TITLE = "Auto Diagnosis Pro"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DTC_DB_PATH = DATA_DIR / "dtc_codes.db"
VEHICLES_DB_PATH = DATA_DIR / "vehicles.db"
ENGINES_DB_PATH = DATA_DIR / "engines.db"
LOCAL_DB_PATH = DATA_DIR / "diagnosis.db"

VEHICLES_DB_URL = (
    "https://github.com/vehiclesdb/vehiclesdb/"
    "releases/latest/download/catalog.sqlite"
)

ENGINES_DB_URL = (
    "https://github.com/gor3a/vehicle-makes-models/"
    "releases/latest/download/vehicles.sqlite"
)

MECHANICDB_FIXES_URL = (
    "https://raw.githubusercontent.com/MechanicDB/"
    "MechanicDB-public/main/dtc_fixes_joined.csv"
)

MECHANICDB_PARTS_URL = (
    "https://raw.githubusercontent.com/MechanicDB/"
    "MechanicDB-public/main/replacement_parts.csv"
)


# ============================================================
# 2. STILUL APLICATIEI
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #101820;
        color: #f2f4f8;
    }

    [data-testid="stSidebar"] {
        background-color: #18232d;
    }

    div[data-testid="stMetric"] {
        background-color: #1d2b36;
        border: 1px solid #344654;
        padding: 14px;
        border-radius: 10px;
    }

    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }

    .app-note {
        background-color: #1d2b36;
        border-left: 4px solid #2997d8;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 12px;
    }

    .warning-note {
        background-color: #382d1d;
        border-left: 4px solid #e5a323;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 12px;
    }

    .success-note {
        background-color: #1d3529;
        border-left: 4px solid #35a66f;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 3. FUNCTII GENERALE
# ============================================================

def now_text():
    """Data si ora curenta, in format lizibil."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value):
    """Transforma valorile primite in text curat."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()


def safe_int(value, default=None):
    """Conversie sigura la numar intreg."""
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value, default=None):
    """Conversie sigura la numar zecimal."""
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def normalize_dtc(code):
    """Normalizeaza un cod OBD-II introdus de utilizator."""
    code = clean_text(code).upper()
    code = re.sub(r"[^A-Z0-9]", "", code)

    if len(code) != 5:
        return ""

    if code[0] not in ("P", "B", "C", "U"):
        return ""

    if not code[1:].isdigit():
        return ""

    return code


def show_notice(message, kind="info"):
    """Afiseaza un mesaj standardizat."""
    if kind == "warning":
        st.warning(message)
    elif kind == "success":
        st.success(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)


def table_exists(conn, table_name):
    """Verifica daca exista un tabel SQLite."""
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,)
    ).fetchone()

    return row is not None


def get_table_columns(conn, table_name):
    """Returneaza coloanele unui tabel, fara a presupune schema."""
    if not table_exists(conn, table_name):
        return []

    rows = conn.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    return [row[1] for row in rows]


def quote_identifier(name):
    """Protejeaza numele de tabele si coloane folosite in SQL."""
    return '"' + str(name).replace('"', '""') + '"'


def read_sqlite_table(db_path, table_name, limit=None):
    """Citeste un tabel SQLite daca exista."""
    db_path = Path(db_path)

    if not db_path.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not table_exists(conn, table_name):
                return pd.DataFrame()

            query = f"SELECT * FROM {quote_identifier(table_name)}"

            if limit is not None:
                query += f" LIMIT {int(limit)}"

            return pd.read_sql_query(query, conn)

    except Exception:
        return pd.DataFrame()


# ============================================================
# 4. DESCARCAREA BAZELOR DE DATE
# ============================================================

def download_file(url, destination, timeout=90):
    """
    Descarca un fisier numai daca nu exista deja.
    Scrie mai intai intr-un fisier temporar pentru a evita
    pastrarea unei descarcari incomplete.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = destination.with_suffix(
        destination.suffix + ".download"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AutoDiagnosisPro/1.0"}
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout
        ) as response:
            with open(temporary_file, "wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

        if not temporary_file.exists():
            return False, "Fisierul nu a fost descarcat."

        if temporary_file.stat().st_size < 100:
            temporary_file.unlink(missing_ok=True)
            return False, "Fisierul descarcat pare incomplet."

        temporary_file.replace(destination)

        return True, "Descarcare finalizata."

    except Exception as exc:
        temporary_file.unlink(missing_ok=True)
        return False, str(exc)


def sqlite_is_valid(db_path):
    """Verifica daca fisierul este o baza de date SQLite valida."""
    db_path = Path(db_path)

    if not db_path.exists():
        return False

    try:
        with sqlite3.connect(str(db_path)) as conn:
            result = conn.execute("PRAGMA quick_check").fetchone()
            return bool(result and result[0] == "ok")

    except Exception:
        return False


def ensure_external_database(db_path, url, required_tables):
    """
    Verifica o baza de date si o descarca daca lipseste.
    Sunt obligatorii numai tabelele enumerate explicit.
    """
    db_path = Path(db_path)

    if sqlite_is_valid(db_path):
        try:
            with sqlite3.connect(str(db_path)) as conn:
                existing_tables = {
                    row[0]
                    for row in conn.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                        """
                    ).fetchall()
                }

            if all(
                table in existing_tables
                for table in required_tables
            ):
                return True, "Baza de date este disponibila."

        except Exception:
            pass

    success, message = download_file(url, db_path)

    if not success:
        return False, message

    if not sqlite_is_valid(db_path):
        db_path.unlink(missing_ok=True)
        return False, "Fisierul descarcat nu este o baza SQLite valida."

    try:
        with sqlite3.connect(str(db_path)) as conn:
            existing_tables = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        missing = [
            table for table in required_tables
            if table not in existing_tables
        ]

        if missing:
            return False, (
                "Lipsesc tabelele obligatorii: "
                + ", ".join(missing)
            )

        return True, "Baza de date a fost descarcata si verificata."

    except Exception as exc:
        return False, str(exc)


# ============================================================
# 5. CONEXIUNI LA BAZELE DE DATE EXTERNE
# ============================================================

@st.cache_resource
def get_external_connection(db_path, modified_time):
    """
    Conexiune read-only.
    modified_time ajuta la reincarcarea conexiunii daca fisierul
    bazei de date este schimbat.
    """
    del modified_time

    uri = Path(db_path).resolve().as_uri() + "?mode=ro"

    return sqlite3.connect(
        uri,
        uri=True,
        check_same_thread=False
    )


def get_db_connection(db_path):
    """Conexiune locala normala, cu posibilitate de scriere."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def get_external_db(db_path):
    """Deschide o baza externa existenta."""
    db_path = Path(db_path)

    if not db_path.exists():
        return None

    try:
        modified_time = db_path.stat().st_mtime

        return get_external_connection(
            str(db_path),
            modified_time
        )

    except Exception:
        return None


# ============================================================
# 6. INITIALIZAREA BAZEI LOCALE
# ============================================================

def initialize_local_database():
    """
    Creeaza tabelele locale pentru:
    - cazuri de reparatie
    - intretinere
    - piese
    - documentatie tehnica
    - masuratori OBD
    - surse si provenienta datelor
    - diagnostice salvate
    """

    conn = get_db_connection(LOCAL_DB_PATH)

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS diagnosis_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dtc_code TEXT NOT NULL,
            title TEXT,
            possible_causes TEXT,
            symptoms TEXT,
            checks TEXT,
            repair_suggestions TEXT,
            source TEXT,
            confidence TEXT DEFAULT 'Orientativ',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS repair_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_date TEXT,
            make TEXT,
            model TEXT,
            year INTEGER,
            engine TEXT,
            mileage INTEGER,
            dtc_codes TEXT,
            symptoms TEXT,
            confirmed_cause TEXT,
            repair_performed TEXT,
            parts_used TEXT,
            result TEXT,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT,
            model TEXT,
            year_from INTEGER,
            year_to INTEGER,
            engine TEXT,
            operation TEXT NOT NULL,
            interval_km INTEGER,
            interval_months INTEGER,
            specification TEXT,
            quantity TEXT,
            source_name TEXT,
            source_url TEXT,
            confidence TEXT DEFAULT 'Neverificat',
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS parts_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT,
            oem_number TEXT,
            brand TEXT,
            category TEXT,
            description TEXT,
            make TEXT,
            model TEXT,
            year_from INTEGER,
            year_to INTEGER,
            engine TEXT,
            compatibility_status TEXT DEFAULT 'Neverificata',
            source_name TEXT,
            source_url TEXT,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS workshop_reference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT,
            model TEXT,
            year INTEGER,
            engine TEXT,
            subject TEXT NOT NULL,
            technical_information TEXT,
            source_name TEXT,
            source_url TEXT,
            license_info TEXT,
            confidence TEXT DEFAULT 'Neverificat',
            safety_warning TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS obd_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle TEXT,
            engine TEXT,
            measurement_date TEXT,
            pid TEXT,
            parameter_name TEXT,
            measured_value TEXT,
            unit TEXT,
            rpm INTEGER,
            coolant_temperature REAL,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS data_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            source_url TEXT,
            license_info TEXT,
            attribution TEXT,
            data_description TEXT,
            last_updated TEXT,
            notes TEXT
        );
        """
    )

    # Diagnostice orientative de baza.
    # Acestea nu inlocuiesc verificarea vehiculului.
    seed_records = [
        (
            "P0300",
            "Rateuri de aprindere detectate aleatoriu sau pe mai multi cilindri",
            "Bujii uzate, bobine, injectoare, presiune combustibil, admisie falsa, compresie.",
            "Motorul poate tremura, poate pierde putere sau poate functiona neregulat.",
            "Verifica bujiile, bobinele, corectiile de combustibil, presiunea combustibilului si compresia.",
            "Diagnostic pe cilindri si verificarea cauzei inainte de inlocuirea pieselor.",
            "Baza interna Auto Diagnosis Pro",
            "Orientativ"
        ),
        (
            "P0171",
            "Amestec prea sarac – Bank 1",
            "Aer fals pe admisie, debitmetru MAF, presiune combustibil scazuta, injectoare sau evacuare neetansa.",
            "Ralanti instabil, ezitari, putere redusa sau consum modificat.",
            "Verifica furtunurile de admisie, valorile MAF, corectiile STFT/LTFT si presiunea combustibilului.",
            "Localizeaza cauza amestecului sarac si verifica din nou corectiile dupa reparatie.",
            "Baza interna Auto Diagnosis Pro",
            "Orientativ"
        ),
        (
            "P0420",
            "Eficienta sistemului catalitic sub prag – Bank 1",
            "Catalizator degradat, senzori lambda, scapari pe evacuare sau probleme de functionare ale motorului.",
            "Martor Check Engine si uneori consum sau performanta modificate.",
            "Verifica scapari pe evacuare, functionarea sondelor lambda si eventualele rateuri sau amestec incorect.",
            "Nu inlocui catalizatorul inainte de verificarea cauzelor care pot afecta eficienta acestuia.",
            "Baza interna Auto Diagnosis Pro",
            "Orientativ"
        ),
        (
            "P0128",
            "Temperatura lichidului de racire sub temperatura de reglare",
            "Termostat blocat deschis, senzor temperatura sau probleme la circuitul de racire.",
            "Incalzire lenta a motorului sau temperatura de functionare neobisnuita.",
            "Compara temperatura raportata la rece cu temperatura ambientala si urmareste incalzirea motorului.",
            "Verifica termostatul si senzorul inainte de inlocuire.",
            "Baza interna Auto Diagnosis Pro",
            "Orientativ"
        ),
        (
            "P0101",
            "Performanta sau plauzibilitate debitmetru MAF – domeniu/performance",
            "MAF murdar sau defect, admisie neetansa, filtru de aer obturat sau cablaj.",
            "Putere redusa, ralanti instabil sau raspuns slab la acceleratie.",
            "Verifica filtrul de aer, admisia, mufele si valorile MAF in raport cu datele specifice motorului.",
            "Confirma cauza prin masuratori si inspectie, nu doar prin stergerea codului.",
            "Baza interna Auto Diagnosis Pro",
            "Orientativ"
        )
    ]

    for record in seed_records:
        exists = conn.execute(
            """
            SELECT id
            FROM diagnosis_records
            WHERE dtc_code = ?
            LIMIT 1
            """,
            (record[0],)
        ).fetchone()

        if not exists:
            conn.execute(
                """
                INSERT INTO diagnosis_records (
                    dtc_code, title, possible_causes, symptoms,
                    checks, repair_suggestions, source, confidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                record + (now_text(),)
            )

    # Surse de date si licente.
    source_records = [
        (
            "VehiclesDB",
            "https://github.com/vehiclesdb/vehiclesdb",
            "CC BY 4.0",
            "VehiclesDB",
            "Catalog de vehicule. Structura exacta este verificata din baza descarcata.",
            now_text(),
            "A se pastra atribuirea sursei."
        ),
        (
            "Vehicle Makes Models",
            "https://github.com/gor3a/vehicle-makes-models",
            "ODbL 1.0",
            "Vehicle Makes Models",
            "Marci, modele, generatii si variante de motorizare.",
            now_text(),
            "A se respecta obligatiile de atribuire si share-alike."
        ),
        (
            "MechanicDB Public Sample",
            "https://github.com/MechanicDB/MechanicDB-public",
            "ODbL 1.0",
            "MechanicDB",
            "Exemple publice de coduri, proceduri si mapari de piese.",
            now_text(),
            "Mostrele gratuite nu reprezinta o baza completa de compatibilitate."
        ),
        (
            "Open Labor Project",
            "https://openlaborproject.com/developers",
            "Conform termenilor serviciului",
            "Open Labor Project",
            "API optional pentru date tehnice si timpi de manopera.",
            now_text(),
            "Necesita cheie API si respectarea limitelor planului gratuit."
        )
    ]

    for source in source_records:
        exists = conn.execute(
            """
            SELECT id FROM data_sources
            WHERE source_name = ?
            LIMIT 1
            """,
            (source[0],)
        ).fetchone()

        if not exists:
            conn.execute(
                """
                INSERT INTO data_sources (
                    source_name, source_url, license_info,
                    attribution, data_description,
                    last_updated, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                source
            )

    conn.commit()
    conn.close()


# Initializam baza locala la pornirea aplicatiei.
initialize_local_database()


# ============================================================
# 7. FUNCTII PENTRU CODURI DE EROARE DTC
# ============================================================

def get_dtc_database_status():
    """Verifica disponibilitatea bazei DTC."""
    if not DTC_DB_PATH.exists():
        return False, "Fisierul dtc_codes.db nu exista."

    if not sqlite_is_valid(DTC_DB_PATH):
        return False, "Baza DTC nu este valida."

    return True, "Baza DTC este disponibila."


def find_dtc_table(conn):
    """Identifica tabelul principal de coduri DTC."""
    candidates = [
        "dtc_definitions",
        "dtc_codes",
        "codes",
        "diagnostic_trouble_codes"
    ]

    for table in candidates:
        if table_exists(conn, table):
            columns = get_table_columns(conn, table)

            if "code" in columns:
                return table

    return None


def search_dtc_database(search_term, limit=100):
    """
    Cauta in baza DTC folosind coloanele existente.
    Nu presupune ca toate bazele au aceeasi structura.
    """
    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return pd.DataFrame()

    try:
        table = find_dtc_table(conn)

        if not table:
            return pd.DataFrame()

        columns = get_table_columns(conn, table)

        searchable_columns = [
            column for column in columns
            if column.lower() in (
                "code",
                "manufacturer",
                "description",
                "definition",
                "system",
                "subsystem"
            )
        ]

        if not searchable_columns:
            return pd.DataFrame()

        term = clean_text(search_term)

        if not term:
            return pd.DataFrame()

        conditions = []
        parameters = []

        for column in searchable_columns:
            conditions.append(
                f"{quote_identifier(column)} LIKE ?"
            )
            parameters.append(f"%{term}%")

        query = (
            f"SELECT * FROM {quote_identifier(table)} "
            f"WHERE {' OR '.join(conditions)} "
            f"LIMIT ?"
        )

        parameters.append(int(limit))

        return pd.read_sql_query(
            query,
            conn,
            params=parameters
        )

    except Exception:
        return pd.DataFrame()

    finally:
        try:
            conn.close()
        except Exception:
            pass


def lookup_dtc_database(code):
    """Cauta un cod exact in baza DTC."""
    code = normalize_dtc(code)

    if not code:
        return pd.DataFrame()

    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return pd.DataFrame()

    try:
        table = find_dtc_table(conn)

        if not table:
            return pd.DataFrame()

        return pd.read_sql_query(
            f"""
            SELECT *
            FROM {quote_identifier(table)}
            WHERE UPPER(code) = ?
            LIMIT 100
            """,
            conn,
            params=(code,)
        )

    except Exception:
        return pd.DataFrame()

    finally:
        try:
            conn.close()
        except Exception:
            pass


def lookup_local_diagnosis(code):
    """Cauta explicatii in baza locala de diagnostice."""
    code = normalize_dtc(code)

    if not code:
        return None

    conn = get_db_connection(LOCAL_DB_PATH)

    row = conn.execute(
        """
        SELECT *
        FROM diagnosis_records
        WHERE UPPER(dtc_code) = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (code,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None


# ============================================================
# 8. FUNCTII PENTRU STRUCTURA BAZELOR VEHICULE SI MOTOARE
# ============================================================

def get_database_tables(db_path):
    """Listeaza tabelele unei baze SQLite."""
    db_path = Path(db_path)

    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()

        return [row[0] for row in rows]

    except Exception:
        return []


def get_database_schema(db_path):
    """Returneaza structura tabelelor unei baze."""
    schema = {}
    db_path = Path(db_path)

    if not db_path.exists():
        return schema

    try:
        with sqlite3.connect(str(db_path)) as conn:
            tables = get_database_tables(db_path)

            for table in tables:
                schema[table] = get_table_columns(conn, table)

    except Exception:
        pass

    return schema


def find_existing_column(columns, candidates):
    """Alege prima coloana existenta dintr-o lista de variante."""
    lower_map = {
        str(column).lower(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


def dynamic_table_search(
    db_path,
    table_name,
    search_columns,
    search_term,
    limit=100
):
    """Cauta intr-un tabel fara a presupune toate coloanele."""
    db_path = Path(db_path)

    if not db_path.exists():
        return pd.DataFrame()

    term = clean_text(search_term)

    if not term:
        return pd.DataFrame()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not table_exists(conn, table_name):
                return pd.DataFrame()

            columns = get_table_columns(conn, table_name)

            valid_columns = [
                column for column in search_columns
                if column in columns
            ]

            if not valid_columns:
                return pd.DataFrame()

            conditions = [
                f"{quote_identifier(column)} LIKE ?"
                for column in valid_columns
            ]

            parameters = [
                f"%{term}%"
                for _ in valid_columns
            ]

            query = (
                f"SELECT * FROM {quote_identifier(table_name)} "
                f"WHERE {' OR '.join(conditions)} "
                f"LIMIT ?"
            )

            parameters.append(int(limit))

            return pd.read_sql_query(
                query,
                conn,
                params=parameters
            )

    except Exception:
        return pd.DataFrame()


# ============================================================
# 9. FUNCTII VEHICULE
# ============================================================

def get_vehicle_database_status():
    """Verifica baza de date pentru vehicule."""
    if not VEHICLES_DB_PATH.exists():
        return False, "Baza vehicles.db nu exista."

    if not sqlite_is_valid(VEHICLES_DB_PATH):
        return False, "Baza vehicles.db nu este valida."

    tables = get_database_tables(VEHICLES_DB_PATH)

    # Verificam doar tabelele esentiale.
    if not all(
        table in tables
        for table in ("makes", "models")
    ):
        return False, (
            "Baza nu contine tabelele esentiale makes si models."
        )

    return True, "Baza de vehicule este disponibila."


def get_vehicle_makes():
    """Returneaza marcile din baza VehiclesDB."""
    db_path = VEHICLES_DB_PATH

    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not table_exists(conn, "makes"):
                return []

            columns = get_table_columns(conn, "makes")

            name_col = find_existing_column(
                columns,
                ["name", "make", "title", "brand"]
            )

            if not name_col:
                return []

            query = (
                f"SELECT DISTINCT {quote_identifier(name_col)} "
                f"FROM makes "
                f"WHERE {quote_identifier(name_col)} IS NOT NULL "
                f"ORDER BY {quote_identifier(name_col)}"
            )

            rows = conn.execute(query).fetchall()

            return [
                str(row[0])
                for row in rows
                if row[0] is not None
            ]

    except Exception:
        return []


def search_vehicles(make="", model="", search_term="", limit=200):
    """
    Cauta vehicule in baza VehiclesDB.
    Detecteaza dinamic coloanele disponibile.
    """
    db_path = VEHICLES_DB_PATH

    if not db_path.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not (
                table_exists(conn, "makes")
                and table_exists(conn, "models")
            ):
                return pd.DataFrame()

            make_columns = get_table_columns(conn, "makes")
            model_columns = get_table_columns(conn, "models")

            make_id_col = find_existing_column(
                make_columns,
                ["id", "make_id"]
            )

            make_name_col = find_existing_column(
                make_columns,
                ["name", "make", "title", "brand"]
            )

            model_id_col = find_existing_column(
                model_columns,
                ["id", "model_id"]
            )

            model_name_col = find_existing_column(
                model_columns,
                ["name", "model", "title"]
            )

            model_make_id_col = find_existing_column(
                model_columns,
                ["make_id", "manufacturer_id"]
            )

            if not model_name_col:
                return pd.DataFrame()

            selected = [
                f'm.{quote_identifier(column)} AS '
                f'{quote_identifier("model_" + column)}'
                for column in model_columns
            ]

            joins = ""
            if (
                make_id_col
                and make_name_col
                and model_make_id_col
            ):
                joins = (
                    f" LEFT JOIN makes mk ON "
                    f"m.{quote_identifier(model_make_id_col)} = "
                    f"mk.{quote_identifier(make_id_col)}"
                )

                selected.append(
                    f'mk.{quote_identifier(make_name_col)} '
                    f'AS "make_name"'
                )

            query = (
                "SELECT "
                + ", ".join(selected)
                + " FROM models m "
                + joins
            )

            conditions = []
            parameters = []

            if make and joins:
                conditions.append(
                    f'mk.{quote_identifier(make_name_col)} = ?'
                )
                parameters.append(make)

            if model:
                conditions.append(
                    f'm.{quote_identifier(model_name_col)} LIKE ?'
                )
                parameters.append(f"%{model}%")

            if search_term:
                term_columns = [
                    column for column in model_columns
                    if column.lower() in (
                        "name", "model", "title",
                        "kind", "type", "category"
                    )
                ]

                if term_columns:
                    term_conditions = [
                        f'm.{quote_identifier(column)} LIKE ?'
                        for column in term_columns
                    ]

                    conditions.append(
                        "(" + " OR ".join(term_conditions) + ")"
                    )

                    parameters.extend(
                        [f"%{search_term}%"] * len(term_columns)
                    )

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " LIMIT ?"
            parameters.append(int(limit))

            return pd.read_sql_query(
                query,
                conn,
                params=parameters
            )

    except Exception:
        return pd.DataFrame()


# ============================================================
# 10. FUNCTII PENTRU BAZA DE DATE A MOTOARELOR
# ============================================================

def get_engine_database_status():
    """Verifica baza de date cu motoare si generatii."""
    if not ENGINES_DB_PATH.exists():
        return False, "Baza engines.db nu exista."

    if not sqlite_is_valid(ENGINES_DB_PATH):
        return False, "Baza engines.db nu este valida."

    tables = get_database_tables(ENGINES_DB_PATH)

    required = ["makes", "models", "generations", "engines"]

    missing = [
        table for table in required
        if table not in tables
    ]

    if missing:
        return False, (
            "Lipsesc tabelele esentiale: "
            + ", ".join(missing)
        )

    return True, "Baza de motoare este disponibila."


def get_engine_makes():
    """Returneaza marcile disponibile in baza de motoare."""
    return get_vehicle_makes_from_engine_db()


def get_vehicle_makes_from_engine_db():
    db_path = ENGINES_DB_PATH

    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not table_exists(conn, "makes"):
                return []

            columns = get_table_columns(conn, "makes")

            id_col = find_existing_column(
                columns,
                ["id", "make_id"]
            )

            name_col = find_existing_column(
                columns,
                ["name", "make", "title"]
            )

            if not name_col:
                return []

            query = (
                f"SELECT DISTINCT {quote_identifier(name_col)} "
                f"FROM makes "
                f"WHERE {quote_identifier(name_col)} IS NOT NULL "
                f"ORDER BY {quote_identifier(name_col)}"
            )

            rows = conn.execute(query).fetchall()

            return [
                str(row[0])
                for row in rows
                if row[0] is not None
            ]

    except Exception:
        return []


def search_engine_catalog(
    make="",
    model="",
    year=None,
    engine_search="",
    limit=300
):
    """
    Cauta motoare in catalogul de generatii.
    Foloseste numai coloanele care exista efectiv.
    """
    db_path = ENGINES_DB_PATH

    if not db_path.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            required_tables = [
                "makes", "models", "generations", "engines"
            ]

            if not all(
                table_exists(conn, table)
                for table in required_tables
            ):
                return pd.DataFrame()

            mc = get_table_columns(conn, "makes")
            moc = get_table_columns(conn, "models")
            gc = get_table_columns(conn, "generations")
            ec = get_table_columns(conn, "engines")

            make_id = find_existing_column(mc, ["id"])
            make_name = find_existing_column(
                mc, ["name", "make", "title"]
            )

            model_id = find_existing_column(moc, ["id"])
            model_name = find_existing_column(
                moc, ["name", "model", "title"]
            )
            model_make_id = find_existing_column(
                moc, ["make_id"]
            )

            generation_id = find_existing_column(gc, ["id"])
            generation_model_id = find_existing_column(
                gc, ["model_id"]
            )

            engine_generation_id = find_existing_column(
                ec, ["generation_id"]
            )

            engine_label = find_existing_column(
                ec, ["label", "name", "engine", "code"]
            )

            if not all([
                make_id,
                make_name,
                model_id,
                model_name,
                model_make_id,
                generation_id,
                generation_model_id,
                engine_generation_id
            ]):
                return pd.DataFrame()

            select_parts = [
                f'mk.{quote_identifier(make_name)} AS make',
                f'm.{quote_identifier(model_name)} AS model'
            ]

            for column in gc:
                select_parts.append(
                    f'g.{quote_identifier(column)} AS '
                    f'{quote_identifier("generation_" + column)}'
                )

            for column in ec:
                select_parts.append(
                    f'e.{quote_identifier(column)} AS '
                    f'{quote_identifier("engine_" + column)}'
                )

            query = (
                "SELECT "
                + ", ".join(select_parts)
                + " FROM engines e "
                + "JOIN generations g ON "
                + f"e.{quote_identifier(engine_generation_id)} = "
                + f"g.{quote_identifier(generation_id)} "
                + "JOIN models m ON "
                + f"g.{quote_identifier(generation_model_id)} = "
                + f"m.{quote_identifier(model_id)} "
                + "JOIN makes mk ON "
                + f"m.{quote_identifier(model_make_id)} = "
                + f"mk.{quote_identifier(make_id)}"
            )

            conditions = []
            parameters = []

            if make:
                conditions.append(
                    f"mk.{quote_identifier(make_name)} = ?"
                )
                parameters.append(make)

            if model:
                conditions.append(
                    f"m.{quote_identifier(model_name)} LIKE ?"
                )
                parameters.append(f"%{model}%")

            if year is not None:
                year_start = find_existing_column(
                    gc, ["year_start", "start_year", "year_from"]
                )
                year_end = find_existing_column(
                    gc, ["year_end", "end_year", "year_to"]
                )

                if year_start and year_end:
                    conditions.append(
                        f"g.{quote_identifier(year_start)} <= ?"
                    )
                    conditions.append(
                        f"("
                        f"g.{quote_identifier(year_end)} IS NULL "
                        f"OR g.{quote_identifier(year_end)} = 0 "
                        f"OR g.{quote_identifier(year_end)} >= ?"
                        f")"
                    )
                    parameters.extend([int(year), int(year)])

                elif year_start:
                    conditions.append(
                        f"g.{quote_identifier(year_start)} = ?"
                    )
                    parameters.append(int(year))

            if engine_search and engine_label:
                conditions.append(
                    f"e.{quote_identifier(engine_label)} LIKE ?"
                )
                parameters.append(f"%{engine_search}%")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " LIMIT ?"
            parameters.append(int(limit))

            return pd.read_sql_query(
                query,
                conn,
                params=parameters
            )

    except Exception:
        return pd.DataFrame()


def get_engine_specs(engine_id):
    """Returneaza specificatiile suplimentare pentru un motor."""
    db_path = ENGINES_DB_PATH

    if not db_path.exists():
        return pd.DataFrame()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if not table_exists(conn, "engine_specs"):
                return pd.DataFrame()

            columns = get_table_columns(conn, "engine_specs")

            engine_id_col = find_existing_column(
                columns, ["engine_id"]
            )

            if not engine_id_col:
                return pd.DataFrame()

            return pd.read_sql_query(
                f"""
                SELECT *
                FROM engine_specs
                WHERE {quote_identifier(engine_id_col)} = ?
                """,
                conn,
                params=(engine_id,)
            )

    except Exception:
        return pd.DataFrame()


# ============================================================
# 11. FUNCTII GENERICE PENTRU DATELE LOCALE
# ============================================================

def get_local_table(table_name, limit=1000):
    """Citeste date dintr-un tabel al aplicatiei."""
    allowed_tables = {
        "diagnosis_records",
        "repair_cases",
        "maintenance_records",
        "parts_records",
        "workshop_reference",
        "obd_measurements",
        "data_sources"
    }

    if table_name not in allowed_tables:
        return pd.DataFrame()

    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        return pd.read_sql_query(
            f"""
            SELECT *
            FROM {quote_identifier(table_name)}
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(int(limit),)
        )

    except Exception:
        return pd.DataFrame()

    finally:
        conn.close()


def add_local_record(table_name, record):
    """Adauga un rand intr-un tabel local permis."""
    allowed_tables = {
        "repair_cases",
        "maintenance_records",
        "parts_records",
        "workshop_reference",
        "obd_measurements",
        "data_sources"
    }

    if table_name not in allowed_tables:
        raise ValueError("Tabel local nepermis.")

    if not isinstance(record, dict) or not record:
        raise ValueError("Datele introduse nu sunt valide.")

    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        columns = get_table_columns(conn, table_name)

        valid_record = {
            key: value
            for key, value in record.items()
            if key in columns and key != "id"
        }

        if not valid_record:
            raise ValueError("Nu exista campuri valide de salvat.")

        field_names = list(valid_record.keys())

        query = (
            f"INSERT INTO {quote_identifier(table_name)} "
            f"({', '.join(quote_identifier(c) for c in field_names)}) "
            f"VALUES ({', '.join('?' for _ in field_names)})"
        )

        conn.execute(
            query,
            [valid_record[field] for field in field_names]
        )

        conn.commit()

    finally:
        conn.close()


def update_local_record(table_name, record_id, record):
    """Actualizeaza un rand dintr-un tabel local permis."""
    allowed_tables = {
        "repair_cases",
        "maintenance_records",
        "parts_records",
        "workshop_reference",
        "obd_measurements"
    }

    if table_name not in allowed_tables:
        raise ValueError("Tabel local nepermis.")

    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        columns = get_table_columns(conn, table_name)

        valid_record = {
            key: value
            for key, value in record.items()
            if key in columns and key != "id"
        }

        if not valid_record:
            raise ValueError("Nu exista campuri de actualizat.")

        assignments = ", ".join(
            f"{quote_identifier(column)} = ?"
            for column in valid_record
        )

        query = (
            f"UPDATE {quote_identifier(table_name)} "
            f"SET {assignments} WHERE id = ?"
        )

        conn.execute(
            query,
            list(valid_record.values()) + [int(record_id)]
        )

        conn.commit()

    finally:
        conn.close()


def delete_local_record(table_name, record_id):
    """Sterge un rand dintr-un tabel local permis."""
    allowed_tables = {
        "repair_cases",
        "maintenance_records",
        "parts_records",
        "workshop_reference",
        "obd_measurements"
    }

    if table_name not in allowed_tables:
        raise ValueError("Tabel local nepermis.")

    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        conn.execute(
            f"DELETE FROM {quote_identifier(table_name)} WHERE id = ?",
            (int(record_id),)
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# SFARSIT PARTEA 1 DIN 4
# Urmeaza: surse gratuite, import date si functii suplimentare.
# ============================================================

# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 2 DIN 4 – SURSE GRATUITE, IMPORT SI DIAGNOSTIC
# ============================================================


# ============================================================
# 1. DESCARCARE OPTIONALA MECHANICDB
# ============================================================

MECHANICDB_DIR = DATA_DIR / "mechanicdb"
MECHANICDB_DIR.mkdir(exist_ok=True)

MECHANICDB_FIXES_PATH = MECHANICDB_DIR / "dtc_fixes_joined.csv"
MECHANICDB_PARTS_PATH = MECHANICDB_DIR / "replacement_parts.csv"


def download_mechanicdb_sample():
    """
    Descarca mostrele publice MechanicDB.
    Daca sursa nu este disponibila, aplicatia continua sa functioneze.
    """
    results = []

    files = [
        (MECHANICDB_FIXES_URL, MECHANICDB_FIXES_PATH),
        (MECHANICDB_PARTS_URL, MECHANICDB_PARTS_PATH)
    ]

    for url, destination in files:
        success, message = download_file(
            url,
            destination,
            timeout=60
        )

        results.append({
            "Fisier": destination.name,
            "Rezultat": "Descarcat" if success else "Indisponibil",
            "Detalii": message
        })

    return pd.DataFrame(results)


def read_mechanicdb_csv(file_path, limit=None):
    """
    Citeste fisierele CSV MechanicDB.
    Mostrele publice folosesc separatorul |.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            file_path,
            sep="|",
            encoding="utf-8-sig",
            dtype=str,
            low_memory=False
        )

        df.columns = [
            str(column).strip()
            for column in df.columns
        ]

        if limit:
            df = df.head(int(limit))

        return df

    except Exception:
        try:
            return pd.read_csv(
                file_path,
                encoding="utf-8-sig",
                dtype=str,
                low_memory=False
            )
        except Exception:
            return pd.DataFrame()


def get_mechanicdb_fixes():
    return read_mechanicdb_csv(MECHANICDB_FIXES_PATH)


def get_mechanicdb_parts():
    return read_mechanicdb_csv(MECHANICDB_PARTS_PATH)


def search_mechanicdb_fixes(search_term, limit=100):
    """Cauta in mostrele de proceduri MechanicDB."""
    df = get_mechanicdb_fixes()

    if df.empty or not clean_text(search_term):
        return pd.DataFrame()

    term = clean_text(search_term).lower()

    mask = df.astype(str).apply(
        lambda column: column.str.lower().str.contains(
            re.escape(term),
            na=False
        )
    ).any(axis=1)

    return df.loc[mask].head(limit)


def search_mechanicdb_parts(search_term, limit=100):
    """Cauta in mostrele de piese MechanicDB."""
    df = get_mechanicdb_parts()

    if df.empty or not clean_text(search_term):
        return pd.DataFrame()

    term = clean_text(search_term).lower()

    mask = df.astype(str).apply(
        lambda column: column.str.lower().str.contains(
            re.escape(term),
            na=False
        )
    ).any(axis=1)

    return df.loc[mask].head(limit)


def get_mechanicdb_status():
    """Afiseaza starea fisierelor MechanicDB."""
    return {
        "Proceduri": MECHANICDB_FIXES_PATH.exists(),
        "Piese": MECHANICDB_PARTS_PATH.exists()
    }


# ============================================================
# 2. CAUTARE COMBINATA DTC
# ============================================================

def combined_dtc_search(code):
    """
    Combina rezultatele din:
    - baza DTC existenta
    - baza locala de diagnostic
    - mostra MechanicDB
    """
    code = normalize_dtc(code)

    if not code:
        return {
            "database": pd.DataFrame(),
            "local": None,
            "mechanicdb": pd.DataFrame()
        }

    return {
        "database": lookup_dtc_database(code),
        "local": lookup_local_diagnosis(code),
        "mechanicdb": search_mechanicdb_fixes(code)
    }


def get_dtc_manufacturers():
    """Returneaza producatorii existenti in baza DTC."""
    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return []

    try:
        table = find_dtc_table(conn)

        if not table:
            return []

        columns = get_table_columns(conn, table)

        manufacturer_col = find_existing_column(
            columns,
            ["manufacturer", "make", "brand"]
        )

        if not manufacturer_col:
            return []

        rows = conn.execute(
            f"""
            SELECT DISTINCT {quote_identifier(manufacturer_col)}
            FROM {quote_identifier(table)}
            WHERE {quote_identifier(manufacturer_col)} IS NOT NULL
              AND TRIM({quote_identifier(manufacturer_col)}) != ''
            ORDER BY {quote_identifier(manufacturer_col)}
            """
        ).fetchall()

        return [
            str(row[0])
            for row in rows
            if row[0]
        ]

    except Exception:
        return []

    finally:
        conn.close()


def get_dtc_statistics():
    """Calculeaza statistici despre baza de coduri DTC."""
    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return {
            "total": 0,
            "manufacturers": 0
        }

    try:
        table = find_dtc_table(conn)

        if not table:
            return {
                "total": 0,
                "manufacturers": 0
            }

        total = conn.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table)}"
        ).fetchone()[0]

        columns = get_table_columns(conn, table)

        manufacturer_col = find_existing_column(
            columns,
            ["manufacturer", "make", "brand"]
        )

        manufacturers = 0

        if manufacturer_col:
            manufacturers = conn.execute(
                f"""
                SELECT COUNT(DISTINCT {quote_identifier(manufacturer_col)})
                FROM {quote_identifier(table)}
                WHERE {quote_identifier(manufacturer_col)} IS NOT NULL
                """
            ).fetchone()[0]

        return {
            "total": total,
            "manufacturers": manufacturers
        }

    except Exception:
        return {
            "total": 0,
            "manufacturers": 0
        }

    finally:
        conn.close()


# ============================================================
# 3. DIAGNOSTICARE PE SIMPTOME
# ============================================================

SYMPTOM_GUIDE = {
    "Motorul tremura la ralanti": [
        "Verifica eventualele coduri de rateuri P0300-P030x.",
        "Verifica bujiile si bobinele, daca motorul este pe benzina.",
        "Verifica injectoarele si alimentarea.",
        "Verifica admisia pentru pierderi de aer.",
        "Verifica valorile de corectie combustibil si compresia."
    ],
    "Motorul nu are putere": [
        "Citeste codurile de eroare din ECU.",
        "Verifica filtrul de aer si admisia.",
        "Verifica presiunea combustibilului.",
        "Verifica turbocompresorul si circuitul de supraalimentare, daca exista.",
        "Verifica evacuarea si eventualele restrictii."
    ],
    "Consum mare de combustibil": [
        "Verifica temperatura reala si raportata a motorului.",
        "Verifica corectiile de combustibil.",
        "Verifica senzorii MAF si lambda, unde sunt disponibili.",
        "Verifica presiunea combustibilului si injectoarele.",
        "Verifica franele si presiunea anvelopelor."
    ],
    "Pornire grea": [
        "Verifica tensiunea bateriei la pornire.",
        "Verifica turatia motorului la demaror.",
        "Verifica presiunea combustibilului.",
        "Verifica senzorii de turatie si sincronizare.",
        "Verifica bujiile incandescente la motoarele diesel."
    ],
    "Motorul se supraincalzeste": [
        "Opreste motorul daca temperatura este in zona periculoasa.",
        "Nu deschide capacul vasului de expansiune cat timp sistemul este fierbinte.",
        "Verifica nivelul lichidului numai dupa racire.",
        "Verifica ventilatorul, termostatul si radiatorul.",
        "Verifica eventualele pierderi si functionarea pompei de apa."
    ],
    "Martor Check Engine aprins": [
        "Citeste codurile de eroare cu un tester compatibil.",
        "Noteaza codurile inainte de stergere.",
        "Verifica daca exista simptome asociate.",
        "Nu inlocui piese doar pe baza unui singur cod.",
        "Dupa reparatie, verifica daca eroarea revine."
    ],
    "Vibratii la acceleratie": [
        "Verifica suporturile motorului si transmisiei.",
        "Verifica planetarele si articulatiile.",
        "Verifica rotile si anvelopele.",
        "Verifica rateurile motorului sub sarcina.",
        "Verifica transmisia daca vibratia depinde de treapta de viteza."
    ],
    "Fum excesiv la evacuare": [
        "Noteaza culoarea fumului si conditiile in care apare.",
        "Verifica nivelul uleiului si al lichidului de racire.",
        "Verifica injectia si admisia.",
        "La diesel, verifica sistemul de supraalimentare si DPF, daca exista.",
        "Nu continua deplasarea daca apar zgomote grave sau supraincalzire."
    ]
}


def get_symptom_recommendations(symptom):
    """Returneaza pasii orientativi pentru un simptom."""
    return SYMPTOM_GUIDE.get(symptom, [])


# ============================================================
# 4. DIAGNOSTICARE AVANSATA – PID OBD-II
# ============================================================

OBD_PID_REFERENCE = [
    {
        "pid": "01 0C",
        "name": "Turatie motor",
        "unit": "rpm",
        "formula": "(A*256+B)/4",
        "description": "Turatia motorului raportata de ECU."
    },
    {
        "pid": "01 0D",
        "name": "Viteza vehiculului",
        "unit": "km/h",
        "formula": "A",
        "description": "Viteza raportata de ECU."
    },
    {
        "pid": "01 05",
        "name": "Temperatura lichidului de racire",
        "unit": "°C",
        "formula": "A-40",
        "description": "Temperatura raportata de senzorul de racire."
    },
    {
        "pid": "01 0F",
        "name": "Temperatura aerului admis",
        "unit": "°C",
        "formula": "A-40",
        "description": "Temperatura aerului admis raportata de ECU."
    },
    {
        "pid": "01 11",
        "name": "Pozitie clapeta acceleratie",
        "unit": "%",
        "formula": "A*100/255",
        "description": "Pozitia clapetei raportata prin PID."
    },
    {
        "pid": "01 10",
        "name": "Debit aer MAF",
        "unit": "g/s",
        "formula": "(A*256+B)/100",
        "description": "Debit masic de aer raportat de ECU."
    },
    {
        "pid": "01 06",
        "name": "Corectie combustibil STFT Bank 1",
        "unit": "%",
        "formula": "(A-128)*100/128",
        "description": "Corectie pe termen scurt a amestecului."
    },
    {
        "pid": "01 07",
        "name": "Corectie combustibil LTFT Bank 1",
        "unit": "%",
        "formula": "(A-128)*100/128",
        "description": "Corectie pe termen lung a amestecului."
    },
    {
        "pid": "01 0B",
        "name": "Presiune absoluta admisie",
        "unit": "kPa",
        "formula": "A",
        "description": "Presiunea absoluta raportata de MAP."
    },
    {
        "pid": "01 0E",
        "name": "Avans aprindere",
        "unit": "grade",
        "formula": "A/2-64",
        "description": "Avansul raportat de ECU."
    },
    {
        "pid": "01 42",
        "name": "Tensiune modul de control",
        "unit": "V",
        "formula": "(A*256+B)/1000",
        "description": "Tensiunea raportata de ECU."
    }
]


def get_obd_pid_reference():
    return pd.DataFrame(OBD_PID_REFERENCE)


def calculate_obd_pid(pid, byte_a, byte_b=0):
    """
    Calculeaza valorile pentru cativa PID standard.
    Valorile A si B trebuie introduse ca numere zecimale 0-255.
    """
    pid = clean_text(pid).upper()

    a = safe_float(byte_a)
    b = safe_float(byte_b, 0)

    if a is None or b is None:
        return None, "Introdu valori numerice valide."

    if not (0 <= a <= 255 and 0 <= b <= 255):
        return None, "Valorile A si B trebuie sa fie intre 0 si 255."

    if pid == "01 0C":
        return (a * 256 + b) / 4, "rpm"

    if pid == "01 0D":
        return a, "km/h"

    if pid in ("01 05", "01 0F"):
        return a - 40, "°C"

    if pid == "01 11":
        return a * 100 / 255, "%"

    if pid == "01 10":
        return (a * 256 + b) / 100, "g/s"

    if pid in ("01 06", "01 07"):
        return (a - 128) * 100 / 128, "%"

    if pid == "01 0B":
        return a, "kPa"

    if pid == "01 0E":
        return a / 2 - 64, "grade"

    if pid == "01 42":
        return (a * 256 + b) / 1000, "V"

    return None, "PID-ul nu este inclus in calculatorul simplificat."


# ============================================================
# 5. IMPORT FISIERE CSV CU LOGURI OBD
# ============================================================

def normalize_obd_csv(df):
    """
    Normalizeaza un fisier CSV incarcat de utilizator.
    Nu presupune un format unic al testerului.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()

    result.columns = [
        re.sub(
            r"[^a-z0-9_]",
            "_",
            str(column).strip().lower()
        )
        for column in result.columns
    ]

    return result


def import_obd_csv(uploaded_file):
    """Citeste un fisier CSV incarcat din aplicatie."""
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            uploaded_file,
            sep=None,
            engine="python",
            encoding="utf-8-sig"
        )

        return normalize_obd_csv(df)

    except Exception as exc:
        st.error(f"Nu am putut citi fisierul CSV: {exc}")
        return pd.DataFrame()


def save_obd_measurements(df, vehicle="", engine="", notes=""):
    """
    Salveaza masuratorile CSV in baza locala.
    Fiecare rand importat este pastrat ca date brute.
    """
    if df is None or df.empty:
        return 0

    saved = 0

    for _, row in df.iterrows():
        row_data = row.to_dict()

        pid = (
            row_data.get("pid")
            or row_data.get("parameter_id")
            or row_data.get("mode_pid")
            or ""
        )

        parameter = (
            row_data.get("parameter")
            or row_data.get("name")
            or row_data.get("description")
            or row_data.get("sensor")
            or ""
        )

        value = (
            row_data.get("value")
            or row_data.get("reading")
            or row_data.get("measurement")
            or ""
        )

        unit = (
            row_data.get("unit")
            or row_data.get("units")
            or ""
        )

        add_local_record(
            "obd_measurements",
            {
                "vehicle": clean_text(vehicle),
                "engine": clean_text(engine),
                "measurement_date": now_text(),
                "pid": clean_text(pid),
                "parameter_name": clean_text(parameter),
                "measured_value": clean_text(value),
                "unit": clean_text(unit),
                "notes": clean_text(notes)
            }
        )

        saved += 1

    return saved


# ============================================================
# 6. ISTORIC SI STATISTICI LOCALE
# ============================================================

def get_repair_statistics():
    """Statistici despre cazurile de reparatie salvate."""
    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM repair_cases"
        ).fetchone()[0]

        successful = conn.execute(
            """
            SELECT COUNT(*)
            FROM repair_cases
            WHERE LOWER(COALESCE(result, '')) LIKE '%rezolvat%'
               OR LOWER(COALESCE(result, '')) LIKE '%reparat%'
               OR LOWER(COALESCE(result, '')) LIKE '%succes%'
            """
        ).fetchone()[0]

        return {
            "total": total,
            "successful": successful
        }

    finally:
        conn.close()


def get_recent_repair_cases(limit=10):
    return get_local_table("repair_cases", limit=limit)


def get_recent_obd_measurements(limit=100):
    return get_local_table("obd_measurements", limit=limit)


def get_maintenance_count():
    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        return conn.execute(
            "SELECT COUNT(*) FROM maintenance_records"
        ).fetchone()[0]

    finally:
        conn.close()


def get_parts_count():
    conn = get_db_connection(LOCAL_DB_PATH)

    try:
        return conn.execute(
            "SELECT COUNT(*) FROM parts_records"
        ).fetchone()[0]

    finally:
        conn.close()


# ============================================================
# 7. VALIDAREA DATELOR INTRODUSE
# ============================================================

def validate_year(year):
    year = safe_int(year)

    if year is None:
        return None

    if year < 1886 or year > datetime.now().year + 2:
        return None

    return year


def validate_mileage(mileage):
    mileage = safe_int(mileage)

    if mileage is None:
        return None

    if mileage < 0 or mileage > 2_000_000:
        return None

    return mileage


def validate_interval(value, maximum=2_000_000):
    value = safe_int(value)

    if value is None:
        return None

    if value < 0 or value > maximum:
        return None

    return value


def validate_source_url(url):
    """Accepta numai URL-uri HTTP sau HTTPS."""
    url = clean_text(url)

    if not url:
        return ""

    if url.startswith("https://") or url.startswith("http://"):
        return url

    return ""


# ============================================================
# 8. CONECTARE OPTIONALA LA OPEN LABOR PROJECT
# ============================================================

def open_labor_project_request(api_key, endpoint, params=None):
    """
    Functie generica pentru apeluri API.
    Nu presupune endpoint-uri specifice.
    Endpoint-ul trebuie sa fie furnizat conform documentatiei
    oficiale Open Labor Project.
    """
    api_key = clean_text(api_key)
    endpoint = clean_text(endpoint)

    if not api_key:
        return None, "Introdu cheia API."

    if not endpoint.startswith("https://"):
        return None, "Endpoint-ul trebuie sa inceapa cu https://."

    if not endpoint.startswith("https://openlaborproject.com/"):
        return None, "Endpoint-ul nu apartine domeniului oficial."

    if params:
        from urllib.parse import urlencode

        separator = "&" if "?" in endpoint else "?"
        endpoint += separator + urlencode(params)

    request = urllib.request.Request(
        endpoint,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "AutoDiagnosisPro/1.0"
        }
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=25
        ) as response:
            content = response.read().decode("utf-8")
            return json.loads(content), "Solicitare reusita."

    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            message = "Cheia API nu este acceptata."
        elif exc.code == 403:
            message = "Accesul la aceasta resursa este restrictionat."
        elif exc.code == 429:
            message = "Limita de solicitari API a fost atinsa."
        else:
            message = f"Eroare API HTTP: {exc.code}"

        return None, message

    except Exception as exc:
        return None, f"Eroare la conectarea API: {exc}"


# ============================================================
# 9. EXPORT DATE LOCALE
# ============================================================

def export_local_table_csv(table_name):
    """Pregateste un tabel local pentru descarcare CSV."""
    allowed_tables = {
        "repair_cases",
        "maintenance_records",
        "parts_records",
        "workshop_reference",
        "obd_measurements",
        "data_sources",
        "diagnosis_records"
    }

    if table_name not in allowed_tables:
        return None

    df = get_local_table(table_name, limit=100000)

    if df.empty:
        return None

    return df.to_csv(
        index=False,
        encoding="utf-8-sig"
    ).encode("utf-8-sig")


# ============================================================
# SFARSIT PARTEA 2 DIN 4
# Urmeaza: interfata utilizator si paginile aplicatiei.
# ============================================================

# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 3 DIN 4 – INTERFATA SI MODULELE PRINCIPALE
# ============================================================


# ============================================================
# 1. MENIU SI CONFIGURARE INTERFATA
# ============================================================

PAGES = [
    "🏠 Dashboard",
    "🔎 Diagnosticare DTC",
    "📚 Cautare coduri DTC",
    "🚘 Cautare vehicule",
    "⚙️ Date tehnice motor",
    "🛠️ Intretinere si service",
    "📊 Diagnosticare avansata OBD"
]


def page_header(title, description=""):
    st.title(title)

    if description:
        st.caption(description)

    st.divider()


def show_database_status():
    """Afiseaza starea bazelor de date."""
    status_items = [
        ("Coduri DTC", DTC_DB_PATH),
        ("Vehicule", VEHICLES_DB_PATH),
        ("Motoare", ENGINES_DB_PATH),
        ("Date locale", LOCAL_DB_PATH)
    ]

    cols = st.columns(4)

    for col, (label, path) in zip(cols, status_items):
        with col:
            if Path(path).exists():
                st.success(f"{label}: disponibil")
            else:
                st.warning(f"{label}: lipsa")


# ============================================================
# 2. DASHBOARD
# ============================================================

def page_dashboard():
    page_header(
        "Auto Diagnosis Pro",
        "Platforma de diagnosticare, informatii tehnice si evidenta reparatiilor."
    )

    st.markdown(
        """
        <div class="app-note">
        Aplicatia reuneste informatii despre coduri DTC, vehicule,
        motorizari, intretinere, diagnoza OBD si cazuri de reparatii.
        Datele tehnice trebuie confirmate pentru vehiculul concret.
        </div>
        """,
        unsafe_allow_html=True
    )

    dtc_stats = get_dtc_statistics()
    repair_stats = get_repair_statistics()

    maintenance_count = get_maintenance_count()
    parts_count = get_parts_count()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Coduri DTC in baza",
        f"{dtc_stats['total']:,}"
    )

    c2.metric(
        "Producatori DTC",
        f"{dtc_stats['manufacturers']:,}"
    )

    c3.metric(
        "Cazuri reparatii",
        repair_stats["total"]
    )

    c4.metric(
        "Inregistrari service",
        maintenance_count
    )

    st.subheader("Module disponibile")

    modules = [
        ("🔎", "Diagnosticare DTC", "Identificarea codurilor de eroare."),
        ("🚘", "Vehicule", "Cautare dupa marca si model."),
        ("⚙️", "Motoare", "Generatii si variante de motorizare."),
        ("🛠️", "Intretinere", "Evidenta operatiunilor de service."),
        ("📊", "Diagnoza OBD", "Valori PID si fisiere CSV."),
        ("🔧", "Piese", "Catalog local si compatibilitate documentata."),
        ("📋", "Reparatii", "Istoric de interventii."),
        ("📖", "Documentatie", "Informatii tehnice si surse.")
    ]

    cols = st.columns(4)

    for index, module in enumerate(modules):
        with cols[index % 4]:
            st.markdown(f"### {module[0]} {module[1]}")
            st.caption(module[2])

    st.subheader("Starea bazelor de date")
    show_database_status()

    st.subheader("Ultimele cazuri de reparatii")

    recent = get_recent_repair_cases(5)

    if recent.empty:
        st.info("Nu exista inca reparatii salvate.")
    else:
        display_columns = [
            column for column in [
                "id",
                "repair_date",
                "make",
                "model",
                "year",
                "engine",
                "dtc_codes",
                "result"
            ]
            if column in recent.columns
        ]

        st.dataframe(
            recent[display_columns],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 3. DIAGNOSTICARE DTC
# ============================================================

def page_dtc_diagnosis():
    page_header(
        "Diagnosticare DTC",
        "Introdu un cod OBD-II pentru a cauta explicatii si posibile cauze."
    )

    code_input = st.text_input(
        "Cod de eroare",
        placeholder="Exemplu: P0300",
        max_chars=10
    )

    if st.button("🔍 Cauta codul", type="primary"):
        code = normalize_dtc(code_input)

        if not code:
            st.error("Cod invalid. Introdu un cod de forma P0300.")
            return

        st.session_state["selected_dtc"] = code

    code = st.session_state.get("selected_dtc", "")

    if not code:
        st.info("Introdu un cod DTC pentru a incepe.")
        return

    st.subheader(f"Rezultate pentru {code}")

    results = combined_dtc_search(code)

    local = results["local"]
    database = results["database"]
    mechanicdb = results["mechanicdb"]

    if local:
        st.markdown("### Diagnostic local")

        st.markdown(f"**{local.get('title', '')}**")

        st.write("**Cauze posibile:**")
        st.write(local.get("possible_causes", "Nu exista date."))

        st.write("**Simptome:**")
        st.write(local.get("symptoms", "Nu exista date."))

        st.write("**Verificari recomandate:**")
        st.write(local.get("checks", "Nu exista date."))

        st.write("**Recomandari de reparatie:**")
        st.write(
            local.get(
                "repair_suggestions",
                "Nu exista date."
            )
        )

        st.caption(
            "Sursa: "
            + clean_text(local.get("source"))
            + " | Nivel: "
            + clean_text(local.get("confidence"))
        )

    if not database.empty:
        st.markdown("### Informatii din baza DTC")

        st.dataframe(
            database,
            use_container_width=True,
            hide_index=True
        )

    if not mechanicdb.empty:
        st.markdown("### Proceduri din MechanicDB")

        st.caption(
            "Mostra publica MechanicDB. "
            "Verifica aplicabilitatea procedurii pentru vehicul."
        )

        st.dataframe(
            mechanicdb,
            use_container_width=True,
            hide_index=True
        )

    if not local and database.empty and mechanicdb.empty:
        st.warning(
            "Nu am gasit informatii pentru acest cod in sursele disponibile."
        )

    st.divider()

    st.subheader("Salveaza diagnosticul intr-un caz de reparatie")

    if st.button("Deschide formularul de reparatie"):
        st.session_state["repair_prefill_dtc"] = code
        st.session_state["active_page"] = "📋 Cazuri de reparatii"
        st.rerun()

    st.markdown(
        """
        <div class="warning-note">
        Un cod DTC indica o problema detectata de calculatorul vehiculului.
        Nu identifica automat piesa defecta. Confirma diagnosticul prin
        masuratori si verificari specifice modelului.
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 4. CAUTARE CODURI DTC
# ============================================================

def page_dtc_search():
    page_header(
        "Cautare coduri DTC",
        "Cauta dupa cod, descriere sau producator."
    )

    search_term = st.text_input(
        "Cod sau cuvant de cautare",
        placeholder="Exemplu: P0420, catalyst, oxygen sensor"
    )

    manufacturer_options = ["Toti producatorii"] + get_dtc_manufacturers()

    manufacturer = st.selectbox(
        "Producator",
        manufacturer_options
    )

    if st.button("Cauta in baza DTC", type="primary"):
        if not clean_text(search_term):
            st.warning("Introdu un termen de cautare.")
        else:
            df = search_dtc_database(search_term, limit=300)

            if (
                not df.empty
                and manufacturer != "Toti producatorii"
            ):
                manufacturer_col = find_existing_column(
                    list(df.columns),
                    ["manufacturer", "make", "brand"]
                )

                if manufacturer_col:
                    df = df[
                        df[manufacturer_col].astype(str)
                        == manufacturer
                    ]

            st.session_state["dtc_search_results"] = df

    results = st.session_state.get(
        "dtc_search_results",
        pd.DataFrame()
    )

    if not results.empty:
        st.success(f"Au fost gasite {len(results)} rezultate.")

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        csv_data = results.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Descarca rezultatele CSV",
            csv_data,
            file_name="dtc_search_results.csv",
            mime="text/csv"
        )

    elif "dtc_search_results" in st.session_state:
        st.info("Nu au fost gasite rezultate.")


# ============================================================
# 5. CAUTARE VEHICULE
# ============================================================

def page_vehicle_search():
    page_header(
        "Cautare vehicule",
        "Cauta marci si modele in catalogul VehiclesDB."
    )

    status, message = get_vehicle_database_status()

    if not status:
        st.warning(message)

        if st.button("Descarca baza VehiclesDB"):
            success, download_message = ensure_external_database(
                VEHICLES_DB_PATH,
                VEHICLES_DB_URL,
                ["makes", "models"]
            )

            if success:
                st.success(download_message)
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error(download_message)

        return

    makes = get_vehicle_makes()

    if not makes:
        st.warning("Nu am putut identifica marcile din baza.")
        return

    col1, col2 = st.columns(2)

    with col1:
        selected_make = st.selectbox(
            "Marca",
            ["Toate"] + makes
        )

    with col2:
        model_search = st.text_input(
            "Model",
            placeholder="Exemplu: Golf, Focus, Corolla"
        )

    general_search = st.text_input(
        "Cautare suplimentara",
        placeholder="Cuvant din denumire sau categorie"
    )

    if st.button("Cauta vehicule", type="primary"):
        df = search_vehicles(
            make="" if selected_make == "Toate" else selected_make,
            model=model_search,
            search_term=general_search,
            limit=500
        )

        st.session_state["vehicle_results"] = df

    results = st.session_state.get(
        "vehicle_results",
        pd.DataFrame()
    )

    if not results.empty:
        st.success(f"Rezultate: {len(results)}")

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        csv_data = results.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Descarca vehicule CSV",
            csv_data,
            file_name="vehicle_results.csv",
            mime="text/csv"
        )

    elif "vehicle_results" in st.session_state:
        st.info("Nu am gasit vehicule pentru criteriile introduse.")


# ============================================================
# 6. DATE TEHNICE MOTOR
# ============================================================

def page_engine_data():
    page_header(
        "Date tehnice motor",
        "Cauta variante de motorizare, generatii si specificatii."
    )

    status, message = get_engine_database_status()

    if not status:
        st.warning(message)

        if st.button("Descarca baza de motoare"):
            success, download_message = ensure_external_database(
                ENGINES_DB_PATH,
                ENGINES_DB_URL,
                ["makes", "models", "generations", "engines"]
            )

            if success:
                st.success(download_message)
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error(download_message)

        return

    makes = get_engine_makes()

    if not makes:
        st.warning("Nu am putut identifica marcile.")
        return

    col1, col2 = st.columns(2)

    with col1:
        make = st.selectbox(
            "Marca",
            ["Toate"] + makes,
            key="engine_make"
        )

    with col2:
        model = st.text_input(
            "Model",
            placeholder="Exemplu: A4, 320d, Civic",
            key="engine_model"
        )

    col3, col4 = st.columns(2)

    with col3:
        year = st.number_input(
            "An de fabricatie",
            min_value=1886,
            max_value=datetime.now().year + 2,
            value=2020,
            step=1
        )

    with col4:
        engine_search = st.text_input(
            "Cod sau denumire motor",
            placeholder="Exemplu: 2.0 TDI, N47, K9K"
        )

    use_year = st.checkbox(
        "Filtreaza si dupa an",
        value=False
    )

    if st.button("Cauta motorizari", type="primary"):
        df = search_engine_catalog(
            make="" if make == "Toate" else make,
            model=model,
            year=int(year) if use_year else None,
            engine_search=engine_search,
            limit=500
        )

        st.session_state["engine_results"] = df

    results = st.session_state.get(
        "engine_results",
        pd.DataFrame()
    )

    if not results.empty:
        st.success(
            f"Au fost gasite {len(results)} variante."
        )

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        csv_data = results.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Descarca datele motoarelor",
            csv_data,
            file_name="engine_results.csv",
            mime="text/csv"
        )

        engine_id_column = find_existing_column(
            list(results.columns),
            ["engine_id"]
        )

        if engine_id_column:
            engine_ids = results[engine_id_column].dropna().tolist()

            if engine_ids:
                selected_engine_id = st.selectbox(
                    "Selecteaza motorul pentru specificatii suplimentare",
                    engine_ids
                )

                specs = get_engine_specs(selected_engine_id)

                if not specs.empty:
                    st.subheader("Specificatii suplimentare")
                    st.dataframe(
                        specs,
                        use_container_width=True,
                        hide_index=True
                    )

    elif "engine_results" in st.session_state:
        st.info("Nu au fost gasite motorizari.")


# ============================================================
# 7. INTRETINERE SI SERVICE
# ============================================================

def page_maintenance():
    page_header(
        "Intretinere si service",
        "Creeaza un registru de operatiuni si intervale de service."
    )

    st.markdown(
        """
        <div class="app-note">
        Aplicatia nu inventeaza intervale de service.
        Introdu intervalele numai dupa verificarea documentatiei
        producatorului sau a unei surse tehnice de incredere.
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("➕ Adauga o operatiune de intretinere", expanded=True):
        with st.form("maintenance_form"):
            c1, c2 = st.columns(2)

            with c1:
                make = st.text_input("Marca")
                model = st.text_input("Model")
                year_from = st.number_input(
                    "An inceput",
                    min_value=1886,
                    max_value=datetime.now().year + 2,
                    value=2015
                )

                year_to = st.number_input(
                    "An sfarsit",
                    min_value=1886,
                    max_value=datetime.now().year + 2,
                    value=2020
                )

                engine = st.text_input("Motorizare")

            with c2:
                operation = st.text_input(
                    "Operatiune",
                    placeholder="Exemplu: schimb ulei motor"
                )

                interval_km = st.number_input(
                    "Interval kilometri",
                    min_value=0,
                    max_value=2_000_000,
                    value=0
                )

                interval_months = st.number_input(
                    "Interval luni",
                    min_value=0,
                    max_value=600,
                    value=0
                )

                specification = st.text_input(
                    "Specificatie tehnica",
                    placeholder="Exemplu: norma ulei"
                )

                quantity = st.text_input(
                    "Cantitate",
                    placeholder="Exemplu: 4.5 L"
                )

            source_name = st.text_input("Sursa informatiei")
            source_url = st.text_input("Link sursa")
            confidence = st.selectbox(
                "Nivel verificare",
                [
                    "Neverificat",
                    "Sursa producator",
                    "Sursa tehnica verificata",
                    "Date introduse de utilizator"
                ]
            )

            notes = st.text_area("Observatii")

            submitted = st.form_submit_button(
                "Salveaza operatiunea",
                type="primary"
            )

            if submitted:
                if not operation.strip():
                    st.error("Introdu denumirea operatiunii.")
                elif year_to < year_from:
                    st.error("Anul de sfarsit nu poate fi mai mic.")
                else:
                    add_local_record(
                        "maintenance_records",
                        {
                            "make": make,
                            "model": model,
                            "year_from": int(year_from),
                            "year_to": int(year_to),
                            "engine": engine,
                            "operation": operation,
                            "interval_km": int(interval_km) or None,
                            "interval_months": int(interval_months) or None,
                            "specification": specification,
                            "quantity": quantity,
                            "source_name": source_name,
                            "source_url": validate_source_url(source_url),
                            "confidence": confidence,
                            "notes": notes,
                            "created_at": now_text()
                        }
                    )

                    st.success("Operatiunea a fost salvata.")
                    st.rerun()

    st.subheader("Registru de intretinere")

    maintenance = get_local_table(
        "maintenance_records",
        limit=1000
    )

    if maintenance.empty:
        st.info("Nu exista operatiuni salvate.")
    else:
        search = st.text_input(
            "Filtreaza operatiunile",
            key="maintenance_filter"
        )

        if search:
            mask = maintenance.astype(str).apply(
                lambda column: column.str.contains(
                    re.escape(search),
                    case=False,
                    na=False
                )
            ).any(axis=1)

            maintenance = maintenance.loc[mask]

        st.dataframe(
            maintenance,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Export registru CSV",
            maintenance.to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="maintenance_records.csv",
            mime="text/csv"
        )

    st.divider()

    st.subheader("Stergere inregistrare")

    maintenance = get_local_table(
        "maintenance_records",
        limit=1000
    )

    if not maintenance.empty:
        record_id = st.number_input(
            "ID operatiune",
            min_value=1,
            step=1,
            key="delete_maintenance_id"
        )

        if st.button("Sterge operatiunea selectata"):
            try:
                delete_local_record(
                    "maintenance_records",
                    record_id
                )
                st.success("Inregistrarea a fost stearsa.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


# ============================================================
# 8. DIAGNOSTICARE AVANSATA OBD
# ============================================================

def page_advanced_obd():
    page_header(
        "Diagnosticare avansata OBD",
        "Introdu valori PID sau importa loguri din testerul auto."
    )

    st.markdown(
        """
        <div class="warning-note">
        Aplicatia ruleaza in cloud si nu se poate conecta direct la
        adaptorul Bluetooth sau USB ELM327 al masinii.
        Pentru conectare live va fi necesara o aplicatie locala
        intermediara. In acest modul poti introduce valori manual
        sau importa fisiere CSV exportate de tester.
        </div>
        """,
        unsafe_allow_html=True
    )

    tabs = st.tabs([
        "Calculator PID",
        "Referinta PID",
        "Import CSV",
        "Istoric masuratori"
    ])

    with tabs[0]:
        st.subheader("Calculator valori PID")

        pid_options = [
            item["pid"] + " – " + item["name"]
            for item in OBD_PID_REFERENCE
        ]

        selected = st.selectbox(
            "Selecteaza PID",
            pid_options
        )

        pid = selected.split(" – ")[0]

        col1, col2 = st.columns(2)

        with col1:
            byte_a = st.number_input(
                "Byte A",
                min_value=0,
                max_value=255,
                value=0
            )

        with col2:
            byte_b = st.number_input(
                "Byte B",
                min_value=0,
                max_value=255,
                value=0
            )

        if st.button("Calculeaza valoarea PID"):
            result, unit = calculate_obd_pid(
                pid,
                byte_a,
                byte_b
            )

            if result is None:
                st.error(unit)
            else:
                st.metric(
                    "Valoare calculata",
                    f"{result:.2f} {unit}"
                )

                st.caption(
                    "Rezultat calculat conform formulei PID standard."
                )

    with tabs[1]:
        st.subheader("Lista PID-uri standard")

        pid_df = get_obd_pid_reference()

        st.dataframe(
            pid_df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "PID-urile disponibile depind de ECU si de compatibilitatea vehiculului."
        )

    with tabs[2]:
        st.subheader("Import log OBD CSV")

        vehicle = st.text_input(
            "Vehicul",
            placeholder="Exemplu: Volkswagen Golf 7"
        )

        engine = st.text_input(
            "Motorizare",
            placeholder="Exemplu: 2.0 TDI"
        )

        uploaded_file = st.file_uploader(
            "Alege fisierul CSV exportat de tester",
            type=["csv"]
        )

        notes = st.text_area(
            "Observatii despre sesiunea de diagnoza"
        )

        if uploaded_file is not None:
            imported = import_obd_csv(uploaded_file)

            if not imported.empty:
                st.success(
                    f"Fisier citit: {len(imported)} randuri."
                )

                st.dataframe(
                    imported.head(100),
                    use_container_width=True,
                    hide_index=True
                )

                if st.button("Salveaza masuratorile importate"):
                    count = save_obd_measurements(
                        imported,
                        vehicle=vehicle,
                        engine=engine,
                        notes=notes
                    )

                    st.success(
                        f"Au fost salvate {count} masuratori."
                    )

    with tabs[3]:
        st.subheader("Istoric masuratori")

        history = get_recent_obd_measurements(500)

        if history.empty:
            st.info("Nu exista masuratori salvate.")
        else:
            st.dataframe(
                history,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "Descarca istoricul CSV",
                history.to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name="obd_measurements.csv",
                mime="text/csv"
            )


# ============================================================
# SFARSIT PARTEA 3 DIN 4
# Urmeaza: piese, compatibilitate, reparatii,
# documentatie tehnica si administrarea surselor.
# ============================================================

# ============================================================
# PARTEA 4/4 - PIESE, REPARATII, DOCUMENTATIE SI MENIU FINAL
# ============================================================

from datetime import date
from pathlib import Path
import sqlite3


# ------------------------------------------------------------
# CONEXIUNI SQLITE
# Deschide o conexiune noua la fiecare utilizare.
# Evita reutilizarea conexiunilor inchise din cache.
# ------------------------------------------------------------

def get_external_db(db_path):
    path = Path(db_path)

    if not path.exists():
        return None

    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True, check_same_thread=False)
    except Exception:
        return None


# ------------------------------------------------------------
# UTILITARE
# ------------------------------------------------------------

def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def valid_source_url(url):
    url = safe_text(url).lower()
    return url.startswith("https://") or url.startswith("http://")


def show_local_records(table_name, title):
    st.subheader(title)

    try:
        records = get_local_table(table_name)

        if records is None or records.empty:
            st.info("Nu exista inregistrari salvate.")
            return records

        st.dataframe(records, use_container_width=True, hide_index=True)
        return records

    except Exception as exc:
        st.warning(f"Nu am putut incarca inregistrarile: {exc}")
        return None


def export_dataframe_csv(dataframe, filename, button_label):
    if dataframe is None or dataframe.empty:
        st.info("Nu exista date pentru export.")
        return

    csv_data = dataframe.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        button_label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=True
    )


# ------------------------------------------------------------
# MODUL PIESE SI COMPATIBILITATE
# ------------------------------------------------------------

def page_parts():
    st.title("🔧 Piese si compatibilitate")
    st.caption(
        "Catalog local de piese. Compatibilitatea trebuie verificata "
        "dupa codul OEM, VIN si configuratia exacta a vehiculului."
    )

    with st.expander("➕ Adauga o piesa noua", expanded=True):
        with st.form("add_part_form", clear_on_submit=True):

            col1, col2 = st.columns(2)

            with col1:
                part_number = st.text_input("Cod piesa")
                oem_number = st.text_input("Cod OEM")
                brand = st.text_input("Producator piesa")
                category = st.selectbox(
                    "Categorie",
                    [
                        "Motor",
                        "Filtre",
                        "Frane",
                        "Suspensie",
                        "Directie",
                        "Transmisie",
                        "Electric",
                        "Racire",
                        "Caroserie",
                        "Consumabile",
                        "Altele"
                    ]
                )

            with col2:
                make = st.text_input("Marca vehicul")
                model = st.text_input("Model vehicul")
                year_range = st.text_input("Ani compatibili")
                engine = st.text_input("Motor / cod motor")

            description = st.text_area("Descriere piesa")

            compatibility = st.selectbox(
                "Statut compatibilitate",
                [
                    "Neverificata",
                    "Verificata dupa cod OEM",
                    "Verificata dupa VIN",
                    "Confirmata de producator"
                ]
            )

            source_name = st.text_input("Sursa informatiei")
            source_url = st.text_input("Link sursa")
            notes = st.text_area("Observatii")

            submitted = st.form_submit_button(
                "Salveaza piesa",
                use_container_width=True
            )

            if submitted:
                if not part_number and not oem_number:
                    st.error("Introdu cel putin codul piesei sau codul OEM.")
                elif source_url and not valid_source_url(source_url):
                    st.error("Linkul trebuie sa inceapa cu http:// sau https://.")
                else:
                    record = {
                        "part_number": part_number,
                        "oem_number": oem_number,
                        "brand": brand,
                        "category": category,
                        "description": description,
                        "make": make,
                        "model": model,
                        "year_range": year_range,
                        "engine": engine,
                        "compatibility": compatibility,
                        "source_name": source_name,
                        "source_url": source_url,
                        "notes": notes
                    }

                    try:
                        add_local_record("parts_records", record)
                        st.success("Piesa a fost salvata.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Eroare la salvare: {exc}")

    st.divider()
    st.subheader("🔍 Cauta in catalogul local")

    search = st.text_input(
        "Cod piesa, OEM, marca, model sau descriere",
        key="parts_search"
    )

    try:
        parts = get_local_table("parts_records")

        if parts is not None and not parts.empty:
            filtered = parts.copy()

            if search:
                mask = filtered.astype(str).apply(
                    lambda column: column.str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ).any(axis=1)

                filtered = filtered[mask]

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True
            )

            export_dataframe_csv(
                filtered,
                "catalog_piese.csv",
                "Descarca catalogul de piese"
            )

            if "id" in filtered.columns and not filtered.empty:
                ids = filtered["id"].astype(str).tolist()

                selected_id = st.selectbox(
                    "Selecteaza ID-ul piesei pentru stergere",
                    [""] + ids,
                    key="delete_part_id"
                )

                if st.button("Sterge piesa selectata", key="delete_part"):
                    if selected_id:
                        delete_local_record(
                            "parts_records",
                            int(selected_id)
                        )
                        st.success("Piesa a fost stearsa.")
                        st.rerun()
        else:
            st.info("Catalogul local este gol.")

    except Exception as exc:
        st.warning(f"Catalogul nu poate fi afisat: {exc}")

    st.warning(
        "Important: prezenta unei piese in catalog nu confirma automat "
        "compatibilitatea. Verifica intotdeauna codul OEM, VIN-ul, "
        "motorizarea si eventualele diferente de echipare."
    )


# ------------------------------------------------------------
# MODUL CAZURI DE REPARATII
# ------------------------------------------------------------

def page_repairs():
    st.title("📋 Cazuri de reparatii")
    st.caption(
        "Istoric de defecte, diagnostic confirmat, lucrari efectuate "
        "si rezultate."
    )

    prefill_dtc = st.session_state.get("repair_prefill_dtc", "")

    with st.expander("➕ Inregistreaza un caz nou", expanded=True):
        with st.form("add_repair_form", clear_on_submit=True):

            col1, col2 = st.columns(2)

            with col1:
                repair_date = st.date_input(
                    "Data reparatiei",
                    value=date.today()
                )
                make = st.text_input("Marca")
                model = st.text_input("Model")
                year = st.text_input("An fabricatie")

            with col2:
                engine = st.text_input("Motor / cod motor")
                mileage = st.number_input(
                    "Kilometraj",
                    min_value=0,
                    step=1000
                )
                dtc_codes = st.text_input(
                    "Coduri DTC",
                    value=prefill_dtc
                )

            symptoms = st.text_area("Simptome reclamate")
            confirmed_cause = st.text_area("Cauza confirmata")
            repair_performed = st.text_area("Reparatia efectuata")
            parts_used = st.text_area("Piese utilizate")
            result = st.selectbox(
                "Rezultatul reparatiei",
                [
                    "Nedeterminat",
                    "Rezolvat",
                    "Rezolvat partial",
                    "Defect persistent",
                    "Necesita verificari suplimentare"
                ]
            )
            notes = st.text_area("Observatii suplimentare")

            submitted = st.form_submit_button(
                "Salveaza cazul",
                use_container_width=True
            )

            if submitted:
                record = {
                    "repair_date": str(repair_date),
                    "make": make,
                    "model": model,
                    "year": year,
                    "engine": engine,
                    "mileage": mileage,
                    "dtc_codes": dtc_codes,
                    "symptoms": symptoms,
                    "confirmed_cause": confirmed_cause,
                    "repair_performed": repair_performed,
                    "parts_used": parts_used,
                    "result": result,
                    "notes": notes
                }

                try:
                    add_local_record("repair_cases", record)
                    st.session_state["repair_prefill_dtc"] = ""
                    st.success("Cazul de reparatie a fost salvat.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Eroare la salvare: {exc}")

    st.divider()
    st.subheader("📚 Istoric reparatii")

    try:
        repairs = get_local_table("repair_cases")

        if repairs is None or repairs.empty:
            st.info("Nu exista cazuri de reparatii salvate.")
            return

        search = st.text_input(
            "Cauta dupa marca, model, motor, DTC sau simptom",
            key="repair_search"
        )

        filtered = repairs.copy()

        if search:
            mask = filtered.astype(str).apply(
                lambda column: column.str.contains(
                    search,
                    case=False,
                    na=False
                )
            ).any(axis=1)

            filtered = filtered[mask]

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            filtered,
            "istoric_reparatii.csv",
            "Descarca istoricul reparatiilor"
        )

        if "id" in repairs.columns:
            st.divider()
            st.subheader("✏️ Editeaza sau sterge un caz")

            ids = repairs["id"].astype(str).tolist()

            selected_id = st.selectbox(
                "Selecteaza cazul",
                [""] + ids,
                key="repair_selected_id"
            )

            if selected_id:
                selected = repairs[
                    repairs["id"].astype(str) == selected_id
                ].iloc[0]

                with st.form("edit_repair_form"):
                    st.write(f"Editezi cazul cu ID {selected_id}")

                    edit_cause = st.text_area(
                        "Cauza confirmata",
                        value=safe_text(
                            selected.get("confirmed_cause", "")
                        )
                    )

                    edit_work = st.text_area(
                        "Reparatia efectuata",
                        value=safe_text(
                            selected.get("repair_performed", "")
                        )
                    )

                    edit_parts = st.text_area(
                        "Piese utilizate",
                        value=safe_text(
                            selected.get("parts_used", "")
                        )
                    )

                    edit_result = st.text_input(
                        "Rezultatul reparatiei",
                        value=safe_text(selected.get("result", ""))
                    )

                    edit_notes = st.text_area(
                        "Observatii",
                        value=safe_text(selected.get("notes", ""))
                    )

                    save_edit = st.form_submit_button(
                        "Salveaza modificarile"
                    )

                    if save_edit:
                        update_local_record(
                            "repair_cases",
                            int(selected_id),
                            {
                                "confirmed_cause": edit_cause,
                                "repair_performed": edit_work,
                                "parts_used": edit_parts,
                                "result": edit_result,
                                "notes": edit_notes
                            }
                        )

                        st.success("Modificarile au fost salvate.")
                        st.rerun()

                if st.button(
                    "Sterge cazul selectat",
                    key="delete_repair"
                ):
                    delete_local_record(
                        "repair_cases",
                        int(selected_id)
                    )
                    st.success("Cazul a fost sters.")
                    st.rerun()

    except Exception as exc:
        st.error(f"Eroare la afisarea istoricului: {exc}")


# ------------------------------------------------------------
# MODUL DOCUMENTATIE TEHNICA
# ------------------------------------------------------------

def page_workshop_reference():
    st.title("📖 Documentatie tehnica")
    st.caption(
        "Fisa tehnica locala pentru informatii de service, "
        "proceduri si referinte de atelier."
    )

    with st.expander("➕ Adauga informatie tehnica", expanded=True):
        with st.form("add_workshop_reference", clear_on_submit=True):

            col1, col2 = st.columns(2)

            with col1:
                make = st.text_input("Marca")
                model = st.text_input("Model")
                year = st.text_input("An / generatie")
                engine = st.text_input("Motor / cod motor")

            with col2:
                subject = st.selectbox(
                    "Subiect",
                    [
                        "Cupluri de strangere",
                        "Uleiuri si fluide",
                        "Distributie",
                        "Sistem de franare",
                        "Sistem electric",
                        "Scheme electrice",
                        "Procedura reparatie",
                        "Intervale service",
                        "Altele"
                    ]
                )

                confidence = st.selectbox(
                    "Nivel de incredere",
                    [
                        "Neverificat",
                        "Sursa secundara",
                        "Documentatie producator",
                        "Documentatie oficiala de service"
                    ]
                )

            information = st.text_area(
                "Informatii tehnice",
                height=180
            )

            source_name = st.text_input("Numele sursei")
            source_url = st.text_input("Link catre documentatie")
            license_info = st.text_input("Licenta / drept de utilizare")

            safety_warning = st.text_area(
                "Avertismente de siguranta"
            )

            submitted = st.form_submit_button(
                "Salveaza documentatia",
                use_container_width=True
            )

            if submitted:
                if not information.strip():
                    st.error("Introdu informatia tehnica.")
                elif source_url and not valid_source_url(source_url):
                    st.error("Linkul trebuie sa fie HTTP sau HTTPS.")
                else:
                    record = {
                        "make": make,
                        "model": model,
                        "year": year,
                        "engine": engine,
                        "subject": subject,
                        "information": information,
                        "source_name": source_name,
                        "source_url": source_url,
                        "license_info": license_info,
                        "confidence": confidence,
                        "safety_warning": safety_warning
                    }

                    try:
                        add_local_record(
                            "workshop_reference",
                            record
                        )
                        st.success("Informatia a fost salvata.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Eroare la salvare: {exc}")

    st.divider()
    st.subheader("📚 Biblioteca tehnica")

    try:
        references = get_local_table("workshop_reference")

        if references is None or references.empty:
            st.info("Biblioteca tehnica este goala.")
            return

        search = st.text_input(
            "Cauta in documentatie",
            key="reference_search"
        )

        filtered = references.copy()

        if search:
            mask = filtered.astype(str).apply(
                lambda column: column.str.contains(
                    search,
                    case=False,
                    na=False
                )
            ).any(axis=1)

            filtered = filtered[mask]

        for _, item in filtered.iterrows():
            title_text = (
                f"{safe_text(item.get('make'))} "
                f"{safe_text(item.get('model'))} - "
                f"{safe_text(item.get('subject'))}"
            )

            with st.expander(title_text):
                st.write(
                    "**Motor:**",
                    safe_text(item.get("engine"))
                )
                st.write(
                    "**An / generatie:**",
                    safe_text(item.get("year"))
                )
                st.write(
                    "**Nivel de incredere:**",
                    safe_text(item.get("confidence"))
                )
                st.write(
                    "**Informatii:**",
                    safe_text(item.get("information"))
                )
                st.write(
                    "**Sursa:**",
                    safe_text(item.get("source_name"))
                )

                url = safe_text(item.get("source_url"))

                if url and valid_source_url(url):
                    st.markdown(f"[Deschide sursa]({url})")

                st.write(
                    "**Licenta:**",
                    safe_text(item.get("license_info"))
                )

                warning = safe_text(
                    item.get("safety_warning")
                )

                if warning:
                    st.warning(warning)

        export_dataframe_csv(
            filtered,
            "documentatie_tehnica.csv",
            "Descarca documentatia"
        )

        if "id" in references.columns:
            ids = references["id"].astype(str).tolist()

            delete_id = st.selectbox(
                "ID informatie pentru stergere",
                [""] + ids,
                key="delete_reference_id"
            )

            if st.button(
                "Sterge informatia selectata",
                key="delete_reference"
            ):
                if delete_id:
                    delete_local_record(
                        "workshop_reference",
                        int(delete_id)
                    )
                    st.success("Informatia a fost stearsa.")
                    st.rerun()

    except Exception as exc:
        st.error(f"Eroare la biblioteca tehnica: {exc}")

    st.warning(
        "Nu folosi valori de cuplu, presiuni, fluide, scheme electrice "
        "sau proceduri de reparatie fara verificarea sursei si a "
        "configuratiei exacte a vehiculului."
    )

    st.error(
        "Atentie: sistemele airbag/SRS si circuitele de inalta tensiune "
        "ale vehiculelor hibride sau electrice necesita proceduri "
        "speciale si personal calificat."
    )


# ------------------------------------------------------------
# MODUL BAZE DE DATE SI SURSE
# ------------------------------------------------------------

def database_status(name, path):
    exists = Path(path).exists()

    if exists:
        size_mb = Path(path).stat().st_size / (1024 * 1024)

        st.success(
            f"{name}: disponibil ({size_mb:.2f} MB)"
        )
    else:
        st.warning(f"{name}: nu este instalat")

    return exists


def inspect_database(path):
    connection = get_external_db(path)

    if connection is None:
        st.info("Baza de date nu este disponibila.")
        return

    try:
        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """,
            connection
        )

        st.dataframe(
            tables,
            use_container_width=True,
            hide_index=True
        )

    except Exception as exc:
        st.warning(f"Nu am putut inspecta baza de date: {exc}")

    finally:
        connection.close()


def page_database_sources():
    st.title("🗄️ Baze de date si surse")
    st.caption(
        "Verifica bazele de date disponibile si descarca seturile "
        "de date externe."
    )

    st.subheader("📦 Starea bazelor de date")

    database_status(
        "Baza de date DTC",
        DTC_DB_PATH
    )

    database_status(
        "Catalog VehiclesDB",
        VEHICLES_DB_PATH
    )

    database_status(
        "Catalog motoare si generatii",
        ENGINES_DB_PATH
    )

    st.divider()
    st.subheader("⬇️ Descarcare baze de date")

    st.write(
        "Descarcarile se fac numai cand apesi butonul. "
        "Prima descarcare poate dura in functie de conexiunea la internet."
    )

    if st.button(
        "Descarca / actualizeaza VehiclesDB",
        use_container_width=True
    ):
        with st.spinner("Se descarca baza VehiclesDB..."):
            try:
                ensure_external_database(
                    VEHICLES_DB_PATH,
                    VEHICLES_DB_URL,
                    required_tables=["makes", "models"]
                )
                st.success("Catalogul VehiclesDB este disponibil.")
                st.rerun()
            except Exception as exc:
                st.error(f"Descarcarea a esuat: {exc}")

    if st.button(
        "Descarca / actualizeaza catalogul de motoare",
        use_container_width=True
    ):
        with st.spinner("Se descarca baza de date pentru motoare..."):
            try:
                ensure_external_database(
                    ENGINES_DB_PATH,
                    ENGINES_DB_URL,
                    required_tables=[
                        "makes",
                        "models",
                        "generations",
                        "engines"
                    ]
                )
                st.success("Catalogul de motoare este disponibil.")
                st.rerun()
            except Exception as exc:
                st.error(f"Descarcarea a esuat: {exc}")

    st.divider()
    st.subheader("🔍 Structura bazelor de date")

    with st.expander("VehiclesDB"):
        inspect_database(VEHICLES_DB_PATH)

    with st.expander("Catalog motoare"):
        inspect_database(ENGINES_DB_PATH)

    with st.expander("Baza de date DTC"):
        inspect_database(DTC_DB_PATH)

    st.divider()
    st.subheader("📚 Surse si licente")

    st.markdown(
        """
        **DTC Database**
        - Proiect: [Wal33D/dtc-database](https://github.com/Wal33D/dtc-database)
        - Verifica licenta si conditiile proiectului original inainte
          de redistribuire.

        **VehiclesDB**
        - Proiect: [vehiclesdb/vehiclesdb](https://github.com/vehiclesdb/vehiclesdb)
        - Licenta: CC BY 4.0.
        - Necesita atribuire si mentionarea modificarilor, daca exista.

        **Vehicle Makes, Models and Engines**
        - Proiect: [gor3a/vehicle-makes-models](https://github.com/gor3a/vehicle-makes-models)
        - Licenta: ODbL 1.0.
        - Respecta cerintele de atribuire si share-alike aplicabile.

        **MechanicDB**
        - Proiect: [MechanicDB](https://github.com/)
        - Verifica sursa exacta si licenta fisierelor importate.
        - Nu redistribui date fara verificarea conditiilor licentei.
        """
    )

    st.info(
        "Bazele de date externe pot avea structuri si versiuni diferite. "
        "Aplicatia incearca sa identifice tabelele necesare, dar nu "
        "garanteaza ca toate campurile sunt disponibile."
    )

    st.divider()
    st.subheader("🧾 Surse adaugate manual")

    try:
        sources = get_local_table("data_sources")

        if sources is not None and not sources.empty:
            st.dataframe(
                sources,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nu ai adaugat surse manuale.")

    except Exception as exc:
        st.warning(f"Nu am putut afisa sursele: {exc}")


# ------------------------------------------------------------
# MENIUL FINAL AL APLICATIEI
# ------------------------------------------------------------

PAGES = [
    "🏠 Dashboard",
    "🔎 Diagnosticare DTC",
    "📚 Cautare coduri DTC",
    "🚘 Cautare vehicule",
    "⚙️ Date tehnice motor",
    "🛠️ Intretinere si service",
    "📊 Diagnosticare avansata OBD",
    "🔧 Piese si compatibilitate",
    "📋 Cazuri de reparatii",
    "📖 Documentatie tehnica",
    "🗄️ Baze de date si surse"
]


def main():

    st.set_page_config(
        page_title="Auto Diagnosis Pro",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if "active_page" not in st.session_state:
        st.session_state["active_page"] = PAGES[0]

    current_page = st.session_state.get(
        "active_page",
        PAGES[0]
    )

    if current_page not in PAGES:
        current_page = PAGES[0]



    st.sidebar.title("🚗 Auto Diagnosis Pro")
    st.sidebar.caption("Platforma de diagnosticare auto")

    selected_page = st.sidebar.radio(
        "Meniu principal",
        PAGES,
        key="main_navigation"
    )

    st.session_state["active_page"] = selected_page

    st.sidebar.divider()

    st.sidebar.caption(
        "Instrument de asistenta pentru diagnosticare. "
        "Nu inlocuieste documentatia oficiala si verificarile "
        "efectuate de un tehnician calificat."
    )

    if st.sidebar.button(
        "Reincarca aplicatia",
        use_container_width=True
    ):
        st.cache_resource.clear()
        st.rerun()

    # --------------------------------------------------------
    # RUTARE PAGINI
    # --------------------------------------------------------

    if selected_page == "🏠 Dashboard":
        page_dashboard()

    elif selected_page == "🔎 Diagnosticare DTC":
        page_dtc_diagnosis()

    elif selected_page == "📚 Cautare coduri DTC":
        page_dtc_search()

    elif selected_page == "🚘 Cautare vehicule":
        page_vehicle_search()

    elif selected_page == "⚙️ Date tehnice motor":
        page_engine_data()

    elif selected_page == "🛠️ Intretinere si service":
        page_maintenance()

    elif selected_page == "📊 Diagnosticare avansata OBD":
        page_advanced_obd()

    elif selected_page == "🔧 Piese si compatibilitate":
        page_parts()

    elif selected_page == "📋 Cazuri de reparatii":
        page_repairs()

    elif selected_page == "📖 Documentatie tehnica":
        page_workshop_reference()

    elif selected_page == "🗄️ Baze de date si surse":
        page_database_sources()


# ------------------------------------------------------------
# PORNIRE APLICATIE
# ------------------------------------------------------------

if __name__ == "__main__":
    main()
