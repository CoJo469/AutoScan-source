
# ============================================================
# AUTO DIAGNOSIS PRO
# VERSIUNE NOUA - PARTEA 1/4
# FUNDATIE, CONFIGURARE, BAZE DE DATE
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
import requests
import json
import csv
import io
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime, date
from urllib.parse import quote

st.set_page_config(
    page_title="Auto Diagnosis Pro",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CONFIGURARE GENERALA
# ============================================================

APP_NAME = "Auto Diagnosis Pro"
APP_VERSION = "2.0"

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

# Baza DTC externa (SQLite) si mostrele publice MechanicDB.
DTC_DB_URL = (
    "https://raw.githubusercontent.com/Wal33D/dtc-database/"
    "main/data/dtc_codes.db"
)
MECHANICDB_DIR = DATA_DIR / "mechanicdb"
MECHANICDB_DIR.mkdir(exist_ok=True)
MECHANICDB_FIXES_PATH = MECHANICDB_DIR / "dtc_fixes_joined.csv"
MECHANICDB_PARTS_PATH = MECHANICDB_DIR / "replacement_parts.csv"
MECHANICDB_FIXES_URL = (
    "https://raw.githubusercontent.com/MechanicDB/MechanicDB-public/"
    "main/dtc_fixes_joined.csv"
)
MECHANICDB_PARTS_URL = (
    "https://raw.githubusercontent.com/MechanicDB/MechanicDB-public/"
    "main/replacement_parts.csv"
)

# Baza explicativa OBDEX: 9.533 coduri OBD-II generice cu cauze, simptome si estimari.
OBDEX_JSON_URL = "https://foerbsnavi.github.io/OBDex/generic.min.json"
OBDEX_PATH = DATA_DIR / "obdex_generic.json"

# ============================================================
# INTERFATA
# ============================================================

st.markdown("""
<style>
.main {
    background-color: #101820;
}
.block-container {
    padding-top: 1.5rem;
}
[data-testid="stSidebar"] {
    background-color: #17232e;
}
div[data-testid="stMetric"] {
    background-color: #1d2b38;
    padding: 15px;
    border-radius: 10px;
}
.stButton button {
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# FUNCTII GENERALE
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_text(value):
    return clean_text(value).casefold()


def safe_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def quote_identifier(identifier):
    """
    Protejeaza identificatorii SQL.
    """

    return '"' + str(identifier).replace('"', '""') + '"'


def valid_url(url):
    return clean_text(url).startswith(
        ("https://", "http://")
    )


def format_number(value):
    try:
        return f"{int(value):,}".replace(",", " ")
    except (ValueError, TypeError):
        return "0"


def page_header(title, description=""):
    st.title(title)

    if description:
        st.caption(description)

    st.divider()


# ============================================================
# BAZA DE DATE LOCALA
# ============================================================

def get_local_connection():
    conn = sqlite3.connect(
        str(LOCAL_DB_PATH),
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def initialize_local_database():

    conn = get_local_connection()

    conn.executescript("""

    CREATE TABLE IF NOT EXISTS repair_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repair_date TEXT,
        make TEXT,
        model TEXT,
        year TEXT,
        generation TEXT,
        engine TEXT,
        mileage INTEGER,
        dtc_codes TEXT,
        symptoms TEXT,
        confirmed_cause TEXT,
        repair_performed TEXT,
        parts_used TEXT,
        result TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS maintenance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        make TEXT,
        model TEXT,
        year TEXT,
        engine TEXT,
        maintenance_type TEXT,
        mileage INTEGER,
        interval_km INTEGER,
        interval_months INTEGER,
        description TEXT,
        source TEXT,
        source_url TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        year_range TEXT,
        engine TEXT,
        compatibility TEXT,
        source_name TEXT,
        source_url TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS workshop_reference (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        make TEXT,
        model TEXT,
        year TEXT,
        engine TEXT,
        subject TEXT,
        information TEXT,
        source_name TEXT,
        source_url TEXT,
        license_info TEXT,
        confidence TEXT,
        safety_warning TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS obd_measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle TEXT,
        engine TEXT,
        pid TEXT,
        measurement TEXT,
        value REAL,
        unit TEXT,
        recorded_at TEXT,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS data_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT,
        license_info TEXT,
        attribution TEXT,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dtc_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle TEXT,
        engine TEXT,
        dtc_code TEXT,
        description TEXT,
        diagnosis TEXT,
        repair TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS diagnosis_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dtc_code TEXT NOT NULL UNIQUE,
        title TEXT,
        possible_causes TEXT,
        symptoms TEXT,
        checks TEXT,
        repair_suggestions TEXT,
        source TEXT,
        confidence TEXT DEFAULT 'Orientativ',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    """)

    seed_records = [
        ("P0300", "Rateuri de aprindere detectate aleatoriu sau pe mai multi cilindri",
         "Bujii uzate, bobine, injectoare, presiune combustibil, admisie falsa sau compresie scazuta.",
         "Motorul poate tremura, poate pierde putere sau poate functiona neregulat.",
         "Verifica bujiile si bobinele; citeste contoarele de rateuri pe cilindri; verifica corectiile de combustibil, presiunea si compresia.",
         "Identifica cilindrii afectati si confirma cauza prin masuratori inainte de inlocuirea pieselor."),
        ("P0171", "Amestec prea sarac – Bank 1",
         "Aer fals pe admisie, debitmetru MAF, presiune combustibil scazuta, injectoare sau evacuare neetansa inaintea sondei.",
         "Ralanti instabil, ezitari, putere redusa sau consum modificat.",
         "Verifica furtunurile si garniturile de admisie; compara valorile MAF; analizeaza STFT/LTFT si masoara presiunea combustibilului.",
         "Localizeaza cauza amestecului sarac si verifica din nou corectiile de combustibil dupa reparatie."),
        ("P0420", "Eficienta sistemului catalitic sub prag – Bank 1",
         "Catalizator degradat, senzori lambda, scapari pe evacuare sau probleme de functionare ale motorului.",
         "Martor Check Engine si uneori consum sau performanta modificate.",
         "Verifica scapari pe evacuare, semnalele sondelor lambda si eventualele rateuri sau amestec incorect.",
         "Nu inlocui catalizatorul inainte de a verifica sondele, scaparea pe evacuare si cauzele care pot deteriora catalizatorul."),
        ("P0128", "Temperatura lichidului de racire sub temperatura de reglare",
         "Termostat blocat deschis, senzor de temperatura sau probleme la circuitul de racire.",
         "Incalzire lenta a motorului sau temperatura de functionare neobisnuit de scazuta.",
         "Compara temperatura ECT la rece cu temperatura ambientala si urmareste cresterea temperaturii in mers.",
         "Verifica termostatul si senzorul ECT; confirma valorile cu datele specifice motorului inainte de inlocuire."),
        ("P0101", "Performanta sau plauzibilitate debitmetru MAF – domeniu/performance",
         "MAF murdar sau defect, admisie neetansa, filtru de aer obturat sau cablaj/conector deteriorat.",
         "Putere redusa, ralanti instabil sau raspuns slab la acceleratie.",
         "Verifica filtrul de aer si traseul de admisie; inspecteaza mufele; compara debitul MAF masurat cu valorile asteptate pentru motor.",
         "Confirma cauza prin inspectie si masuratori; nu rezolva problema doar prin stergerea codului.")
    ]

    for record in seed_records:
        conn.execute(
            """
            INSERT OR IGNORE INTO diagnosis_records (
                dtc_code, title, possible_causes, symptoms, checks,
                repair_suggestions, source, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            record + ("Baza interna Auto Diagnosis Pro", "Orientativ")
        )

    conn.commit()
    conn.close()


initialize_local_database()


# ============================================================
# ADAUGARE, EDITARE SI STERGERE INREGISTRARI
# ============================================================

ALLOWED_TABLES = {
    "repair_cases",
    "maintenance_records",
    "parts_records",
    "workshop_reference",
    "obd_measurements",
    "data_sources",
    "dtc_history"
}


def add_local_record(table_name, record):

    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabel nepermis.")

    if not record:
        raise ValueError("Nu exista date de salvat.")

    conn = get_local_connection()

    columns = list(record.keys())

    query = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(quote_identifier(c) for c in columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})"
    )

    conn.execute(
        query,
        list(record.values())
    )

    conn.commit()
    conn.close()


def update_local_record(table_name, record_id, changes):

    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabel nepermis.")

    if not changes:
        return

    conn = get_local_connection()

    assignments = ", ".join(
        f"{quote_identifier(column)} = ?"
        for column in changes
    )

    query = (
        f"UPDATE {quote_identifier(table_name)} "
        f"SET {assignments} WHERE id = ?"
    )

    conn.execute(
        query,
        list(changes.values()) + [record_id]
    )

    conn.commit()
    conn.close()


def delete_local_record(table_name, record_id):

    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabel nepermis.")

    conn = get_local_connection()

    conn.execute(
        f"DELETE FROM {quote_identifier(table_name)} WHERE id = ?",
        (record_id,)
    )

    conn.commit()
    conn.close()


def get_local_table(table_name):

    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabel nepermis.")

    conn = get_local_connection()

    df = pd.read_sql_query(
        f"SELECT * FROM {quote_identifier(table_name)} ORDER BY id DESC",
        conn
    )

    conn.close()

    return df


# ============================================================
# CONEXIUNI LA BAZELE EXTERNE
# ============================================================

def get_external_db(db_path):

    path = Path(db_path)

    if not path.exists():
        return None

    try:
        uri = path.resolve().as_uri() + "?mode=ro"

        return sqlite3.connect(
            uri,
            uri=True,
            check_same_thread=False
        )

    except Exception:
        return None


def table_exists(conn, table_name):

    result = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND lower(name)=lower(?)
        """,
        (table_name,)
    ).fetchone()

    return result is not None


def get_database_tables(db_path):

    conn = get_external_db(db_path)

    if conn is None:
        return []

    try:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """
        ).fetchall()

        return [row[0] for row in rows]

    finally:
        conn.close()


def get_table_columns(conn, table_name):

    rows = conn.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()

    return [row[1] for row in rows]


def find_existing_column(columns, candidates):

    lookup = {
        str(column).lower(): column
        for column in columns
    }

    for candidate in candidates:

        if candidate.lower() in lookup:
            return lookup[candidate.lower()]

    return None


# ============================================================
# DESCARCARE BAZE DE DATE
# ============================================================

def download_database(url, destination):

    destination = Path(destination)
    temporary = destination.with_suffix(".download")

    try:

        with requests.get(
            url,
            stream=True,
            timeout=(20, 300)
        ) as response:

            response.raise_for_status()

            with open(temporary, "wb") as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

        if temporary.stat().st_size == 0:
            raise ValueError("Fisierul descarcat este gol.")

        # Verifica daca fisierul este o baza SQLite valida.
        test_conn = sqlite3.connect(str(temporary))

        integrity = test_conn.execute(
            "PRAGMA quick_check"
        ).fetchone()

        test_conn.close()

        if not integrity or integrity[0] != "ok":
            raise ValueError("Baza de date descarcata nu este valida.")

        os.replace(temporary, destination)

        return True, "Baza de date a fost descarcata cu succes."

    except Exception as exc:

        if temporary.exists():
            temporary.unlink()

        return False, str(exc)


def ensure_external_database(
    destination,
    url,
    required_tables=None
):

    destination = Path(destination)

    if destination.exists():

        conn = get_external_db(destination)

        if conn is not None:

            try:
                tables = {
                    table.lower()
                    for table in get_database_tables(destination)
                }

                required = {
                    table.lower()
                    for table in (required_tables or [])
                }

                if required.issubset(tables):
                    conn.close()

                    return True, "Baza de date exista si este valida."

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    success, message = download_database(
        url,
        destination
    )

    if not success:
        return False, message

    if required_tables:

        tables = {
            table.lower()
            for table in get_database_tables(destination)
        }

        missing = [
            table for table in required_tables
            if table.lower() not in tables
        ]

        if missing:
            return False, (
                "Lipsesc tabelele necesare: "
                + ", ".join(missing)
            )

    return True, message


# ============================================================
# IDENTIFICAREA BAZELOR
# ============================================================

def get_vehicle_database_status():

    if not VEHICLES_DB_PATH.exists():
        return False, "Catalogul VehiclesDB nu este instalat."

    tables = {
        table.lower()
        for table in get_database_tables(VEHICLES_DB_PATH)
    }

    if not {"makes", "models"}.issubset(tables):
        return False, "Catalogul nu contine tabelele necesare."

    return True, "Catalogul VehiclesDB este disponibil."


def get_engine_database_status():

    if not ENGINES_DB_PATH.exists():
        return False, "Catalogul de motoare nu este instalat."

    tables = {
        table.lower()
        for table in get_database_tables(ENGINES_DB_PATH)
    }

    required = {
        "makes",
        "models",
        "generations",
        "engines"
    }

    if not required.issubset(tables):
        return False, "Catalogul de motoare este incomplet."

    return True, "Catalogul de motoare este disponibil."


# ============================================================
# CITIRE DINAMICA A MARCILOR
# ============================================================

def get_vehicle_makes():

    conn = get_external_db(VEHICLES_DB_PATH)

    if conn is None:
        return []

    try:

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
            f"AND TRIM({quote_identifier(name_col)}) != '' "
            f"ORDER BY {quote_identifier(name_col)}"
        )

        rows = conn.execute(query).fetchall()

        return [row[0] for row in rows]

    except Exception as exc:

        st.error(f"Eroare la citirea marcilor: {exc}")
        return []

    finally:
        conn.close()


# ============================================================
# STATISTICI BAZE DE DATE
# ============================================================

def get_table_count(db_path, table_name):

    conn = get_external_db(db_path)

    if conn is None:
        return 0

    try:

        if not table_exists(conn, table_name):
            return 0

        result = conn.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
        ).fetchone()

        return int(result[0])

    except Exception:
        return 0

    finally:
        conn.close()


def get_database_statistics():

    return {
        "marci": get_table_count(
            VEHICLES_DB_PATH,
            "makes"
        ),
        "modele": get_table_count(
            VEHICLES_DB_PATH,
            "models"
        ),
        "generatii": get_table_count(
            ENGINES_DB_PATH,
            "generations"
        ),
        "motoare": get_table_count(
            ENGINES_DB_PATH,
            "engines"
        )
    }


# ============================================================
# EXPORT CSV
# ============================================================

def export_dataframe_csv(
    dataframe,
    filename,
    label="Descarca CSV"
):

    if dataframe is None or dataframe.empty:
        st.info("Nu exista date pentru export.")
        return

    csv_data = dataframe.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=True
    )


# ============================================================
# FINAL PARTEA 1/4
# ============================================================

# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 2/4 - CATALOG, MOTOARE, DTC SI OBD
# ============================================================


# ============================================================
# CAUTARE VEHICULE FARA LIMITA IMPLICITA
# ============================================================

def search_vehicles(make="", model="", search_term="", limit=None):

    conn = get_external_db(VEHICLES_DB_PATH)

    if conn is None:
        return pd.DataFrame()

    try:
        if not table_exists(conn, "models"):
            return pd.DataFrame()

        model_columns = get_table_columns(conn, "models")

        make_columns = (
            get_table_columns(conn, "makes")
            if table_exists(conn, "makes")
            else []
        )

        model_name = find_existing_column(
            model_columns, ["name", "model", "title"]
        )

        model_make_id = find_existing_column(
            model_columns, ["make_id", "manufacturer_id"]
        )

        make_id = find_existing_column(
            make_columns, ["id", "make_id"]
        )

        make_name = find_existing_column(
            make_columns, ["name", "make", "title", "brand"]
        )

        if not model_name:
            return pd.DataFrame()

        join_makes = bool(
            model_make_id and make_id and make_name
        )

        select_parts = [
            f'm.{quote_identifier(c)} AS '
            f'{quote_identifier("model_" + c)}'
            for c in model_columns
        ]

        sql = "SELECT " + ", ".join(select_parts) + " FROM models m"

        if join_makes:
            sql += (
                f" LEFT JOIN makes mk ON "
                f"m.{quote_identifier(model_make_id)} = "
                f"mk.{quote_identifier(make_id)}"
            )
            sql = sql.replace(
                " FROM models m",
                f', mk.{quote_identifier(make_name)} AS make_name '
                "FROM models m",
                1
            )

        conditions = []
        params = []

        if make and join_makes:
            conditions.append(
                f"mk.{quote_identifier(make_name)} = ?"
            )
            params.append(make)

        if model:
            conditions.append(
                f"CAST(m.{quote_identifier(model_name)} AS TEXT) LIKE ?"
            )
            params.append(f"%{model}%")

        if search_term:
            searchable = [
                c for c in model_columns
                if c.lower() not in ("id",)
            ]

            term_conditions = []

            for column in searchable:
                term_conditions.append(
                    f"CAST(m.{quote_identifier(column)} AS TEXT) LIKE ?"
                )
                params.append(f"%{search_term}%")

            if join_makes:
                term_conditions.append(
                    f"CAST(mk.{quote_identifier(make_name)} AS TEXT) LIKE ?"
                )
                params.append(f"%{search_term}%")

            if term_conditions:
                conditions.append(
                    "(" + " OR ".join(term_conditions) + ")"
                )

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += f" ORDER BY m.{quote_identifier(model_name)}"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        return pd.read_sql_query(sql, conn, params=params)

    except Exception as exc:
        st.error(f"Eroare catalog vehicule: {exc}")
        return pd.DataFrame()

    finally:
        conn.close()


# ============================================================
# CAUTARE DINAMICA IN ORICE TABEL
# ============================================================

def search_database_table(db_path, table_name, search_term=""):

    conn = get_external_db(db_path)

    if conn is None:
        return pd.DataFrame()

    try:
        if not table_exists(conn, table_name):
            return pd.DataFrame()

        columns = get_table_columns(conn, table_name)

        if not columns:
            return pd.DataFrame()

        sql = f"SELECT * FROM {quote_identifier(table_name)}"
        params = []

        if search_term:
            conditions = []

            for column in columns:
                conditions.append(
                    f"CAST({quote_identifier(column)} AS TEXT) LIKE ?"
                )
                params.append(f"%{search_term}%")

            sql += " WHERE " + " OR ".join(conditions)

        sql += " ORDER BY 1"

        return pd.read_sql_query(sql, conn, params=params)

    except Exception as exc:
        st.error(f"Eroare la cautarea in {table_name}: {exc}")
        return pd.DataFrame()

    finally:
        conn.close()


# ============================================================
# CAUTARE GENERATII SI MOTOARE
# ============================================================

def search_engine_catalog(
    make="",
    model="",
    year="",
    fuel="",
    engine_search=""
):

    conn = get_external_db(ENGINES_DB_PATH)

    if conn is None:
        return pd.DataFrame()

    try:
        required = ["makes", "models", "generations", "engines"]

        if not all(table_exists(conn, t) for t in required):
            return pd.DataFrame()

        tables = {
            name: get_table_columns(conn, name)
            for name in required
        }

        # Identifica legaturile dintre tabele.
        make_id = find_existing_column(
            tables["makes"], ["id", "make_id"]
        )
        make_name = find_existing_column(
            tables["makes"], ["name", "make", "title"]
        )

        model_id = find_existing_column(
            tables["models"], ["id", "model_id"]
        )
        model_name = find_existing_column(
            tables["models"], ["name", "model", "title"]
        )
        model_make_id = find_existing_column(
            tables["models"], ["make_id", "manufacturer_id"]
        )

        gen_id = find_existing_column(
            tables["generations"], ["id", "generation_id"]
        )
        gen_model_id = find_existing_column(
            tables["generations"], ["model_id"]
        )

        engine_gen_id = find_existing_column(
            tables["engines"], ["generation_id"]
        )

        if not all([
            make_id, make_name, model_id, model_name,
            model_make_id, gen_id, gen_model_id,
            engine_gen_id
        ]):
            return pd.DataFrame()

        select = []

        for table in required:
            alias = {
                "makes": "mk",
                "models": "mo",
                "generations": "g",
                "engines": "e"
            }[table]

            for column in tables[table]:
                select.append(
                    f'{alias}.{quote_identifier(column)} '
                    f'AS {quote_identifier(table + "_" + column)}'
                )

        sql = (
            "SELECT " + ", ".join(select)
            + f" FROM makes mk"
            + f" JOIN models mo ON "
            f"mo.{quote_identifier(model_make_id)} = "
            f"mk.{quote_identifier(make_id)}"
            + f" JOIN generations g ON "
            f"g.{quote_identifier(gen_model_id)} = "
            f"mo.{quote_identifier(model_id)}"
            + f" JOIN engines e ON "
            f"e.{quote_identifier(engine_gen_id)} = "
            f"g.{quote_identifier(gen_id)}"
        )

        conditions = []
        params = []

        if make:
            conditions.append(
                f"CAST(mk.{quote_identifier(make_name)} AS TEXT) LIKE ?"
            )
            params.append(f"%{make}%")

        if model:
            conditions.append(
                f"CAST(mo.{quote_identifier(model_name)} AS TEXT) LIKE ?"
            )
            params.append(f"%{model}%")

        if year:
            requested_year = safe_int(year)

            start_column = find_existing_column(
                tables["generations"],
                [
                    "year_start", "start_year", "year_from",
                    "from_year", "production_start", "production_start_year"
                ]
            )
            end_column = find_existing_column(
                tables["generations"],
                [
                    "year_end", "end_year", "year_to",
                    "to_year", "production_end", "production_end_year"
                ]
            )
            single_year_column = find_existing_column(
                tables["generations"],
                [
                    "year", "model_year", "production_year",
                    "generation_year"
                ]
            )

            if requested_year is not None and start_column and end_column:
                start_sql = f"CAST(g.{quote_identifier(start_column)} AS INTEGER)"
                end_sql = f"CAST(g.{quote_identifier(end_column)} AS INTEGER)"
                end_text = f"LOWER(TRIM(CAST(g.{quote_identifier(end_column)} AS TEXT)))"
                conditions.append(
                    f"({start_sql} <= ? AND ("
                    f"g.{quote_identifier(end_column)} IS NULL OR "
                    f"TRIM(CAST(g.{quote_identifier(end_column)} AS TEXT)) = '' OR "
                    f"{end_sql} >= ? OR {end_text} IN ('present', 'current', 'ongoing')))"
                )
                params.extend([requested_year, requested_year])

            elif single_year_column:
                conditions.append(
                    f"CAST(g.{quote_identifier(single_year_column)} AS TEXT) LIKE ?"
                )
                params.append(f"%{year}%")

            else:
                # Compatibilitate cu scheme care folosesc alte nume de coloane.
                year_columns = [
                    c for c in tables["generations"]
                    if any(x in c.lower() for x in [
                        "year", "start", "end", "from", "to"
                    ])
                ]

                if year_columns:
                    year_conditions = []
                    for column in year_columns:
                        year_conditions.append(
                            f"CAST(g.{quote_identifier(column)} AS TEXT) LIKE ?"
                        )
                        params.append(f"%{year}%")

                    conditions.append(
                        "(" + " OR ".join(year_conditions) + ")"
                    )

        if fuel:
            fuel_column = find_existing_column(
                tables["engines"],
                ["fuel_type", "fuel", "fuelType", "fuel_name"]
            )

            if fuel_column:
                fuel_aliases = {
                    "petrol": ["petrol", "gasoline", "gas", "benzin", "benzina", "essence"],
                    "gasoline": ["petrol", "gasoline", "gas", "benzin", "benzina", "essence"],
                    "diesel": ["diesel", "gasoil"],
                    "hybrid": ["hybrid", "hev", "phev", "mild hybrid"],
                    "electric": ["electric", "bev", "ev"],
                    "lpg": ["lpg", "autogas"],
                    "cng": ["cng", "natural gas", "methane"]
                }
                normalized_fuel = normalize_text(fuel)
                aliases = fuel_aliases.get(normalized_fuel, [normalized_fuel])
                fuel_conditions = []

                for alias in aliases:
                    fuel_conditions.append(
                        f"LOWER(CAST(e.{quote_identifier(fuel_column)} AS TEXT)) LIKE ?"
                    )
                    params.append(f"%{alias}%")

                conditions.append(
                    "(" + " OR ".join(fuel_conditions) + ")"
                )

        if engine_search:
            engine_conditions = []

            for column in tables["engines"]:
                engine_conditions.append(
                    f"CAST(e.{quote_identifier(column)} AS TEXT) LIKE ?"
                )
                params.append(f"%{engine_search}%")

            conditions.append(
                "(" + " OR ".join(engine_conditions) + ")"
            )

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += (
            f" ORDER BY mk.{quote_identifier(make_name)}, "
            f"mo.{quote_identifier(model_name)}"
        )

        return pd.read_sql_query(sql, conn, params=params)

    except Exception as exc:
        st.error(f"Eroare catalog motoare: {exc}")
        return pd.DataFrame()

    finally:
        conn.close()


# ============================================================
# CAUTARE CODURI DTC
# ============================================================

def find_dtc_table():

    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return None, None

    try:
        tables = get_database_tables(DTC_DB_PATH)

        for table in tables:
            columns = get_table_columns(conn, table)

            code_col = find_existing_column(
                columns,
                ["code", "dtc", "dtc_code", "trouble_code"]
            )

            if code_col:
                return table, columns

        return None, None

    finally:
        conn.close()


def search_dtc(code="", search_term=""):

    conn = get_external_db(DTC_DB_PATH)

    if conn is None:
        return pd.DataFrame()

    try:
        tables = get_database_tables(DTC_DB_PATH)
        frames = []

        for table in tables:
            columns = get_table_columns(conn, table)
            code_col = find_existing_column(
                columns,
                ["code", "dtc", "dtc_code", "trouble_code"]
            )
            if not code_col:
                continue

            conditions = []
            params = []
            if code:
                conditions.append(
                    f"UPPER(CAST({quote_identifier(code_col)} AS TEXT)) LIKE ?"
                )
                params.append(f"%{code.upper().strip()}%")

            if search_term:
                searchable = [c for c in columns if c != code_col]
                if searchable:
                    parts = []
                    for column in searchable:
                        parts.append(
                            f"CAST({quote_identifier(column)} AS TEXT) LIKE ?"
                        )
                        params.append(f"%{search_term.strip()}%")
                    conditions.append("(" + " OR ".join(parts) + ")")

            sql = f"SELECT * FROM {quote_identifier(table)}"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " LIMIT 500"
            frame = pd.read_sql_query(sql, conn, params=params)
            if not frame.empty:
                frames.append(frame)

        return pd.concat(frames, ignore_index=True).drop_duplicates() if frames else pd.DataFrame()

    except Exception as exc:
        st.error(f"Eroare baza DTC: {exc}")
        return pd.DataFrame()
    finally:
        conn.close()


def download_text_dataset(url, destination, required_columns):
    """Descarca un CSV extern intr-un fisier temporar si il valideaza."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    try:
        response = requests.get(url, timeout=(20, 180))
        response.raise_for_status()
        if not response.content or len(response.content) < 20:
            raise ValueError("Fisierul descarcat este gol sau incomplet.")
        temporary.write_bytes(response.content)
        frame = pd.read_csv(temporary, sep="|", encoding="utf-8-sig", dtype=str, nrows=5)
        missing = [column for column in required_columns if column not in frame.columns]
        if missing:
            raise ValueError("Lipsesc coloanele obligatorii: " + ", ".join(missing))
        temporary.replace(destination)
        return True, f"Fisier descarcat si verificat ({destination.stat().st_size / 1024:.0f} KB)."
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        return False, str(exc)


def read_mechanicdb_csv(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, sep="|", encoding="utf-8-sig", dtype=str, low_memory=False)
        frame.columns = [str(column).strip() for column in frame.columns]
        return frame
    except Exception:
        return pd.DataFrame()


def search_mechanicdb_fixes(code, limit=100):
    frame = read_mechanicdb_csv(MECHANICDB_FIXES_PATH)
    if frame.empty or not code:
        return pd.DataFrame()
    code_col = find_existing_column(list(frame.columns), ["dtc_code", "code", "trouble_code"])
    if not code_col:
        return pd.DataFrame()
    mask = frame[code_col].astype(str).str.upper().str.strip() == str(code).upper().strip()
    return frame.loc[mask].head(limit)


def search_mechanicdb_parts(code, limit=100):
    """Leaga piesele prin fix_id, asa cum este definita schema MechanicDB."""
    fixes = search_mechanicdb_fixes(code, limit=500)
    parts = read_mechanicdb_csv(MECHANICDB_PARTS_PATH)
    if fixes.empty or parts.empty:
        return pd.DataFrame()

    fix_id_col = find_existing_column(list(fixes.columns), ["fix_id", "id"])
    parts_fix_id_col = find_existing_column(list(parts.columns), ["fix_id"])
    if not fix_id_col or not parts_fix_id_col:
        return pd.DataFrame()

    fix_ids = set(fixes[fix_id_col].dropna().astype(str).str.strip())
    mask = parts[parts_fix_id_col].astype(str).str.strip().isin(fix_ids)
    return parts.loc[mask].head(limit)


def download_obdex_dataset(force=False):
    """Descarca si valideaza catalogul explicativ OBDEX (date CC0)."""
    destination = Path(OBDEX_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.stat().st_size > 100000 and not force:
        return True, "Catalogul explicativ OBDEX exista deja."

    temporary = destination.with_suffix(".json.download")
    try:
        response = requests.get(
            OBDEX_JSON_URL,
            timeout=(20, 180),
            headers={"User-Agent": "AutoDiagnosisPro/2.0"}
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            payload = payload.get("codes", payload.get("data", payload))

        if not isinstance(payload, list) or len(payload) < 5000:
            raise ValueError("Catalogul primit nu contine lista asteptata de coduri.")

        sample = next((item for item in payload if isinstance(item, dict) and item.get("code")), None)
        if not sample or not any(key in sample for key in ("common_causes", "symptoms", "description")):
            raise ValueError("Structura catalogului nu contine campurile explicative necesare.")

        temporary.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8"
        )
        temporary.replace(destination)

        try:
            load_obdex_dataset.clear()
        except Exception:
            pass

        return True, f"Catalog explicativ instalat: {len(payload):,} inregistrari."
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        return False, f"Nu am putut descarca OBDEX: {exc}"


@st.cache_data(ttl=3600, show_spinner=False)
def load_obdex_dataset():
    """Incarca in memorie catalogul OBDEX si indexeaza codurile."""
    path = Path(OBDEX_PATH)
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("codes", payload.get("data", []))
        if not isinstance(payload, list):
            return {}

        return {
            str(item.get("code", "")).upper().strip(): item
            for item in payload
            if isinstance(item, dict) and item.get("code")
        }
    except Exception:
        return {}


def get_obdex_record(code):
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    if not code:
        return None
    return load_obdex_dataset().get(code)


def obdex_text(value):
    """Alege textul englez, cu fallback la germana."""
    if isinstance(value, dict):
        return clean_text(value.get("en") or value.get("de") or value.get("ro"))
    if isinstance(value, list):
        return ", ".join(obdex_text(item) for item in value if item)
    return clean_text(value)


def display_obdex_diagnosis(record):
    """Afiseaza explicatiile si recomandarile din inregistrarea OBDEX."""
    title = obdex_text(record.get("title"))
    description = obdex_text(record.get("description"))

    st.markdown("### Explicatie tehnica detaliata")
    if title:
        st.markdown(f"**{title}**")
    if description:
        st.write(description)
        st.caption("Descrierea este afisata in limba originala a sursei (engleza; germana daca engleza lipseste).")

    components = record.get("affected_components") or []
    if components:
        st.markdown("**Componente implicate**")
        st.write(", ".join(
            str(item).replace("_", " ").capitalize()
            for item in components
        ))

    causes = record.get("common_causes") or []
    if causes:
        st.markdown("**Cauze probabile**")
        for cause in causes:
            if isinstance(cause, dict):
                label = obdex_text(cause.get("label") or cause.get("id"))
                likelihood = clean_text(cause.get("likelihood"))
                suffix = f" — probabilitate: {likelihood}" if likelihood else ""
                st.write(f"- {label}{suffix}")

    symptoms = record.get("symptoms") or []
    if symptoms:
        st.markdown("**Simptome posibile**")
        for symptom in symptoms:
            st.write("- " + obdex_text(symptom))

    repair = record.get("repair") or {}
    if repair:
        st.markdown("**Dificultatea si estimarea reparatiei**")
        difficulty_names = {
            "easy": "Usoara",
            "medium": "Medie",
            "hard": "Dificila"
        }
        difficulty = difficulty_names.get(
            str(repair.get("difficulty", "")).lower(),
            clean_text(repair.get("difficulty"))
        )
        if difficulty:
            st.write(f"- Dificultate: {difficulty}")
        if repair.get("diy_possible") is not None:
            st.write(
                "- Reparatie DIY posibila: "
                + ("Da" if repair.get("diy_possible") else "Nu; recomandat service")
            )
        cost = repair.get("estimated_cost_eur")
        if isinstance(cost, list) and len(cost) >= 2:
            st.write(f"- Cost estimativ: {cost[0]}–{cost[1]} EUR")
        hours = repair.get("estimated_hours")
        if isinstance(hours, list) and len(hours) >= 2:
            st.write(f"- Timp estimativ de manopera: {hours[0]}–{hours[1]} ore")

    flags = record.get("flags") or {}
    if flags:
        st.markdown("**Avertizari si comportament**")
        flag_names = {
            "mil": "Aprinde martorul Check Engine",
            "emissions_relevant": "Poate afecta emisiile",
            "drive_cycle_required": "Poate necesita ciclu de conducere pentru reverificare",
            "limp_mode_possible": "Poate activa modul de avarie"
        }
        for key, label in flag_names.items():
            if flags.get(key):
                st.write("- " + label)

    related = record.get("related_codes") or []
    if related:
        st.markdown("**Coduri asociate**")
        st.write(", ".join(str(code) for code in related))

    sources = record.get("sources") or []
    if sources:
        st.markdown("**Surse tehnice**")
        for source in sources[:12]:
            source_url = clean_text(source)
            if source_url.startswith(("https://", "http://")):
                st.write(source_url)

    if record.get("reviewed"):
        st.caption(f"Data ultimei revizuiri in sursa: {record.get('reviewed')}")

    st.caption("Sursa datelor: OBDEX, licenta CC0-1.0. Estimarile sunt orientative si trebuie confirmate pentru vehiculul concret.")


# ============================================================
# DIAGNOSTICARE DTC - EXPLICATII SI ISTORIC
# ============================================================

def save_dtc_history(
    vehicle,
    engine,
    code,
    description,
    diagnosis="",
    repair=""
):

    add_local_record(
        "dtc_history",
        {
            "vehicle": vehicle,
            "engine": engine,
            "dtc_code": code,
            "description": description,
            "diagnosis": diagnosis,
            "repair": repair
        }
    )


def get_dtc_history():

    return get_local_table("dtc_history")


# ============================================================
# OBD-II - PID-URI STANDARD
# ============================================================

OBD_PIDS = {
    "01": {
        "name": "Engine Load",
        "unit": "%",
        "description": "Sarcina calculata a motorului"
    },
    "04": {
        "name": "Engine Coolant Temperature",
        "unit": "°C",
        "description": "Temperatura lichidului de racire"
    },
    "05": {
        "name": "Intake Air Temperature",
        "unit": "°C",
        "description": "Temperatura aerului admis"
    },
    "0B": {
        "name": "Intake Manifold Pressure",
        "unit": "kPa",
        "description": "Presiunea in galeria de admisie"
    },
    "0C": {
        "name": "Engine RPM",
        "unit": "rpm",
        "description": "Turatia motorului"
    },
    "0D": {
        "name": "Vehicle Speed",
        "unit": "km/h",
        "description": "Viteza vehiculului"
    },
    "0F": {
        "name": "Intake Air Temperature",
        "unit": "°C",
        "description": "Temperatura aerului admis"
    },
    "10": {
        "name": "MAF Air Flow",
        "unit": "g/s",
        "description": "Debit masic de aer"
    },
    "11": {
        "name": "Throttle Position",
        "unit": "%",
        "description": "Pozitia clapetei de acceleratie"
    },
    "2F": {
        "name": "Fuel Tank Level",
        "unit": "%",
        "description": "Nivel combustibil"
    },
    "42": {
        "name": "Control Module Voltage",
        "unit": "V",
        "description": "Tensiunea modulului de control"
    }
}


def decode_obd_pid(pid, a, b=0, c=0, d=0):

    pid = str(pid).upper()

    if pid == "04":
        return a * 100 / 255

    if pid == "05" or pid == "0F":
        return a - 40

    if pid == "0B":
        return a

    if pid == "0C":
        return ((a * 256) + b) / 4

    if pid == "0D":
        return a

    if pid == "10":
        return ((a * 256) + b) / 100

    if pid == "11":
        return a * 100 / 255

    if pid == "2F":
        return a * 100 / 255

    if pid == "42":
        return ((a * 256) + b) / 1000

    if pid == "01":
        return a * 100 / 255

    return None


def parse_obd_hex(value):

    parts = re.findall(
        r"[0-9A-Fa-f]{2}",
        clean_text(value)
    )

    return [int(part, 16) for part in parts]


def import_obd_csv(uploaded_file):

    try:
        return pd.read_csv(uploaded_file)
    except Exception:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(
                uploaded_file,
                sep=";",
                encoding="utf-8-sig"
            )
        except Exception:
            return pd.DataFrame()


# ============================================================
# FINAL PARTEA 2/4
# ============================================================

# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 3/4 - PAGINI SI INTERFATA
# ============================================================


# ============================================================
# DASHBOARD
# ============================================================

def page_dashboard():

    page_header(
        "Auto Diagnosis Pro",
        "Platforma pentru diagnosticare si informatii tehnice auto."
    )

    stats = get_database_statistics()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Marci", format_number(stats["marci"]))
    col2.metric("Modele", format_number(stats["modele"]))
    col3.metric("Generatii", format_number(stats["generatii"]))
    col4.metric("Motoare", format_number(stats["motoare"]))

    st.subheader("Module disponibile")

    modules = [
        ("🔎 Diagnosticare DTC", "Identificarea codurilor de defect."),
        ("🚘 Cautare vehicule", "Catalog auto si modele."),
        ("⚙️ Date tehnice motor", "Generatii si variante de motorizare."),
        ("🛠️ Intretinere", "Evidenta lucrarilor de service."),
        ("📊 Diagnosticare OBD", "Interpretarea parametrilor OBD-II."),
        ("🔧 Piese", "Catalog local de piese."),
        ("📋 Reparatii", "Istoric cazuri de reparatii."),
        ("📖 Documentatie", "Informatii tehnice si surse.")
    ]

    for name, description in modules:
        st.write(f"**{name}** — {description}")

    st.divider()

    st.info(
        "Pentru rezultate complete, descarca bazele de date din "
        "modulul «Baze de date si surse»."
    )


# ============================================================
# DIAGNOSTICARE DTC
# ============================================================

def lookup_local_diagnosis(code):
    """Intoarce explicatiile locale pentru codurile DTC cunoscute."""
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    if len(code) != 5:
        return None
    conn = get_local_connection()
    try:
        row = conn.execute(
            "SELECT * FROM diagnosis_records WHERE UPPER(dtc_code) = ? LIMIT 1",
            (code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def page_dtc_diagnosis():

    page_header(
        "Diagnosticare DTC",
        "Introdu codul de eroare pentru explicatii, cauze posibile, simptome si recomandari."
    )

    code = st.text_input(
        "Cod DTC",
        placeholder="Exemplu: P0420",
        max_chars=10
    ).upper().strip()

    vehicle = st.text_input("Vehicul")
    engine = st.text_input("Motor")

    if st.button("Analizeaza codul DTC", type="primary"):
        normalized_code = re.sub(r"[^A-Z0-9]", "", code)
        if len(normalized_code) != 5 or normalized_code[0] not in "PBCU" or not normalized_code[1:].isdigit():
            st.warning("Introdu un cod OBD-II valid, de exemplu P0420.")
        else:
            st.session_state["dtc_current_code"] = normalized_code
            st.session_state["dtc_vehicle"] = vehicle
            st.session_state["dtc_engine"] = engine
            st.session_state["dtc_results"] = search_dtc(code=normalized_code)

            if not Path(OBDEX_PATH).exists():
                with st.spinner("Se descarca prima data catalogul explicativ cu peste 9.500 de coduri..."):
                    ok, message = download_obdex_dataset()
                st.session_state["obdex_download_message"] = message
            else:
                st.session_state["obdex_download_message"] = "Catalogul explicativ este disponibil."

    current_code = st.session_state.get("dtc_current_code", "")
    if not current_code:
        st.info("Introdu un cod DTC si apasa «Analizeaza codul DTC».")
        return

    st.subheader(f"Rezultate pentru {current_code}")

    obdex_record = get_obdex_record(current_code)
    local = lookup_local_diagnosis(current_code)
    results = st.session_state.get("dtc_results", pd.DataFrame())

    if obdex_record:
        display_obdex_diagnosis(obdex_record)
    elif local:
        st.markdown("### Diagnostic local si sugestii de rezolvare")
        st.markdown(f"**{local.get('title', '')}**")
        st.write("**Cauze posibile:** " + (local.get("possible_causes") or "Nu exista date."))
        st.write("**Simptome:** " + (local.get("symptoms") or "Nu exista date."))
        st.write("**Verificari recomandate:** " + (local.get("checks") or "Nu exista date."))
        st.write("**Recomandari de reparatie:** " + (local.get("repair_suggestions") or "Nu exista date."))
        st.caption(f"Sursa: {local.get('source', 'Baza interna')} | Nivel: {local.get('confidence', 'Orientativ')}")
    else:
        st.info("Nu exista o fisa explicativa detaliata disponibila pentru acest cod in sursele conectate.")

    if not results.empty:
        st.markdown("### Definitii DTC si variante specifice producatorului")
        st.dataframe(results, use_container_width=True, hide_index=True)
        description = results.to_string(index=False)
    else:
        description = f"Cod DTC: {current_code}"

    fixes = search_mechanicdb_fixes(current_code)
    if not fixes.empty:
        st.markdown("### Proceduri de remediere – mostra MechanicDB")
        st.caption("Mostra publica limitata. Procedurile trebuie potrivite cu marca, modelul si motorul vehiculului.")
        st.dataframe(fixes, use_container_width=True, hide_index=True)

    parts = search_mechanicdb_parts(current_code)
    if not parts.empty:
        st.markdown("### Piese asociate – mostra MechanicDB")
        st.dataframe(parts, use_container_width=True, hide_index=True)

    if not obdex_record and not local and results.empty and fixes.empty:
        st.warning(
            "Codul nu a fost gasit in cataloagele disponibile. "
            "Verifica daca ai selectat producatorul corect si daca baza DTC este descarcata."
        )

    st.divider()
    st.subheader("Salveaza diagnosticul")
    diagnosis = st.text_area("Diagnostic stabilit de tehnician")
    repair_text = st.text_area("Reparatie efectuata")

    if st.button("Salveaza in istoricul DTC"):
        save_dtc_history(
            st.session_state.get("dtc_vehicle", ""),
            st.session_state.get("dtc_engine", ""),
            current_code,
            description,
            diagnosis,
            repair_text
        )
        st.success("Codul a fost salvat in istoric.")

    if not results.empty:
        export_dataframe_csv(results, "diagnostic_dtc.csv")

    st.warning(
        "Un cod DTC descrie o conditie detectata, nu confirma singur piesa defecta. "
        "Costurile si recomandarile sunt orientative; confirma diagnosticul cu procedura producatorului."
    )


# ============================================================

def lookup_local_diagnosis(code):
    """Intoarce explicatiile locale pentru codurile DTC cunoscute."""
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    if len(code) != 5:
        return None
    conn = get_local_connection()
    try:
        row = conn.execute(
            "SELECT * FROM diagnosis_records WHERE UPPER(dtc_code) = ? LIMIT 1",
            (code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================

def lookup_local_diagnosis(code):
    """Intoarce explicatiile locale pentru codurile DTC cunoscute."""
    code = re.sub(r"[^A-Z0-9]", "", str(code or "").upper())
    if len(code) != 5:
        return None
    conn = get_local_connection()
    try:
        row = conn.execute(
            "SELECT * FROM diagnosis_records WHERE UPPER(dtc_code) = ? LIMIT 1",
            (code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# CAUTARE CODURI DTC
# ============================================================

def page_dtc_search():

    page_header(
        "Biblioteca DTC",
        "Cauta dupa cod sau descriere."
    )

    col1, col2 = st.columns(2)

    with col1:
        code = st.text_input(
            "Cod DTC",
            placeholder="P0300"
        )

    with col2:
        term = st.text_input(
            "Cuvant din descriere"
        )

    if st.button("Cauta coduri"):

        results = search_dtc(
            code=code,
            search_term=term
        )

        st.session_state["dtc_library_results"] = results

    results = st.session_state.get(
        "dtc_library_results",
        pd.DataFrame()
    )

    if not results.empty:

        st.write(f"Rezultate: {len(results)}")

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            results,
            "biblioteca_dtc.csv"
        )

    elif "dtc_library_results" in st.session_state:
        st.info("Nu au fost gasite rezultate.")


# ============================================================
# CAUTARE VEHICULE
# ============================================================

def page_vehicle_search():

    page_header(
        "Catalog vehicule",
        "Cauta marci si modele din baza VehiclesDB."
    )

    status, message = get_vehicle_database_status()

    if not status:

        st.warning(message)

        if st.button("Descarca baza VehiclesDB"):

            with st.spinner("Se descarca baza de date..."):

                success, download_message = ensure_external_database(
                    VEHICLES_DB_PATH,
                    VEHICLES_DB_URL,
                    ["makes", "models"]
                )

            if success:
                st.success(download_message)
                st.rerun()
            else:
                st.error(download_message)

        return

    makes = get_vehicle_makes()

    if not makes:
        st.error("Nu am putut identifica marcile.")
        return

    st.write(
        f"Marci disponibile in baza de date: **{len(makes)}**"
    )

    col1, col2 = st.columns(2)

    with col1:
        selected_make = st.selectbox(
            "Marca",
            ["Toate"] + makes
        )

    with col2:
        model_search = st.text_input(
            "Model",
            placeholder="Exemplu: Logan, Golf, Corolla"
        )

    general_search = st.text_input(
        "Cautare suplimentara",
        placeholder="Cuvant din denumire sau categorie"
    )

    if st.button("Cauta vehicule", type="primary"):

        with st.spinner("Se cauta in catalog..."):

            df = search_vehicles(
                make="" if selected_make == "Toate"
                else selected_make,
                model=model_search,
                search_term=general_search
            )

            st.session_state["vehicle_results"] = df

    results = st.session_state.get(
        "vehicle_results",
        pd.DataFrame()
    )

    if not results.empty:

        st.success(
            f"Au fost gasite {len(results)} rezultate."
        )

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            results,
            "catalog_vehicule.csv",
            "Descarca toate rezultatele CSV"
        )

    elif "vehicle_results" in st.session_state:
        st.info("Nu exista rezultate pentru cautarea efectuata.")


# ============================================================
# DATE TEHNICE MOTOR
# ============================================================

def page_engine_data():

    page_header(
        "Date tehnice motor",
        "Cauta generatii, motorizari si specificatii."
    )

    status, message = get_engine_database_status()

    if not status:

        st.warning(message)

        if st.button("Descarca baza de motoare"):

            with st.spinner("Se descarca baza de motoare..."):

                success, download_message = ensure_external_database(
                    ENGINES_DB_PATH,
                    ENGINES_DB_URL,
                    [
                        "makes",
                        "models",
                        "generations",
                        "engines"
                    ]
                )

            if success:
                st.success(download_message)
                st.rerun()
            else:
                st.error(download_message)

        return

    col1, col2 = st.columns(2)

    with col1:
        make = st.text_input("Marca")

        model = st.text_input("Model")

    with col2:
        year = st.text_input("An fabricatie")

        fuel = st.selectbox(
            "Combustibil",
            [
                "",
                "Petrol",
                "Diesel",
                "Gasoline",
                "Hybrid",
                "Electric",
                "LPG",
                "CNG"
            ]
        )

    engine_search = st.text_input(
        "Motor, cod motor sau specificatie"
    )

    if st.button("Cauta motorizari", type="primary"):

        with st.spinner("Se cauta motorizari..."):

            results = search_engine_catalog(
                make=make,
                model=model,
                year=year,
                fuel=fuel,
                engine_search=engine_search
            )

            st.session_state["engine_results"] = results

    results = st.session_state.get(
        "engine_results",
        pd.DataFrame()
    )

    if not results.empty:

        st.success(
            f"Motorizari gasite: {len(results)}"
        )

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            results,
            "catalog_motoare.csv"
        )

    elif "engine_results" in st.session_state:
        st.info("Nu au fost gasite motorizari.")


# ============================================================
# INTRETINERE SI SERVICE
# ============================================================

def page_maintenance():

    page_header(
        "Intretinere si service",
        "Evidenta operatiunilor de intretinere."
    )

    with st.expander("Adauga operatiune de service", expanded=True):

        with st.form("maintenance_form"):

            col1, col2 = st.columns(2)

            with col1:
                make = st.text_input("Marca vehicul")
                model = st.text_input("Model")
                year = st.text_input("An")
                engine = st.text_input("Motor")

            with col2:
                maintenance_type = st.selectbox(
                    "Operatiune",
                    [
                        "Schimb ulei",
                        "Filtru ulei",
                        "Filtru aer",
                        "Filtru combustibil",
                        "Filtru habitaclu",
                        "Distributie",
                        "Frane",
                        "Lichid racire",
                        "Lichid frana",
                        "Transmisie",
                        "Altele"
                    ]
                )

                mileage = st.number_input(
                    "Kilometraj",
                    min_value=0,
                    step=1000
                )

                interval_km = st.number_input(
                    "Interval kilometri",
                    min_value=0,
                    step=1000
                )

                interval_months = st.number_input(
                    "Interval luni",
                    min_value=0,
                    step=1
                )

            description = st.text_area("Descriere")
            source = st.text_input("Sursa")
            source_url = st.text_input("Link sursa")
            notes = st.text_area("Observatii")

            submitted = st.form_submit_button("Salveaza")

            if submitted:

                if source_url and not valid_url(source_url):
                    st.error("Linkul nu este valid.")

                else:

                    add_local_record(
                        "maintenance_records",
                        {
                            "make": make,
                            "model": model,
                            "year": year,
                            "engine": engine,
                            "maintenance_type": maintenance_type,
                            "mileage": mileage,
                            "interval_km": interval_km,
                            "interval_months": interval_months,
                            "description": description,
                            "source": source,
                            "source_url": source_url,
                            "notes": notes
                        }
                    )

                    st.success("Operatiunea a fost salvata.")
                    st.rerun()

    records = get_local_table("maintenance_records")

    if not records.empty:

        st.subheader("Istoric service")

        st.dataframe(
            records,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            records,
            "istoric_service.csv"
        )

    else:
        st.info("Nu exista operatiuni inregistrate.")

    st.warning(
        "Intervalele de service trebuie verificate in documentatia "
        "producatorului pentru motorul si configuratia exacta."
    )


# ============================================================
# DIAGNOSTICARE AVANSATA OBD
# ============================================================

def page_advanced_obd():

    page_header(
        "Diagnosticare avansata OBD-II",
        "Interpretarea datelor OBD introduse manual."
    )

    st.info(
        "Aplicatia web nu se conecteaza direct la adaptorul Bluetooth "
        "sau USB al masinii. Poti introduce valori sau importa CSV."
    )

    pid = st.selectbox(
        "PID",
        list(OBD_PIDS.keys()),
        format_func=lambda x: (
            x + " - " + OBD_PIDS[x]["name"]
        )
    )

    st.caption(OBD_PIDS[pid]["description"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        a = st.number_input(
            "Byte A",
            min_value=0,
            max_value=255,
            value=0
        )

    with col2:
        b = st.number_input(
            "Byte B",
            min_value=0,
            max_value=255,
            value=0
        )

    with col3:
        c = st.number_input(
            "Byte C",
            min_value=0,
            max_value=255,
            value=0
        )

    with col4:
        d = st.number_input(
            "Byte D",
            min_value=0,
            max_value=255,
            value=0
        )

    value = decode_obd_pid(
        pid,
        a,
        b,
        c,
        d
    )

    if value is not None:

        st.metric(
            OBD_PIDS[pid]["name"],
            f"{value:.2f} {OBD_PIDS[pid]['unit']}"
        )

        if st.button("Salveaza masuratoarea"):

            add_local_record(
                "obd_measurements",
                {
                    "vehicle": "",
                    "engine": "",
                    "pid": pid,
                    "measurement": OBD_PIDS[pid]["name"],
                    "value": value,
                    "unit": OBD_PIDS[pid]["unit"],
                    "recorded_at": datetime.now().isoformat(),
                    "notes": "Valoare introdusa manual"
                }
            )

            st.success("Masuratoarea a fost salvata.")

    st.divider()
    st.subheader("Import date OBD din CSV")

    uploaded = st.file_uploader(
        "Alege fisier CSV",
        type=["csv"]
    )

    if uploaded is not None:

        df = import_obd_csv(uploaded)

        if not df.empty:

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            export_dataframe_csv(
                df,
                "date_obd_export.csv"
            )

        else:
            st.error("Fisierul CSV nu a putut fi citit.")

    st.divider()
    st.subheader("Istoric masuratori")

    measurements = get_local_table("obd_measurements")

    if not measurements.empty:

        st.dataframe(
            measurements,
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_csv(
            measurements,
            "istoric_obd.csv"
        )

    else:
        st.info("Nu exista masuratori salvate.")


# ============================================================
# FINAL PARTEA 3/4
# ============================================================

# ============================================================
# AUTO DIAGNOSIS PRO
# PARTEA 4/4 - MODULE FINALE SI MENIU
# ============================================================


# ============================================================
# PIESE SI COMPATIBILITATE
# ============================================================

def page_parts():

    page_header(
        "Piese si compatibilitate",
        "Catalog local de piese si referinte OEM."
    )

    with st.expander("Adauga piesa", expanded=True):

        with st.form("parts_form"):

            col1, col2 = st.columns(2)

            with col1:
                part_number = st.text_input("Cod piesa")
                oem_number = st.text_input("Cod OEM")
                brand = st.text_input("Producator")
                category = st.text_input("Categorie")

            with col2:
                make = st.text_input("Marca vehicul")
                model = st.text_input("Model vehicul")
                year_range = st.text_input("Ani compatibili")
                engine = st.text_input("Motor / cod motor")

            description = st.text_area("Descriere")

            compatibility = st.selectbox(
                "Verificare compatibilitate",
                [
                    "Neverificata",
                    "Verificata dupa cod OEM",
                    "Verificata dupa VIN",
                    "Confirmata de producator"
                ]
            )

            source_name = st.text_input("Sursa")
            source_url = st.text_input("Link sursa")
            notes = st.text_area("Observatii")

            submitted = st.form_submit_button("Salveaza piesa")

            if submitted:

                if not part_number and not oem_number:
                    st.error("Introdu codul piesei sau codul OEM.")

                elif source_url and not valid_url(source_url):
                    st.error("Linkul trebuie sa fie HTTP sau HTTPS.")

                else:

                    add_local_record(
                        "parts_records",
                        {
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
                    )

                    st.success("Piesa a fost salvata.")
                    st.rerun()

    st.divider()

    parts = get_local_table("parts_records")

    search = st.text_input("Cauta piesa")

    if not parts.empty:

        filtered = parts.copy()

        if search:

            mask = filtered.astype(str).apply(
                lambda col: col.str.contains(
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
            "catalog_piese.csv"
        )

        if "id" in filtered.columns:

            selected_id = st.selectbox(
                "ID piesa pentru stergere",
                [""] + filtered["id"].astype(str).tolist()
            )

            if st.button("Sterge piesa") and selected_id:

                delete_local_record(
                    "parts_records",
                    int(selected_id)
                )

                st.success("Piesa a fost stearsa.")
                st.rerun()

    else:
        st.info("Catalogul de piese este gol.")

    st.warning(
        "Prezenta unei piese in catalog nu confirma compatibilitatea. "
        "Verifica VIN-ul, codul OEM si configuratia vehiculului."
    )


# ============================================================
# CAZURI DE REPARATII
# ============================================================

def page_repairs():

    page_header(
        "Cazuri de reparatii",
        "Istoric de diagnosticare si lucrari efectuate."
    )

    with st.expander("Adauga caz de reparatie", expanded=True):

        with st.form("repair_form"):

            col1, col2 = st.columns(2)

            with col1:
                repair_date = st.date_input(
                    "Data",
                    value=date.today()
                )

                make = st.text_input("Marca")
                model = st.text_input("Model")
                year = st.text_input("An")

            with col2:
                generation = st.text_input("Generatie")
                engine = st.text_input("Motor")
                mileage = st.number_input(
                    "Kilometraj",
                    min_value=0,
                    step=1000
                )

                dtc_codes = st.text_input(
                    "Coduri DTC",
                    value=st.session_state.get(
                        "repair_prefill_dtc", ""
                    )
                )

            symptoms = st.text_area("Simptome")
            cause = st.text_area("Cauza confirmata")
            repair = st.text_area("Reparatia efectuata")
            parts = st.text_area("Piese utilizate")

            result = st.selectbox(
                "Rezultat",
                [
                    "Nedeterminat",
                    "Rezolvat",
                    "Rezolvat partial",
                    "Defect persistent",
                    "Necesita verificari"
                ]
            )

            notes = st.text_area("Observatii")

            submitted = st.form_submit_button(
                "Salveaza cazul"
            )

            if submitted:

                add_local_record(
                    "repair_cases",
                    {
                        "repair_date": str(repair_date),
                        "make": make,
                        "model": model,
                        "year": year,
                        "generation": generation,
                        "engine": engine,
                        "mileage": mileage,
                        "dtc_codes": dtc_codes,
                        "symptoms": symptoms,
                        "confirmed_cause": cause,
                        "repair_performed": repair,
                        "parts_used": parts,
                        "result": result,
                        "notes": notes
                    }
                )

                st.session_state["repair_prefill_dtc"] = ""

                st.success("Cazul a fost salvat.")
                st.rerun()

    st.divider()

    repairs = get_local_table("repair_cases")

    search = st.text_input(
        "Cauta marca, model, cod DTC sau simptom"
    )

    if repairs.empty:
        st.info("Nu exista cazuri de reparatii.")

    else:

        filtered = repairs.copy()

        if search:

            mask = filtered.astype(str).apply(
                lambda col: col.str.contains(
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
            "cazuri_reparatii.csv"
        )

        st.divider()
        st.subheader("Editeaza un caz")

        selected_id = st.selectbox(
            "Selecteaza ID",
            [""] + repairs["id"].astype(str).tolist()
        )

        if selected_id:

            selected = repairs[
                repairs["id"].astype(str) == selected_id
            ].iloc[0]

            with st.form("edit_repair_form"):

                cause = st.text_area(
                    "Cauza confirmata",
                    value=clean_text(
                        selected.get("confirmed_cause")
                    )
                )

                repair = st.text_area(
                    "Reparatia efectuata",
                    value=clean_text(
                        selected.get("repair_performed")
                    )
                )

                parts = st.text_area(
                    "Piese utilizate",
                    value=clean_text(
                        selected.get("parts_used")
                    )
                )

                result = st.text_input(
                    "Rezultat",
                    value=clean_text(
                        selected.get("result")
                    )
                )

                notes = st.text_area(
                    "Observatii",
                    value=clean_text(
                        selected.get("notes")
                    )
                )

                save = st.form_submit_button(
                    "Salveaza modificarile"
                )

                if save:

                    update_local_record(
                        "repair_cases",
                        int(selected_id),
                        {
                            "confirmed_cause": cause,
                            "repair_performed": repair,
                            "parts_used": parts,
                            "result": result,
                            "notes": notes
                        }
                    )

                    st.success("Cazul a fost actualizat.")
                    st.rerun()

            if st.button("Sterge cazul selectat"):

                delete_local_record(
                    "repair_cases",
                    int(selected_id)
                )

                st.success("Cazul a fost sters.")
                st.rerun()


# ============================================================
# DOCUMENTATIE TEHNICA
# ============================================================

def page_workshop_reference():

    page_header(
        "Documentatie tehnica",
        "Biblioteca de informatii tehnice pentru atelier."
    )

    with st.expander("Adauga documentatie", expanded=True):

        with st.form("reference_form"):

            col1, col2 = st.columns(2)

            with col1:
                make = st.text_input("Marca")
                model = st.text_input("Model")
                year = st.text_input("An / generatie")
                engine = st.text_input("Motor")

            with col2:
                subject = st.selectbox(
                    "Categorie",
                    [
                        "Cupluri strangere",
                        "Uleiuri si fluide",
                        "Distributie",
                        "Frane",
                        "Sistem electric",
                        "Scheme electrice",
                        "Proceduri reparatie",
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
                        "Documentatie oficiala service"
                    ]
                )

            information = st.text_area(
                "Informatii tehnice",
                height=180
            )

            source_name = st.text_input("Sursa")
            source_url = st.text_input("Link")
            license_info = st.text_input("Licenta")
            safety_warning = st.text_area("Avertismente de siguranta")

            submitted = st.form_submit_button(
                "Salveaza documentatia"
            )

            if submitted:

                if not information:
                    st.error("Introdu informatia tehnica.")

                elif source_url and not valid_url(source_url):
                    st.error("Link invalid.")

                else:

                    add_local_record(
                        "workshop_reference",
                        {
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
                    )

                    st.success("Documentatia a fost salvata.")
                    st.rerun()

    references = get_local_table("workshop_reference")

    search = st.text_input("Cauta documentatie")

    if not references.empty:

        filtered = references.copy()

        if search:

            mask = filtered.astype(str).apply(
                lambda col: col.str.contains(
                    search,
                    case=False,
                    na=False
                )
            ).any(axis=1)

            filtered = filtered[mask]

        for _, item in filtered.iterrows():

            heading = (
                clean_text(item.get("make"))
                + " "
                + clean_text(item.get("model"))
                + " - "
                + clean_text(item.get("subject"))
            )

            with st.expander(heading):

                st.write("Motor:", item.get("engine", ""))
                st.write("An:", item.get("year", ""))
                st.write("Nivel:", item.get("confidence", ""))
                st.write(item.get("information", ""))

                if item.get("source_name"):
                    st.write("Sursa:", item["source_name"])

                url = clean_text(item.get("source_url"))

                if url and valid_url(url):
                    st.markdown(f"[Deschide sursa]({url})")

                if item.get("license_info"):
                    st.write("Licenta:", item["license_info"])

                if item.get("safety_warning"):
                    st.warning(item["safety_warning"])

        export_dataframe_csv(
            filtered,
            "documentatie_tehnica.csv"
        )

        selected_id = st.selectbox(
            "ID documentatie pentru stergere",
            [""] + references["id"].astype(str).tolist()
        )

        if st.button("Sterge documentatia") and selected_id:

            delete_local_record(
                "workshop_reference",
                int(selected_id)
            )

            st.success("Documentatia a fost stearsa.")
            st.rerun()

    else:
        st.info("Nu exista documentatie salvata.")

    st.warning(
        "Nu considera valorile tehnice introduse manual ca fiind "
        "specificatii oficiale daca nu au o sursa verificabila. "
        "Sistemele SRS si circuitele de inalta tensiune necesita "
        "personal calificat si proceduri corespunzatoare."
    )


# ============================================================
# BAZE DE DATE SI SURSE
# ============================================================

def page_database_sources():

    page_header(
        "Baze de date si surse",
        "Administrarea cataloagelor externe."
    )

    st.subheader("Stare baze de date")

    paths = [
        ("Coduri DTC", DTC_DB_PATH),
        ("Catalog explicativ OBDEX", OBDEX_PATH),
        ("VehiclesDB", VEHICLES_DB_PATH),
        ("Motoare si generatii", ENGINES_DB_PATH),
        ("Baza locala", LOCAL_DB_PATH)
    ]

    for name, path in paths:

        if Path(path).exists():

            size = Path(path).stat().st_size / (1024 * 1024)

            st.success(
                f"{name}: disponibil - {size:.2f} MB"
            )

        else:
            st.warning(f"{name}: indisponibil")

    st.divider()

    st.subheader("Descarcare cataloage")

    if st.button("Descarca / actualizeaza baza de coduri DTC", use_container_width=True):
        with st.spinner("Se descarca baza DTC externa..."):
            success, message = ensure_external_database(
                DTC_DB_PATH,
                DTC_DB_URL,
                ["dtc_definitions"]
            )
        if success:
            st.success("Baza DTC este instalata. " + message)
            st.rerun()
        else:
            st.error("Descarcarea bazei DTC a esuat: " + message)

    if st.button("Descarca / actualizeaza catalogul explicativ OBDEX (9.500+ coduri)", use_container_width=True):
        with st.spinner("Se descarca catalogul explicativ OBDEX..."):
            success, message = download_obdex_dataset(force=True)
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    if st.button("Descarca mostrele publice MechanicDB", use_container_width=True):
        with st.spinner("Se descarca procedurile si piesele MechanicDB..."):
            fixes_ok, fixes_msg = download_text_dataset(
                MECHANICDB_FIXES_URL,
                MECHANICDB_FIXES_PATH,
                ["dtc_code", "fix_title"]
            )
            parts_ok, parts_msg = download_text_dataset(
                MECHANICDB_PARTS_URL,
                MECHANICDB_PARTS_PATH,
                ["fix_id", "part_name"]
            )
        if fixes_ok and parts_ok:
            st.success("Mostrele MechanicDB au fost descarcate.")
            st.rerun()
        else:
            st.error("Proceduri: " + fixes_msg)
            st.error("Piese: " + parts_msg)

    if st.button(
        "Descarca / actualizeaza VehiclesDB",
        use_container_width=True
    ):

        with st.spinner("Se descarca VehiclesDB..."):

            success, message = ensure_external_database(
                VEHICLES_DB_PATH,
                VEHICLES_DB_URL,
                ["makes", "models"]
            )

        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    if st.button(
        "Descarca / actualizeaza catalogul de motoare",
        use_container_width=True
    ):

        with st.spinner("Se descarca baza de motoare..."):

            success, message = ensure_external_database(
                ENGINES_DB_PATH,
                ENGINES_DB_URL,
                [
                    "makes",
                    "models",
                    "generations",
                    "engines"
                ]
            )

        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.divider()

    st.subheader("Statistici catalog")

    stats = get_database_statistics()

    col1, col2 = st.columns(2)

    col1.metric("Marci", format_number(stats["marci"]))
    col2.metric("Modele", format_number(stats["modele"]))

    col3, col4 = st.columns(2)

    col3.metric("Generatii", format_number(stats["generatii"]))
    col4.metric("Motoare", format_number(stats["motoare"]))

    st.divider()

    st.subheader("Structura bazelor de date")

    for name, path in [
        ("VehiclesDB", VEHICLES_DB_PATH),
        ("Catalog motoare", ENGINES_DB_PATH),
        ("Coduri DTC", DTC_DB_PATH)
    ]:

        with st.expander(name):

            tables = get_database_tables(path)

            if tables:

                st.write("Tabele disponibile:")

                for table in tables:
                    st.write("- " + table)

                    conn = get_external_db(path)

                    if conn:

                        try:
                            columns = get_table_columns(
                                conn,
                                table
                            )

                            st.caption(
                                "Coloane: " + ", ".join(columns)
                            )

                        finally:
                            conn.close()

            else:
                st.info("Baza nu este disponibila.")

    st.divider()

    st.subheader("Surse si licente")

    st.markdown("""
    **VehiclesDB**
    - Proiect: https://github.com/vehiclesdb/vehiclesdb
    - Licenta: CC BY 4.0
    - Necesita atribuire.

    **Vehicle Makes, Models and Engines**
    - Proiect: https://github.com/gor3a/vehicle-makes-models
    - Licenta: ODbL 1.0
    - Respecta cerintele de atribuire si share-alike.

    **DTC Database**
    - Proiect: https://github.com/Wal33D/dtc-database
    - Licenta declarata: MIT.
    - Datasetul public documenteaza 18.805 definitii, 12.128 coduri unice si 33 de marci; valorile se pot modifica intre versiuni.

    **MechanicDB – mostra publica**
    - Proiect: https://github.com/MechanicDB/MechanicDB-public
    - Mostra gratuita: 90 coduri DTC si proceduri asociate; nu este baza completa comerciala.
    - Licenta datelor mostrei: ODbL 1.0, cu atribuire si share-alike.
    """)

    st.subheader("Surse adaugate manual")

    sources = get_local_table("data_sources")

    if not sources.empty:

        st.dataframe(
            sources,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("Nu exista surse manuale.")


# ============================================================
# MENIU PRINCIPAL
# ============================================================

PAGES = [
    "🏠 Dashboard",
    "🔎 Diagnosticare DTC",
    "📚 Biblioteca DTC",
    "🚘 Catalog vehicule",
    "⚙️ Date tehnice motor",
    "🛠️ Intretinere si service",
    "📊 Diagnosticare OBD-II",
    "🔧 Piese si compatibilitate",
    "📋 Cazuri de reparatii",
    "📖 Documentatie tehnica",
    "🗄️ Baze de date si surse"
]



def main():

    if "active_page" not in st.session_state:
        st.session_state["active_page"] = PAGES[0]

    st.sidebar.title("🚗 Auto Diagnosis Pro")
    st.sidebar.caption("Versiunea " + APP_VERSION)
    st.sidebar.divider()
    st.sidebar.subheader("Meniu principal")

    for index, page in enumerate(PAGES):
        if st.sidebar.button(
            page,
            key=f"adp_sidebar_navigation_button_{index}",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state["active_page"] == page
                else "secondary"
            )
        ):
            st.session_state["active_page"] = page
            st.rerun()

    st.sidebar.divider()
    st.sidebar.caption(
        "Platforma de asistenta pentru diagnosticare auto."
    )

    if st.sidebar.button(
        "Reincarca aplicatia",
        key="adp_reload_application",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    selected_page = st.session_state["active_page"]

    if selected_page == "🏠 Dashboard":
        page_dashboard()
    elif selected_page == "🔎 Diagnosticare DTC":
        page_dtc_diagnosis()
    elif selected_page == "📚 Biblioteca DTC":
        page_dtc_search()
    elif selected_page == "🚘 Catalog vehicule":
        page_vehicle_search()
    elif selected_page == "⚙️ Date tehnice motor":
        page_engine_data()
    elif selected_page == "🛠️ Intretinere si service":
        page_maintenance()
    elif selected_page == "📊 Diagnosticare OBD-II":
        page_advanced_obd()
    elif selected_page == "🔧 Piese si compatibilitate":
        page_parts()
    elif selected_page == "📋 Cazuri de reparatii":
        page_repairs()
    elif selected_page == "📖 Documentatie tehnica":
        page_workshop_reference()
    elif selected_page == "🗄️ Baze de date si surse":
        page_database_sources()


if __name__ == "__main__":
    main()



# ============================================================
# PORNIRE APLICATIE
# ============================================================


