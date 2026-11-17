
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path

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

DATA_DIR.mkdir(exist_ok=True)

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
# DATABASE CONNECTIONS
# =====================================================

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
            (dtc_code, title, symptoms, causes, checks, repair, notes)
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
            SELECT code, manufacturer, description,
                   type, locale, is_generic
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
        SELECT dtc_code, title, symptoms,
               causes, checks, repair, notes
        FROM diagnosis
        WHERE UPPER(dtc_code) = ?
        LIMIT 1
    """, (code.upper().strip(),))

    row = cursor.fetchone()

    if not row:
        return None

    keys = [
        "dtc_code", "title", "symptoms",
        "causes", "checks", "repair", "notes"
    ]

    return dict(zip(keys, row))


def get_statistics():

    conn = get_dtc_connection()

    if conn is None:
        return 0, 0

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM dtc_definitions")
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

        return [row[0] for row in cursor.fetchall()]

    except Exception:
        return []


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

st.sidebar.caption("Auto Diagnosis Pro")


# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":

    st.markdown(
        '<div class="main-title">🔧 Auto Diagnosis Pro</div>',
        unsafe_allow_html=True
    )

    st.write("Platformă de diagnostic și informații auto.")

    definitions, codes = get_statistics()

    conn = get_diagnosis_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM diagnosis")
    diagnosis_count = cursor.fetchone()[0]

    c1, c2, c3 = st.columns(3)

    c1.metric("Coduri DTC unice", f"{codes:,}")
    c2.metric("Definiții DTC", f"{definitions:,}")
    c3.metric("Fișe de diagnostic", diagnosis_count)

    st.markdown("---")

    st.subheader("Module disponibile")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("🔍 DTC Diagnosis\n\nDiagnostic detaliat al codurilor.")

    with col2:
        st.info("🔎 DTC Search\n\nCăutare în baza DTC.")

    with col3:
        st.info("🚗 Vehicle Search\n\nCăutare după vehicul.")

    col4, col5, col6 = st.columns(3)

    with col4:
        st.info("🛠️ Repair Cases\n\nCazuri și reparații.")

    with col5:
        st.info("🗄️ Database\n\nStatistici și baze de date.")

    with col6:
        st.info("📚 Diagnosis Library\n\nFișe de diagnostic dezvoltate.")


# =====================================================
# DTC DIAGNOSIS
# =====================================================

elif page == "DTC Diagnosis":

    st.title("🔍 DTC Diagnosis")

    st.write("Caută un cod de eroare pentru a vedea diagnosticul.")

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

    code = st.session_state.get("selected_dtc", code)

    if code:

        st.markdown("---")

        dtc_data = search_dtc(code)
        diagnosis = get_diagnosis(code)

        if selected_manufacturer != "Toți producătorii":
            if not dtc_data.empty:
                dtc_data = dtc_data[
                    dtc_data["manufacturer"] == selected_manufacturer
                ]

        if dtc_data.empty:

            st.error("Codul nu a fost găsit pentru filtrul selectat.")

        else:

            st.success(f"Codul {code} a fost găsit.")

            first = dtc_data.iloc[0]

            st.subheader(f"{code} — {first['description']}")

            st.write("**Producători și definiții disponibile:**")

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

    st.write("Caută după cod, descriere sau producător.")

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
                SELECT code, manufacturer, description,
                       type, locale, is_generic
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

                st.success(f"{len(df)} rezultate găsite.")

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

    st.info(
        "Modulul de căutare după vehicul este pregătit "
        "pentru integrarea bazei de date cu mărci, modele și motoare."
    )

    col1, col2 = st.columns(2)

    with col1:
        brand = st.selectbox(
            "Marcă",
            [
                "BMW", "Mercedes-Benz", "Audi",
                "Volkswagen", "Skoda", "Seat",
                "Ford", "Opel", "Renault",
                "Peugeot", "Toyota", "Volvo",
                "Other"
            ]
        )

    with col2:
        model = st.text_input("Model", placeholder="Exemplu: 320d")

    engine = st.text_input(
        "Motor / Cod motor",
        placeholder="Exemplu: B47"
    )

    year = st.text_input("An fabricație")

    if st.button("Caută vehicul"):

        st.warning(
            "Baza tehnică pentru vehicule nu este încă integrată. "
            "Datele introduse nu sunt salvate."
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

        st.success(f"Fișier disponibil: {DTC_DB_PATH.name}")

    else:

        st.error("dtc_codes.db nu există în folderul data.")

    st.markdown("---")

    st.subheader("Diagnosis Database")

    conn = get_diagnosis_connection()

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM diagnosis")
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

    st.caption(
        "Baza DTC este separată de baza de diagnostic. "
        "Fișele suplimentare nu modifică definițiile originale."
    )
