
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
VEHICLES_DB_PATH = DATA_DIR / "vehicles.db"

DATA_DIR.mkdir(exist_ok=True)

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
def get_vehicles_connection():
    if not VEHICLES_DB_PATH.exists():
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
# VEHICLE DATABASE FUNCTIONS
# =====================================================

def get_vehicle_statistics():

    conn = get_vehicles_connection()

    if conn is None:
        return 0, 0

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM makes
            WHERE kind = 'car'
        """)
        makes_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM models
            WHERE kind = 'car'
        """)
        models_count = cursor.fetchone()[0]

        return makes_count, models_count

    except sqlite3.Error:
        return 0, 0


def get_vehicle_makes():

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name
            FROM makes
            WHERE kind = 'car'
            ORDER BY name COLLATE NOCASE
        """)

        return cursor.fetchall()

    except sqlite3.Error:
        return []


def get_vehicle_models(make_id):

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name
            FROM models
            WHERE kind = 'car'
              AND make_id = ?
            ORDER BY name COLLATE NOCASE
        """, (make_id,))

        return cursor.fetchall()

    except sqlite3.Error:
        return []


def get_vehicle_countries():

    conn = get_vehicles_connection()

    if conn is None:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT country
            FROM availability
            WHERE kind = 'car'
            ORDER BY country
        """)

        return [
            row[0].upper()
            for row in cursor.fetchall()
            if row[0]
        ]

    except sqlite3.Error:
        return []


def search_vehicles(make_id=None, model_id=None,
                    year=None, country=None):

    conn = get_vehicles_connection()

    if conn is None:
        return pd.DataFrame()

    query = """
        SELECT
            models.id AS model_id,
            makes.name AS make,
            models.name AS model,
            models.body_types AS body_types,
            models.regions AS regions,
            models.global_popularity_decile AS popularity,
            models.lifecycle_status AS lifecycle_status,
            models.year_start AS year_start,
            models.year_end AS year_end,
            models.year_start_planned AS year_start_planned,
            models.year_end_planned AS year_end_planned
        FROM models
        INNER JOIN makes
            ON models.make_id = makes.id
           AND models.kind = makes.kind
        WHERE models.kind = 'car'
    """

    params = []

    if make_id:
        query += " AND models.make_id = ?"
        params.append(make_id)

    if model_id:
        query += " AND models.id = ?"
        params.append(model_id)

    if year:
        query += """
            AND (
                models.year_start IS NULL
                OR models.year_start <= ?
            )
            AND (
                models.year_end IS NULL
                OR models.year_end >= ?
            )
        """
        params.extend([year, year])

    if country:
        query += """
            AND EXISTS (
                SELECT 1
                FROM availability
                WHERE availability.model_id = models.id
                  AND availability.kind = models.kind
                  AND UPPER(availability.country) = ?
            )
        """
        params.append(country.upper())

    query += " ORDER BY makes.name, models.name LIMIT 500"

    try:
        return pd.read_sql_query(
            query,
            conn,
            params=params
        )
    except Exception:
        return pd.DataFrame()


def get_vehicle_availability(model_id):

    conn = get_vehicles_connection()

    if conn is None:
        return pd.DataFrame()

    try:
        return pd.read_sql_query("""
            SELECT country, evidence, source
            FROM availability
            WHERE model_id = ?
              AND kind = 'car'
            ORDER BY country
        """, conn, params=(model_id,))
    except Exception:
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

if VEHICLES_DB_PATH.exists():
    st.sidebar.success("Vehicle Database: OK")
else:
    st.sidebar.error("Vehicle Database: Missing")

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
    makes_count, models_count = get_vehicle_statistics()

    conn = get_diagnosis_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM diagnosis")
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

    conn = get_vehicles_connection()

    if conn is None:

        st.error("Nu am putut deschide vehicles.db.")

        st.write(
            "Verifică dacă fișierul vehicles.db există în folderul data."
        )

    else:

        makes = get_vehicle_makes()
        countries = get_vehicle_countries()

        if not makes:

            st.error(
                "Nu am găsit mărcile auto în baza vehicles.db. "
                "Este posibil ca structura fișierului să fie diferită."
            )

        else:

            st.write(
                "Selectează marca, modelul și anul pentru a căuta vehiculul."
            )

            make_options = [
                ("", "Toate mărcile")
            ] + makes

            selected_make = st.selectbox(
                "Marcă auto",
                make_options,
                format_func=lambda item: item[1]
            )

            make_id = selected_make[0] if selected_make[0] else None

            model_options = [("", "Toate modelele")]

            if make_id:
                model_options += get_vehicle_models(make_id)

            selected_model = st.selectbox(
                "Model",
                model_options,
                format_func=lambda item: item[1]
            )

            model_id = (
                selected_model[0]
                if selected_model[0]
                else None
            )

            col1, col2 = st.columns(2)

            with col1:

                selected_year = st.number_input(
                    "An fabricație (opțional)",
                    min_value=1950,
                    max_value=2035,
                    value=None,
                    step=1,
                    placeholder="Lasă necompletat pentru toți anii"
                )

            with col2:

                country_options = ["Toate țările"] + countries

                selected_country = st.selectbox(
                    "Țara în care modelul este documentat",
                    country_options
                )

            country_filter = (
                None
                if selected_country == "Toate țările"
                else selected_country
            )

            st.markdown("---")

            if st.button("🔎 Caută vehicul", type="primary"):

                year_filter = (
                    int(selected_year)
                    if selected_year is not None
                    else None
                )

                results = search_vehicles(
                    make_id=make_id,
                    model_id=model_id,
                    year=year_filter,
                    country=country_filter
                )

                st.session_state["vehicle_results"] = results

                st.session_state["vehicle_search_done"] = True

            if st.session_state.get("vehicle_search_done"):

                results = st.session_state.get(
                    "vehicle_results",
                    pd.DataFrame()
                )

                st.markdown("---")

                if results.empty:

                    st.warning(
                        "Nu am găsit rezultate pentru criteriile selectate."
                    )

                else:

                    st.success(
                        f"Am găsit {len(results)} rezultate."
                    )

                    display_df = results.rename(columns={
                        "make": "Marcă",
                        "model": "Model",
                        "body_types": "Caroserie",
                        "regions": "Regiuni",
                        "popularity": "Popularitate",
                        "lifecycle_status": "Status",
                        "year_start": "Început producție",
                        "year_end": "Sfârșit producție",
                        "year_start_planned": "Început planificat",
                        "year_end_planned": "Sfârșit planificat"
                    })

                    columns_to_show = [
                        "Marcă",
                        "Model",
                        "Caroserie",
                        "Început producție",
                        "Sfârșit producție",
                        "Status"
                    ]

                    st.dataframe(
                        display_df[columns_to_show],
                        use_container_width=True,
                        hide_index=True
                    )

                    st.caption(
                        "Anii afișați reprezintă informații despre "
                        "ciclul de producție atunci când sunt disponibile. "
                        "Nu sunt o confirmare a anului exact al unui vehicul."
                    )

                    st.markdown("---")
                    st.subheader("Detalii vehicul")

                    selected_result = st.selectbox(
                        "Alege modelul pentru detalii",
                        range(len(results)),
                        format_func=lambda i: (
                            f"{results.iloc[i]['make']} "
                            f"{results.iloc[i]['model']}"
                        )
                    )

                    vehicle = results.iloc[selected_result]

                    st.subheader(
                        f"{vehicle['make']} {vehicle['model']}"
                    )

                    d1, d2, d3 = st.columns(3)

                    d1.metric(
                        "Început producție",
                        vehicle["year_start"]
                        if pd.notna(vehicle["year_start"])
                        else "Necunoscut"
                    )

                    d2.metric(
                        "Sfârșit producție",
                        vehicle["year_end"]
                        if pd.notna(vehicle["year_end"])
                        else "Necunoscut / în producție"
                    )

                    d3.metric(
                        "Status",
                        vehicle["lifecycle_status"]
                        if pd.notna(vehicle["lifecycle_status"])
                        else "Nespecificat"
                    )

                    if pd.notna(vehicle["body_types"]):
                        st.write(
                            "**Tipuri de caroserie:**",
                            vehicle["body_types"]
                        )

                    if pd.notna(vehicle["regions"]):
                        st.write(
                            "**Regiuni:**",
                            vehicle["regions"]
                        )

                    if pd.notna(vehicle["popularity"]):
                        st.write(
                            "**Indice popularitate:**",
                            vehicle["popularity"]
                        )

                    availability = get_vehicle_availability(
                        vehicle["model_id"]
                    )

                    st.markdown("---")
                    st.subheader("Disponibilitate pe țări")

                    if availability.empty:

                        st.info(
                            "Nu există informații de disponibilitate "
                            "pentru acest model."
                        )

                    else:

                        st.dataframe(
                            availability,
                            use_container_width=True,
                            hide_index=True
                        )

                    st.caption(
                        "Datele despre vehicule sunt furnizate de "
                        "VehiclesDB, sub licență CC BY 4.0."
                    )

                    st.markdown(
                        f"[VehiclesDB — sursa datelor]({VEHICLES_SOURCE})"
                    )

    st.markdown("---")

    st.caption(
        "Baza actuală oferă informații despre mărci și modele. "
        "Codurile de motor, generațiile detaliate și ECU vor fi "
        "integrate într-o etapă viitoare."
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

    st.markdown("---")

    st.subheader("Vehicle Database")

    if VEHICLES_DB_PATH.exists():

        makes_count, models_count = get_vehicle_statistics()

        v1, v2 = st.columns(2)

        v1.metric("Mărci auto", f"{makes_count:,}")
        v2.metric("Modele auto", f"{models_count:,}")

        st.success("vehicles.db este disponibilă.")

        st.markdown(
            f"[Sursa datelor: VehiclesDB]({VEHICLES_SOURCE})"
        )

    else:

        st.error("vehicles.db nu există în folderul data.")

    st.markdown("---")

    st.caption(
        "Baza DTC, baza de diagnostic și baza de vehicule "
        "sunt fișiere separate. Datele originale nu sunt modificate."
    )
