import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd

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

DTC_DB_PATH = DATA_DIR / "dtc_codes.db"
DIAGNOSIS_DB_PATH = DATA_DIR / "diagnosis.db"

DATA_DIR.mkdir(exist_ok=True)


# =========================================================
# CONECTARE DATABASE
# =========================================================

@st.cache_resource
def get_dtc_connection():
    if not DTC_DB_PATH.exists():
        return None

    return sqlite3.connect(
        f"file:{DTC_DB_PATH}?mode=ro",
        uri=True,
        check_same_thread=False
    )


@st.cache_resource
def get_diagnosis_connection():
    conn = sqlite3.connect(
        DIAGNOSIS_DB_PATH,
        check_same_thread=False
    )

    create_diagnosis_database(conn)

    return conn


# =========================================================
# CREARE BAZA DE DIAGNOSTIC
# =========================================================

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


# =========================================================
# DATE INITIALE DE DIAGNOSTIC
# =========================================================

def insert_initial_diagnosis(conn):

    cursor = conn.cursor()

    data = [

        (
            "P0300",
            "Random / Multiple Cylinder Misfire Detected",

            """Motorul poate funcționa neregulat.
Pot apărea vibrații la ralanti.
Poate exista pierdere de putere.
Martorul Check Engine poate fi aprins.
În unele situații motorul poate porni greu.""",

            """Bujii uzate sau deteriorate.
Bobină de inducție defectă.
Injector cu debit incorect.
Presiune combustibil insuficientă.
Admisie de aer fals.
Compresie scăzută pe unul sau mai mulți cilindri.
Probleme de sincronizare.
Probleme ale sistemului de aprindere.""",

            """1. Verifică freeze-frame-ul codului.
2. Verifică misfire counters pentru fiecare cilindru.
3. Verifică starea bujiilor.
4. Verifică bobinele de inducție.
5. Verifică injectoarele.
6. Verifică presiunea combustibilului.
7. Verifică eventualele pierderi de vacuum.
8. Dacă problema persistă, efectuează test de compresie.
9. Verifică sincronizarea motorului dacă există indicii.""",

            """Repararea trebuie făcută în funcție de cauza confirmată.

Înlocuiește bujiile dacă sunt uzate.
Înlocuiește bobina defectă.
Verifică sau înlocuiește injectorul defect.
Remediază pierderile de aer.
Remediază problema de alimentare cu combustibil.
Dacă există compresie scăzută, este necesară investigarea mecanică a motorului.""",

            "Nu înlocui componente la întâmplare. Confirmă cauza prin teste."
        ),

        (
            "P0171",
            "System Too Lean - Bank 1",

            """Ralanti instabil.
Motorul poate avea ezitări la accelerație.
Poate apărea pierdere de putere.
Consum crescut în anumite situații.
Martor Check Engine aprins.""",

            """Pierdere de vacuum.
Furtun de admisie fisurat.
Debitmetru MAF contaminat sau defect.
Presiune combustibil insuficientă.
Injector cu debit redus.
Senzor O2/A/F cu funcționare incorectă.
Probleme ale sistemului PCV.""",

            """1. Verifică fuel trims STFT și LTFT.
2. Verifică eventualele pierderi de vacuum.
3. Inspectează furtunurile de admisie.
4. Verifică valorile MAF.
5. Verifică presiunea combustibilului.
6. Verifică injectoarele.
7. Analizează valorile senzorului O2/A/F.
8. Compară comportamentul motorului la ralanti și la turație.""",

            """Remediază cauza confirmată.

Repară furtunurile fisurate.
Remediază pierderile de vacuum.
Curăță sau înlocuiește MAF dacă testele confirmă problema.
Remediază alimentarea cu combustibil.
Verifică sau înlocuiește injectorul defect.""",

            "Fuel trims trebuie interpretate împreună cu condițiile de funcționare ale motorului."
        ),

        (
            "P0420",
            "Catalyst System Efficiency Below Threshold - Bank 1",

            """Martor Check Engine.
Uneori nu există simptome evidente.
Poate apărea consum crescut.
În anumite situații pot exista probleme de performanță sau miros neobișnuit al gazelor.""",

            """Catalizator degradat.
Senzor O2 defect.
Scăpări pe evacuare.
Motor care funcționează cu amestec incorect.
Misfire-uri repetate.
Consum de ulei.
Probleme ale sistemului de alimentare.""",

            """1. Verifică existența altor coduri DTC.
2. Verifică misfire-urile.
3. Verifică fuel trims.
4. Verifică eventualele scăpări pe evacuare.
5. Compară semnalele senzorilor O2.
6. Verifică temperatura catalizatorului.
7. Analizează datele live înainte de a condamna catalizatorul.""",

            """Nu înlocui direct catalizatorul.

Identifică mai întâi cauza care a dus la eficiență redusă.
Dacă testele confirmă degradarea catalizatorului, acesta poate necesita înlocuire.""",

            "Un P0420 nu înseamnă automat că senzorul O2 este defect sau că trebuie schimbat imediat catalizatorul."
        ),

        (
            "P0128",
            "Coolant Thermostat / Coolant Temperature Below Regulating Temperature",

            """Motorul ajunge greu la temperatura normală.
Temperatura poate rămâne prea scăzută.
Încălzirea habitaclului poate fi slabă.
Consum crescut de combustibil în anumite condiții.""",

            """Termostat blocat deschis.
Senzor temperatură lichid răcire cu valori incorecte.
Nivel scăzut al lichidului de răcire.
Probleme ale circuitului de răcire.
Probleme de cablaj sau conector.""",

            """1. Verifică temperatura reală a motorului.
2. Compară temperatura ECU cu temperatura măsurată.
3. Verifică nivelul lichidului de răcire.
4. Verifică funcționarea termostatului.
5. Verifică senzorul ECT.
6. Verifică mufa și cablajul senzorului.""",

            """Dacă termostatul este blocat deschis și testele confirmă problema, înlocuiește termostatul.

Dacă temperatura raportată este incorectă, verifică senzorul ECT și circuitul acestuia.""",

            "Interpretarea temperaturii trebuie făcută în funcție de motor și temperatura ambientală."
        ),

        (
            "P0101",
            "Mass or Volume Air Flow Circuit Range / Performance",

            """Ralanti instabil.
Ezitare la accelerație.
Pierdere de putere.
Consum crescut.
Motorul poate funcționa cu amestec incorect.""",

            """MAF contaminat.
MAF defect.
Filtru de aer foarte murdar.
Pierdere de aer după MAF.
Probleme de alimentare.
Probleme de cablaj sau conector.
Probleme ale sistemului PCV.""",

            """1. Verifică furtunul dintre MAF și clapeta de accelerație.
2. Verifică eventualele pierderi de aer.
3. Verifică filtrul de aer.
4. Analizează valorile MAF live.
5. Verifică alimentarea și masa senzorului.
6. Verifică conectorul și cablajul.
7. Compară valorile MAF cu valorile așteptate pentru motor.""",

            """Curăță MAF doar dacă procedura este permisă pentru senzorul respectiv.

Dacă testele confirmă defectarea senzorului, acesta poate necesita înlocuire.

Remediază orice pierdere de aer înainte de înlocuirea MAF.""",

            "Nu înlocui MAF doar pe baza codului P0101."
        )
    ]

    for item in data:

        cursor.execute("""
            INSERT OR IGNORE INTO diagnosis (
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


# =========================================================
# FUNCȚII DTC
# =========================================================

def search_dtc(code):

    conn = get_dtc_connection()

    if conn is None:
        return pd.DataFrame()

    query = """
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
    """

    try:
        return pd.read_sql_query(
            query,
            conn,
            params=(code.upper().strip(),)
        )
    except Exception:
        return pd.DataFrame()


def get_diagnosis(code):

    conn = get_diagnosis_connection()

    query = """
        SELECT *
        FROM diagnosis
        WHERE UPPER(dtc_code) = ?
        LIMIT 1
    """

    cursor = conn.cursor()

    cursor.execute(
        query,
        (code.upper().strip(),)
    )

    row = cursor.fetchone()

    if row is None:
        return None

    columns = [
        "id",
        "dtc_code",
        "title",
        "symptoms",
        "causes",
        "checks",
        "repair",
        "notes"
    ]

    return dict(zip(columns, row))


def get_dtc_statistics():

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


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🔧 Auto Diagnosis Pro")

page = st.sidebar.radio(
    "Meniu",
    [
        "Dashboard",
        "DTC Diagnosis",
        "DTC Search",
        "Database"
    ]
)

st.sidebar.markdown("---")

if DTC_DB_PATH.exists():
    st.sidebar.success("DTC Database: OK")
else:
    st.sidebar.error("DTC Database: lipsă")

if DIAGNOSIS_DB_PATH.exists():
    st.sidebar.success("Diagnosis Database: OK")


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    st.title("🔧 Auto Diagnosis Pro")

    st.subheader("Sistem de diagnostic auto")

    definitions, codes = get_dtc_statistics()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Coduri DTC",
            f"{codes:,}"
        )

    with col2:
        st.metric(
            "Definiții",
            f"{definitions:,}"
        )

    with col3:
        conn = get_diagnosis_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM diagnosis"
        )

        diagnostic_count = cursor.fetchone()[0]

        st.metric(
            "Diagnostice dezvoltate",
            diagnostic_count
        )

    st.markdown("---")

    st.info(
        "Baza DTC furnizează codurile și descrierile. "
        "Baza Diagnosis adaugă simptome, cauze, verificări și soluții."
    )


# =========================================================
# DTC DIAGNOSIS
# =========================================================

elif page == "DTC Diagnosis":

    st.title("🔍 DTC Diagnosis")

    st.write(
        "Introdu codul de eroare pentru a vedea informațiile disponibile."
    )

    code = st.text_input(
        "Cod DTC",
        placeholder="Exemplu: P0300"
    ).upper().strip()

    if code:

        st.markdown("---")

        dtc_data = search_dtc(code)

        diagnosis = get_diagnosis(code)

        if dtc_data.empty:

            st.error(
                f"Codul {code} nu a fost găsit în baza DTC."
            )

        else:

            st.success(
                f"Codul {code} a fost găsit."
            )

            first = dtc_data.iloc[0]

            st.subheader(
                f"{code} — {first['description']}"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(
                    "**Producător:**",
                    first["manufacturer"]
                )

            with col2:
                st.write(
                    "**Tip:**",
                    first["type"]
                )

            with col3:
                st.write(
                    "**Generic:**",
                    first["is_generic"]
                )

            st.markdown("---")

            if diagnosis:

                st.subheader("⚠️ Simptome posibile")

                st.write(
                    diagnosis["symptoms"]
                )

                st.markdown("---")

                st.subheader("🔎 Cauze posibile")

                st.write(
                    diagnosis["causes"]
                )

                st.markdown("---")

                st.subheader("🧪 Verificări recomandate")

                st.write(
                    diagnosis["checks"]
                )

                st.markdown("---")

                st.subheader("🔧 Rezolvare")

                st.write(
                    diagnosis["repair"]
                )

                st.markdown("---")

                st.subheader("ℹ️ Observații")

                st.info(
                    diagnosis["notes"]
                )

            else:

                st.warning(
                    "Pentru acest cod există descriere în baza DTC, "
                    "dar încă nu avem o fișă de diagnostic proprie."
                )

                st.info(
                    "Putem adăuga ulterior simptome, cauze, teste și rezolvare."
                )


# =========================================================
# DTC SEARCH
# =========================================================

elif page == "DTC Search":

    st.title("🔎 DTC Search")

    search = st.text_input(
        "Caută cod sau descriere",
        placeholder="Exemplu: P0300 sau misfire"
    )

    if search:

        conn = get_dtc_connection()

        if conn is None:

            st.error(
                "Baza DTC nu a fost găsită."
            )

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
                WHERE
                    UPPER(code) LIKE ?
                    OR LOWER(description) LIKE ?
                ORDER BY code
                LIMIT 200
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=(
                    f"%{search.upper()}%",
                    f"%{search.lower()}%"
                )
            )

            if df.empty:

                st.warning(
                    "Nu au fost găsite rezultate."
                )

            else:

                st.success(
                    f"{len(df)} rezultate găsite."
                )

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# DATABASE
# =========================================================

elif page == "Database":

    st.title("🗄️ Database")

    definitions, codes = get_dtc_statistics()

    st.subheader("DTC Database")

    if DTC_DB_PATH.exists():

        st.success(
            "Baza DTC este disponibilă."
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Coduri unice",
                f"{codes:,}"
            )

        with col2:
            st.metric(
                "Definiții",
                f"{definitions:,}"
            )

    else:

        st.error(
            "Fișierul dtc_codes.db nu a fost găsit."
        )

    st.markdown("---")

    st.subheader("Diagnosis Database")

    conn = get_diagnosis_connection()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM diagnosis"
    )

    count = cursor.fetchone()[0]

    st.success(
        f"Diagnosis database activă — {count} fișe de diagnostic."
    )

    if count > 0:

        df = pd.read_sql_query(
            """
            SELECT
                dtc_code,
                title
            FROM diagnosis
            ORDER BY dtc_code
            """,
            conn
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )
