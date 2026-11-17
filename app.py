
import streamlit as st
import sqlite3
import pandas as pd
import urllib.request
from pathlib import Path
import os

# =====================================================
# CONFIGURARE
# =====================================================

st.set_page_config(
    page_title="Auto Diagnosis Pro",
    page_icon="🔧",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

DTC_DB_PATH = DATA_DIR / "dtc_codes.db"
DIAGNOSIS_DB_PATH = DATA_DIR / "diagnosis.db"
VEHICLES_DB_PATH = DATA_DIR / "vehicles.db"

DATA_DIR.mkdir(exist_ok=True)

VEHICLES_URL = (
    "https://github.com/vehiclesdb/vehiclesdb/"
    "releases/latest/download/catalog.sqlite"
)

VEHICLES_SOURCE = "https://github.com/vehiclesdb/vehiclesdb"


# =====================================================
# DESIGN
# =====================================================

st.markdown("""
<style>
.main-title {
    font-size: 32px;
    font-weight: bold;
    color: #2196F3;
}
.section-title {
    font-size: 23px;
    font-weight: bold;
    margin-top: 15px;
}
div[data-testid="stMetric"] {
    background-color: rgba(128,128,128,0.08);
    padding: 15px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


# =====================================================
# VEHICLES DATABASE - VALIDARE SI DESCARCARE
# =====================================================

def validate_vehicles_database(path):

    if not path.exists():
        return False, "Fișierul nu există."

    try:
        if path.stat().st_size < 100000:
            return False, "Fișierul este prea mic."

        with open(path, "rb") as file:
            header = file.read(16)

        if header != b"SQLite format 3\x00":
            return False, "Fișierul nu are format SQLite."

        conn = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True
        )

        cursor = conn.cursor()

        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()

        if not result or result[0] != "ok":
            conn.close()
            return False, "Verificarea SQLite a eșuat."

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """)

        tables = {
            row[0] for row in cursor.fetchall()
        }

        required_tables = {
            "makes",
            "models",
            "availability",
            "popularity",
            "meta"
        }

        if not required_tables.issubset(tables):
            conn.close()
            return False, "Lipsesc tabele necesare."

        conn.close()

        return True, None

    except Exception as e:
        return False, str(e)


def download_vehicles_database():

    temporary_path = DATA_DIR / "vehicles_download.tmp"

    try:

        request = urllib.request.Request(
            VEHICLES_URL,
            headers={
                "User-Agent": "Auto-Diagnosis-Pro/1.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=90
        ) as response:

            with open(temporary_path, "wb") as file:

                while True:
                    chunk = response.read(1024 * 1024)

                    if not chunk:
                        break

                    file.write(chunk)

        valid, error = validate_vehicles_database(
            temporary_path
        )

        if not valid:
            raise Exception(
                f"Baza descărcată nu este validă: {error}"
            )

        os.replace(
            temporary_path,
            VEHICLES_DB_PATH
        )

        return True, None

    except Exception as e:

        if temporary_path.exists():
            temporary_path.unlink()

        return False, str(e)


def prepare_vehicles_database():

    valid, error = validate_vehicles_database(
        VEHICLES_DB_PATH
    )

    if valid:
        return True, "Baza VehiclesDB existentă este validă."

    success, download_error = download_vehicles_database()

    if success:
        return True, "Baza VehiclesDB a fost descărcată și verificată."

    return False, (
        "Nu am putut pregăti baza VehiclesDB. "
        f"Motiv: {download_error}"
    )


# Verificăm și pregătim baza înainte de conectare.
vehicles_ready, vehicles_status = (
    prepare_vehicles_database()
)


# =====================================================
# DATABASE CONNECTIONS
# =====================================================

@st.cache_resource
def get_dtc_connection():

    if not DTC_DB_PATH.exists():
        return None

    try:
        return sqlite3.connect(
            f"file:{DTC_DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False
        )
    except sqlite3.Error:
        return None


@st.cache_resource
def get_vehicles_connection():

    if not vehicles_ready:
        return None

    try:
        return sqlite3.connect(
            f"file:{VEHICLES_DB_PATH}?mode=ro",
            uri=True,
            check_same_thread=False
        )
    except sqlite3.Error:
        return None


@st.cache_resource
def get_diagnosis_connection():

    conn = sqlite3.connect(
        DIAGNOSIS_DB_PATH,
        check_same_thread=False
    )

    create_diagnosis_database(conn)

    return conn


# =====================================================
# DIAGNOSIS DATABASE
# =====================================================

def create_diagnosis_database(conn):

    cursor = conn.cursor()

    cursor.execute("""
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

    insert_initial_diagnosis(conn)


def insert_initial_diagnosis(conn):

    data = [

        (
            "P0300",
            "Random / Multiple Cylinder Misfire Detected",
            """Motor neregulat.
Vibrații la ralanti.
Pierdere de putere.
Pornire dificilă.
Martor Check Engine.""",
            """Bujii uzate.
Bobină defectă.
Injector cu probleme.
Presiune combustibil incorectă.
Pierderi de vacuum.
Compresie scăzută.""",
            """1. Verifică freeze-frame.
2. Verifică misfire counters.
3. Verifică bujiile.
4. Testează bobinele.
5. Verifică injectoarele.
6. Măsoară presiunea combustibilului.
7. Verifică vacuumul.
8. Efectuează test de compresie dacă este necesar.""",
            """Remediază cauza confirmată.
Înlocuiește bujiile sau bobina dacă testele confirmă defectul.
Verifică injectoarele și alimentarea.
Remediază pierderile de aer.
Investigarea mecanică este necesară dacă există compresie scăzută.""",
            "Nu înlocui componente fără verificări."
        ),

        (
            "P0171",
            "System Too Lean - Bank 1",
            """Ralanti instabil.
Ezitări la accelerație.
Pierdere de putere.
Consum anormal.""",
            """Pierderi de vacuum.
Furtun admisie fisurat.
MAF contaminat.
Presiune combustibil insuficientă.
Injector cu debit redus.
Probleme PCV.""",
            """1. Verifică STFT și LTFT.
2. Verifică pierderile de vacuum.
3. Inspectează admisia.
4. Analizează valorile MAF.
5. Verifică presiunea combustibilului.
6. Verifică injectoarele.
7. Analizează senzorul O2.""",
            """Remediază pierderile de vacuum.
Repară furtunurile.
Curăță sau înlocuiește MAF numai dacă testele confirmă.
Verifică sistemul de alimentare.""",
            "Interpretează fuel trims în condiții de funcționare cunoscute."
        ),

        (
            "P0420",
            "Catalyst System Efficiency Below Threshold - Bank 1",
            """Martor Check Engine.
Uneori nu există simptome evidente.
Posibil consum crescut.
Posibil miros neobișnuit al gazelor.""",
            """Catalizator degradat.
Senzor O2 defect.
Scăpări pe evacuare.
Misfire repetat.
Amestec incorect.
Consum de ulei.""",
            """1. Verifică alte coduri DTC.
2. Verifică misfire.
3. Verifică fuel trims.
4. Verifică evacuarea.
5. Compară semnalele senzorilor O2.
6. Analizează datele live.""",
            """Identifică mai întâi cauza.
Remediază problemele de amestec sau misfire.
Înlocuiește catalizatorul numai dacă testele confirmă degradarea.""",
            "P0420 nu înseamnă automat catalizator defect."
        ),

        (
            "P0128",
            "Coolant Thermostat Below Regulating Temperature",
            """Motorul ajunge greu la temperatura normală.
Temperatura rămâne prea scăzută.
Încălzire slabă în habitaclu.
Consum posibil crescut.""",
            """Termostat blocat deschis.
Senzor ECT defect.
Nivel scăzut de lichid.
Probleme cablaj.""",
            """1. Verifică temperatura live.
2. Verifică nivelul lichidului.
3. Verifică termostatul.
4. Compară temperatura ECU cu măsurarea independentă.
5. Verifică senzorul ECT și cablajul.""",
            """Înlocuiește termostatul dacă testele confirmă defectul.
Verifică senzorul și circuitul dacă temperatura raportată este incorectă.""",
            "Ține cont de temperatura ambientală și de motor."
        ),

        (
            "P0101",
            "Mass Air Flow Circuit Range / Performance",
            """Ralanti instabil.
Ezitare la accelerație.
Pierdere de putere.
Consum crescut.""",
            """MAF contaminat sau defect.
Filtru de aer murdar.
Pierdere de aer după MAF.
Probleme PCV.
Probleme de cablaj.""",
            """1. Verifică admisia după MAF.
2. Verifică filtrul de aer.
3. Analizează valorile MAF live.
4. Verifică alimentarea și masa.
5. Verifică mufa și cablajul.
6. Compară valorile cu specificațiile motorului.""",
            """Remediază pierderile de aer.
Curăță MAF numai cu produs adecvat.
Înlocuiește senzorul doar dacă testele confirmă defectul.""",
            "Nu înlocui MAF doar pe baza codului."
        )

    ]

    cursor = conn.cursor()

    for item in data:

        cursor.execute("""
            INSERT OR IGNORE INTO diagnosis
            (
                dtc_code,
                title,
                symptoms,
                causes,
                checks,
                repair,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, item)

    conn.commit()


# =====================================================
# DTC FUNCTIONS
# =====================================================

def search_dtc(code):

    conn = get_dtc_connection()

    if conn is None:
        return pd.DataFrame()

    try:
        return pd.read_sql_query("""
            SELECT
                code,
                manufacturer,
                description,
                type,
                locale,
                is_generic
            FROM dtc_definitions
            WHERE UPPER(code) = ?
            ORDER BY manufacturer
        """, conn, params=(code.upper().strip(),))

    except Exception:
        return pd.DataFrame()


def get_diagnosis(code):

    conn = get_diagnosis_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            dtc_code,
            title,
            symptoms,
            causes,
            checks,
            repair,
            notes
        FROM diagnosis
        WHERE UPPER(dtc_code) = ?
        LIMIT 1
    """, (code.upper().strip(),))

    row = cursor.fetchone()

    if not row:
        return None

    keys = [
        "dtc_code",
        "title",
        "symptoms",
        "causes",
        "checks",
        "repair",
        "notes"
    ]

    return dict(zip(keys, row))


def get_statistics():

    conn = get_dtc_connection()

    if conn is None:
        return 0, 0

    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM dtc_definitions"
        )
        definitions = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT code) FROM dtc_definitions"
        )
        codes = cursor.fetchone()[0]

        return definitions, codes

    except Exception:
        return 0, 0


def get_manufacturers():

    conn = get_dtc_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT manufacturer
            FROM dtc_definitions
            WHERE manufacturer IS NOT NULL
            ORDER BY manufacturer
        """)

        return [
            row[0] for row in cursor.fetchall()
        ]

    except Exception:
        return []


# =====================================================
# VEHICLE FUNCTIONS
# =====================================================

def get_vehicle_statistics():

    conn = get_vehicles_connection()

    if conn is None:
        return 0, 0

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM makes")
        makes_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM models")
        models_count = cursor.fetchone()[0]

        return makes_count, models_count

    except sqlite3.Error:
        return 0, 0


def get_vehicle_kinds():

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT kind
            FROM makes
            ORDER BY kind
        """)

        return [
            row[0] for row in cursor.fetchall()
        ]

    except sqlite3.Error:
        return []


def get_vehicle_makes(kind):

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT name
            FROM makes
            WHERE kind = ?
            ORDER BY name
        """, (kind,))

        return [
            row[0] for row in cursor.fetchall()
        ]

    except sqlite3.Error:
        return []


def search_vehicles(kind, make, search_text, selected_year=0):

    conn = get_vehicles_connection()

    if conn is None:
        return pd.DataFrame()

    query = """
        SELECT
            m.kind AS category,
            mk.name AS make,
            m.name AS model,
            m.body_types AS body_types,
            m.year_start AS year_start,
            m.year_end AS year_end,
            GROUP_CONCAT(
                DISTINCT a.country
            ) AS countries

        FROM models m

        JOIN makes mk
            ON mk.id = m.make_id
            AND mk.kind = m.kind

        LEFT JOIN availability a
            ON a.model_id = m.id
            AND a.kind = m.kind

        WHERE m.kind = ?
    """

    params = [kind]

    if make != "Toate mărcile":
        query += " AND mk.name = ?"
        params.append(make)

    if search_text.strip():
        query += " AND LOWER(m.name) LIKE ?"
        params.append(
            f"%{search_text.strip().lower()}%"
        )

    if selected_year > 0:
        query += """
            AND (
                m.year_start IS NULL
                OR m.year_start <= ?
            )
            AND (
                m.year_end IS NULL
                OR m.year_end = 0
                OR m.year_end >= ?
            )
        """
        params.extend([selected_year, selected_year])

    query += """
        GROUP BY
            m.id,
            m.kind,
            mk.name,
            m.name,
            m.body_types,
            m.year_start,
            m.year_end

        ORDER BY mk.name, m.name
    """

    try:
        return pd.read_sql_query(
            query,
            conn,
            params=params
        )

    except Exception as e:
        st.error(f"Eroare la căutarea vehiculelor: {e}")
        return pd.DataFrame()


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.markdown("## 🔧 Auto Diagnosis Pro")
st.sidebar.caption("Automotive Diagnostic Database")

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

if DIAGNOSIS_DB_PATH.exists():
    st.sidebar.success("Diagnosis Database: OK")

if vehicles_ready:
    st.sidebar.success("Vehicle Database: OK")
else:
    st.sidebar.error("Vehicle Database: Error")

st.sidebar.caption("Auto Diagnosis Pro")


# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":

    st.markdown(
        '<div class="main-title">🔧 Auto Diagnosis Pro</div>',
        unsafe_allow_html=True
    )

    st.write(
        "Platformă de diagnostic și informații auto."
    )

    definitions, codes = get_statistics()

    makes_count, models_count = (
        get_vehicle_statistics()
    )

    conn = get_diagnosis_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM diagnosis"
    )
    diagnosis_count = cursor.fetchone()[0]

    c1, c2, c3 = st.columns(3)

    c1.metric("Coduri DTC unice", f"{codes:,}")
    c2.metric("Definiții DTC", f"{definitions:,}")
    c3.metric("Fișe de diagnostic", diagnosis_count)

    st.markdown("---")

    st.subheader("Baza de date vehicule")

    v1, v2 = st.columns(2)

    v1.metric("Mărci auto", f"{makes_count:,}")
    v2.metric("Modele auto", f"{models_count:,}")

    if vehicles_ready:
        st.success(vehicles_status)
    else:
        st.error(vehicles_status)

    st.markdown("---")

    st.subheader("Module disponibile")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info(
            "🔍 DTC Diagnosis\n\n"
            "Diagnostic detaliat al codurilor."
        )

    with col2:
        st.info(
            "🔎 DTC Search\n\n"
            "Căutare în baza DTC."
        )

    with col3:
        st.info(
            "🚗 Vehicle Search\n\n"
            "Căutare după vehicul."
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        st.info(
            "🛠️ Repair Cases\n\n"
            "Cazuri și reparații."
        )

    with col5:
        st.info(
            "🗄️ Database\n\n"
            "Statistici și baze de date."
        )

    with col6:
        st.info(
            "📚 Diagnosis Library\n\n"
            "Fișe de diagnostic dezvoltate."
        )


# =====================================================
# DTC DIAGNOSIS
# =====================================================

elif page == "DTC Diagnosis":

    st.title("🔍 DTC Diagnosis")

    st.write(
        "Caută un cod de eroare pentru a vedea diagnosticul."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        code = st.text_input(
            "Introdu codul DTC",
            placeholder="Exemplu: P0300"
        ).strip().upper()

    manufacturers = get_manufacturers()

    with col2:
        selected_manufacturer = st.selectbox(
            "Producător",
            ["Toți producătorii"] + manufacturers
        )

    if st.button("🔎 Caută codul", type="primary") and code:
        st.session_state["selected_dtc"] = code

    code = st.session_state.get(
        "selected_dtc",
        code
    )

    if code:

        st.markdown("---")

        dtc_data = search_dtc(code)
        diagnosis = get_diagnosis(code)

        if selected_manufacturer != "Toți producătorii":
            if not dtc_data.empty:
                dtc_data = dtc_data[
                    dtc_data["manufacturer"]
                    == selected_manufacturer
                ]

        if dtc_data.empty:

            st.error(
                "Codul nu a fost găsit pentru filtrul selectat."
            )

        else:

            st.success(f"Codul {code} a fost găsit.")

            first = dtc_data.iloc[0]

            st.subheader(
                f"{code} — {first['description']}"
            )

            st.write(
                "**Producători și definiții disponibile:**"
            )

            st.dataframe(
                dtc_data,
                use_container_width=True,
                hide_index=True
            )

            if diagnosis:

                st.markdown("---")
                st.subheader("⚠️ Simptome posibile")
                st.write(diagnosis["symptoms"])

                st.markdown("---")
                st.subheader("🔎 Cauze posibile")
                st.write(diagnosis["causes"])

                st.markdown("---")
                st.subheader("🧪 Verificări recomandate")
                st.write(diagnosis["checks"])

                st.markdown("---")
                st.subheader("🔧 Rezolvare")
                st.write(diagnosis["repair"])

                st.markdown("---")
                st.subheader("ℹ️ Observații")
                st.info(diagnosis["notes"])

            else:

                st.warning(
                    "Există descrierea codului, dar nu există încă "
                    "o fișă suplimentară de diagnostic."
                )


# =====================================================
# DTC SEARCH
# =====================================================

elif page == "DTC Search":

    st.title("🔎 DTC Search")

    st.write(
        "Caută după cod, descriere sau producător."
    )

    search = st.text_input(
        "Termen de căutare",
        placeholder="P0300, misfire, BMW..."
    )

    manufacturers = get_manufacturers()

    manufacturer = st.selectbox(
        "Filtrează după producător",
        ["Toți producătorii"] + manufacturers
    )

    if search:

        conn = get_dtc_connection()

        if conn is None:

            st.error("Baza DTC nu a fost găsită.")

        else:

            query = """
                SELECT
                    code,
                    manufacturer,
                    description,
                    type,
                    locale,
                    is_generic

                FROM dtc_definitions

                WHERE (
                    UPPER(code) LIKE ?
                    OR LOWER(description) LIKE ?
                    OR LOWER(manufacturer) LIKE ?
                )
            """

            params = [
                f"%{search.upper()}%",
                f"%{search.lower()}%",
                f"%{search.lower()}%"
            ]

            if manufacturer != "Toți producătorii":
                query += " AND manufacturer = ?"
                params.append(manufacturer)

            query += " ORDER BY code LIMIT 300"

            try:

                df = pd.read_sql_query(
                    query,
                    conn,
                    params=params
                )

                st.success(
                    f"{len(df)} rezultate găsite."
                )

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

            except Exception as e:

                st.error(f"Eroare la căutare: {e}")


# =====================================================
# VEHICLE SEARCH
# =====================================================

elif page == "Vehicle Search":

    st.title("🚗 Vehicle Search")

    st.write(
        "Caută toate mărcile și modelele disponibile în VehiclesDB."
    )

    if not vehicles_ready:

        st.error(vehicles_status)

        if st.button("Încearcă din nou descărcarea"):
            st.cache_resource.clear()
            st.rerun()

    else:

        makes_count, models_count = (
            get_vehicle_statistics()
        )

        c1, c2 = st.columns(2)

        c1.metric(
            "Mărci în baza de date",
            f"{makes_count:,}"
        )

        c2.metric(
            "Modele în baza de date",
            f"{models_count:,}"
        )

        st.markdown("---")

        kinds = get_vehicle_kinds()

        kind_labels = {
            "car": "Autoturisme",
            "motorcycle": "Motociclete",
            "moped": "Mopede",
            "van": "Autoutilitare",
            "truck": "Camioane",
            "bus": "Autobuze"
        }

        if kinds:

            st.subheader("Filtre de căutare")

            selected_kind = st.selectbox(
                "Categorie vehicul",
                kinds,
                format_func=lambda x: kind_labels.get(
                    x,
                    x.capitalize()
                )
            )

            makes = get_vehicle_makes(selected_kind)

            selected_make = st.selectbox(
                "Marcă",
                ["Toate mărcile"] + makes
            )

            model_search = st.text_input(
                "Numele modelului",
                placeholder="Exemplu: Golf, Corolla, Focus..."
            )

            selected_year = st.number_input(
                "An de fabricație (0 = toți anii)",
                min_value=0,
                max_value=2100,
                value=0,
                step=1
            )

            st.caption(
                "Poți afișa toate modelele sau poți combina filtrele."
            )

            if st.button(
                "🔎 Afișează toate modelele",
                type="primary"
            ):

                results = search_vehicles(
                    selected_kind,
                    selected_make,
                    model_search,
                    selected_year
                )

                if results.empty:

                    st.warning(
                        "Nu am găsit modele pentru criteriile selectate."
                    )

                else:

                    st.success(
                        f"Au fost găsite {len(results):,} modele."
                    )

                    st.dataframe(
                        results,
                        use_container_width=True,
                        hide_index=True,
                        height=650
                    )

                    st.caption(
                        "Sunt afișate toate rezultatele găsite. "
                        "Nu există o limită artificială de 500 de modele."
                    )

                    csv_data = results.to_csv(
                        index=False
                    ).encode("utf-8-sig")

                    st.download_button(
                        label="📥 Descarcă rezultatele CSV",
                        data=csv_data,
                        file_name="vehicle_models.csv",
                        mime="text/csv"
                    )

        else:

            st.warning(
                "Nu am putut identifica tipurile de vehicule."
            )

        st.markdown("---")

        st.markdown(
            f"[Sursa datelor: VehiclesDB]({VEHICLES_SOURCE})"
        )

        st.caption(
            "Date VehiclesDB utilizate conform licenței CC BY 4.0."
        )


# =====================================================
# REPAIR CASES
# =====================================================

elif page == "Repair Cases":

    st.title("🛠️ Repair Cases")

    st.info(
        "Modulul va permite adăugarea cazurilor reale din service."
    )

    st.write("Funcții planificate:")

    st.markdown("""
    - Înregistrare vehicul și motorizare
    - Coduri DTC întâlnite
    - Simptome constatate
    - Cauza confirmată
    - Reparația efectuată
    - Fotografii și documente PDF
    - Rezultatul după reparație
    """)

    st.warning(
        "Salvarea cazurilor reale nu este activată încă."
    )


# =====================================================
# DATABASE
# =====================================================

elif page == "Database":

    st.title("🗄️ Database Management")

    definitions, codes = get_statistics()

    st.subheader("DTC Database")

    if DTC_DB_PATH.exists():

        c1, c2 = st.columns(2)

        c1.metric("Coduri unice", f"{codes:,}")
        c2.metric("Definiții", f"{definitions:,}")

        st.success(
            f"Fișier disponibil: {DTC_DB_PATH.name}"
        )

    else:

        st.error(
            "dtc_codes.db nu există în folderul data."
        )

    st.markdown("---")

    st.subheader("Diagnosis Database")

    conn = get_diagnosis_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM diagnosis"
    )

    count = cursor.fetchone()[0]

    st.metric("Fișe de diagnostic", count)

    df = pd.read_sql_query("""
        SELECT dtc_code, title
        FROM diagnosis
        ORDER BY dtc_code
    """, conn)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    st.subheader("Vehicle Database")

    if vehicles_ready:

        makes_count, models_count = (
            get_vehicle_statistics()
        )

        st.success(vehicles_status)

        v1, v2 = st.columns(2)

        v1.metric("Mărci", f"{makes_count:,}")
        v2.metric("Modele", f"{models_count:,}")

        st.markdown(
            f"[Sursa datelor: VehiclesDB]({VEHICLES_SOURCE})"
        )

        st.caption(
            f"Fișier: {VEHICLES_DB_PATH.name}"
        )

    else:

        st.error(vehicles_status)

        if st.button("Descarcă din nou baza VehiclesDB"):
            st.cache_resource.clear()
            st.rerun()

    st.markdown("---")

    st.caption(
        "Baza DTC, baza de diagnostic și baza de vehicule "
        "sunt fișiere separate. Datele originale nu sunt modificate."
    )
