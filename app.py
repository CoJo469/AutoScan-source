import streamlit as st
import pandas as pd
import sqlite3
import re
from pathlib import Path


# =========================================================
# CONFIGURARE
# =========================================================

st.set_page_config(
    page_title="Auto Diagnosis PRO",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# CONSTANTE
# =========================================================

APP_TITLE = "Auto Diagnosis PRO"

DTC_DB_PATH = Path(__file__).parent / "data" / "dtc_codes.db"


# =========================================================
# VEHICULE DEMO
# =========================================================
# Aceasta este doar baza inițială de vehicule.
# În etapa următoare o vom înlocui cu o bază mult mai mare.
# =========================================================

VEHICLES = {
    "Volkswagen": {
        "Golf": {
            "2018": [
                "1.6 TDI",
                "2.0 TDI",
                "1.4 TSI"
            ],
            "2019": [
                "1.6 TDI",
                "2.0 TDI",
                "1.5 TSI"
            ],
            "2020": [
                "2.0 TDI",
                "1.5 TSI"
            ],
        },

        "Passat": {
            "2018": [
                "1.6 TDI",
                "2.0 TDI"
            ],
            "2019": [
                "2.0 TDI"
            ],
            "2020": [
                "2.0 TDI",
                "1.5 TSI"
            ],
        },
    },

    "BMW": {
        "Seria 3": {
            "2018": [
                "320d",
                "330i"
            ],
            "2019": [
                "320d",
                "330i"
            ],
            "2020": [
                "320d",
                "330i"
            ],
        },

        "Seria 5": {
            "2018": [
                "520d",
                "530d"
            ],
            "2019": [
                "520d",
                "530d"
            ],
            "2020": [
                "520d",
                "530e"
            ],
        },
    },

    "Audi": {
        "A4": {
            "2018": [
                "2.0 TDI",
                "2.0 TFSI"
            ],
            "2019": [
                "2.0 TDI",
                "2.0 TFSI"
            ],
            "2020": [
                "2.0 TDI",
                "2.0 TFSI"
            ],
        },

        "A6": {
            "2018": [
                "2.0 TDI",
                "3.0 TDI"
            ],
            "2019": [
                "2.0 TDI",
                "3.0 TDI"
            ],
            "2020": [
                "2.0 TDI",
                "3.0 TDI"
            ],
        },
    },

    "Ford": {
        "Focus": {
            "2018": [
                "1.5 TDCi",
                "1.0 EcoBoost"
            ],
            "2019": [
                "1.5 EcoBlue",
                "1.0 EcoBoost"
            ],
            "2020": [
                "1.5 EcoBlue",
                "1.0 EcoBoost"
            ],
        },

        "Mondeo": {
            "2018": [
                "2.0 TDCi",
                "2.0 EcoBoost"
            ],
            "2019": [
                "2.0 EcoBlue"
            ],
            "2020": [
                "2.0 EcoBlue"
            ],
        },
    },
}


# =========================================================
# FUNCȚII DTC
# =========================================================

def normalize_dtc(code):
    """
    Normalizează codul DTC.
    Exemplu:
    ' p0299 ' -> 'P0299'
    """

    if not code:
        return ""

    code = str(code).strip().upper()

    code = re.sub(
        r"\s+",
        "",
        code
    )

    return code


def validate_dtc(code):
    """
    Verifică formatul general:
    Pxxxx
    Bxxxx
    Cxxxx
    Uxxxx
    """

    code = normalize_dtc(code)

    pattern = r"^[PBCU][0-9A-F]{4}$"

    return bool(
        re.fullmatch(
            pattern,
            code
        )
    )


def get_connection():
    """
    Deschide conexiunea către baza SQLite.
    """

    if not DTC_DB_PATH.exists():
        return None

    return sqlite3.connect(
        str(DTC_DB_PATH)
    )


def get_database_statistics():
    """
    Returnează statistici din baza DTC.
    """

    conn = get_connection()

    if conn is None:
        return None

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM dtc_definitions
            """
        )

        total_definitions = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT code)
            FROM dtc_definitions
            """
        )

        unique_codes = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT manufacturer)
            FROM dtc_definitions
            WHERE manufacturer != 'GENERIC'
            """
        )

        manufacturers = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT code)
            FROM dtc_definitions
            WHERE is_generic = 1
            """
        )

        generic_codes = cursor.fetchone()[0]

        return {
            "total_definitions": total_definitions,
            "unique_codes": unique_codes,
            "manufacturers": manufacturers,
            "generic_codes": generic_codes
        }

    except Exception:
        return None

    finally:

        conn.close()


def get_manufacturers():
    """
    Returnează producătorii existenți în baza DTC.
    """

    conn = get_connection()

    if conn is None:
        return []

    try:

        query = """
            SELECT DISTINCT manufacturer
            FROM dtc_definitions
            WHERE manufacturer != 'GENERIC'
            ORDER BY manufacturer
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        return df["manufacturer"].tolist()

    except Exception:
        return []

    finally:

        conn.close()


def search_dtc(
    code,
    manufacturer=None
):
    """
    Caută un cod DTC.

    Dacă este selectat producătorul:
    1. caută definiția producătorului
    2. dacă nu există, folosește definiția generică
    """

    conn = get_connection()

    if conn is None:
        return None

    code = normalize_dtc(code)

    try:

        cursor = conn.cursor()

        if manufacturer and manufacturer != "GENERIC":

            query = """
                SELECT
                    code,
                    manufacturer,
                    description,
                    type,
                    locale,
                    is_generic,
                    source_file

                FROM dtc_definitions

                WHERE code = ?

                AND locale = 'en'

                AND (
                    manufacturer = ?
                    OR manufacturer = 'GENERIC'
                )

                ORDER BY
                    CASE
                        WHEN manufacturer = ? THEN 0
                        WHEN manufacturer = 'GENERIC' THEN 1
                        ELSE 2
                    END

                LIMIT 1
            """

            cursor.execute(
                query,
                (
                    code,
                    manufacturer,
                    manufacturer
                )
            )

        else:

            query = """
                SELECT
                    code,
                    manufacturer,
                    description,
                    type,
                    locale,
                    is_generic,
                    source_file

                FROM dtc_definitions

                WHERE code = ?

                AND locale = 'en'

                ORDER BY
                    CASE
                        WHEN manufacturer = 'GENERIC' THEN 0
                        ELSE 1
                    END

                LIMIT 1
            """

            cursor.execute(
                query,
                (code,)
            )

        result = cursor.fetchone()

        return result

    except Exception:
        return None

    finally:

        conn.close()


def search_dtc_text(
    keyword,
    limit=50
):
    """
    Caută după cod sau cuvinte din descriere.
    """

    conn = get_connection()

    if conn is None:
        return pd.DataFrame()

    keyword = str(keyword).strip()

    try:

        query = """
            SELECT
                code,
                manufacturer,
                description,
                type,
                is_generic

            FROM dtc_definitions

            WHERE locale = 'en'

            AND (
                code LIKE ?
                OR description LIKE ?
            )

            ORDER BY
                CASE
                    WHEN manufacturer = 'GENERIC'
                    THEN 0
                    ELSE 1
                END,
                code

            LIMIT ?
        """

        search_value = f"%{keyword}%"

        df = pd.read_sql_query(
            query,
            conn,
            params=(
                search_value,
                search_value,
                limit
            )
        )

        return df

    except Exception:

        return pd.DataFrame()

    finally:

        conn.close()


# =========================================================
# FUNCȚII VEHICULE
# =========================================================

def get_models(brand):

    if brand not in VEHICLES:
        return []

    return list(
        VEHICLES[brand].keys()
    )


def get_years(
    brand,
    model
):

    if brand not in VEHICLES:
        return []

    if model not in VEHICLES[brand]:
        return []

    return list(
        VEHICLES[brand][model].keys()
    )


def get_engines(
    brand,
    model,
    year
):

    if brand not in VEHICLES:
        return []

    if model not in VEHICLES[brand]:
        return []

    if year not in VEHICLES[brand][model]:
        return []

    return VEHICLES[
        brand
    ][
        model
    ][
        year
    ]


# =========================================================
# FUNCȚII UI
# =========================================================

def show_list(items):

    for item in items:

        st.markdown(
            f"- {item}"
        )


def show_database_error():

    st.error(
        "Baza DTC nu a fost găsită."
    )

    st.code(
        "data/dtc_codes.db"
    )

    st.info(
        """
        Verifică dacă fișierul dtc_codes.db
        există în folderul data din GitHub.
        """
    )


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "🔧 Auto Diagnosis PRO"
)

st.sidebar.caption(
    "Platformă de diagnoză auto"
)

st.sidebar.divider()

menu = st.sidebar.radio(
    "Meniu",
    [
        "🏠 Dashboard",
        "🔎 DTC Diagnosis",
        "🔍 DTC Search",
        "🚗 Vehicle Search",
        "🧰 Repair Cases",
        "📊 Database",
    ]
)

st.sidebar.divider()

if DTC_DB_PATH.exists():

    st.sidebar.success(
        "DTC Database: OK"
    )

else:

    st.sidebar.error(
        "DTC Database: lipsă"
    )


# =========================================================
# DASHBOARD
# =========================================================

if menu == "🏠 Dashboard":

    st.title(
        "🔧 Auto Diagnosis PRO"
    )

    st.markdown(
        """
        ### Platformă pentru diagnoză auto

        Caută coduri DTC și pregătește diagnosticul
        pe baza vehiculului și a datelor reale de service.
        """
    )

    st.divider()

    stats = get_database_statistics()

    if stats:

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Coduri DTC",
                f"{stats['unique_codes']:,}"
            )

        with col2:

            st.metric(
                "Definiții",
                f"{stats['total_definitions']:,}"
            )

        with col3:

            st.metric(
                "Producători",
                stats["manufacturers"]
            )

        with col4:

            st.metric(
                "Coduri generice",
                f"{stats['generic_codes']:,}"
            )

    else:

        show_database_error()

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "🔎 Diagnostic DTC"
        )

        st.markdown(
            """
            Introdu un cod precum:

            `P0299`

            `P0101`

            `P0420`

            `U0100`

            și primești definiția din baza DTC.
            """

        )

    with col2:

        st.subheader(
            "🚗 Vehicul"
        )

        st.markdown(
            """
            Selectează:

            - marca
            - modelul
            - anul
            - motorul

            În etapele următoare vom lega aceste
            informații de DTC-urile specifice vehiculului.
            """
        )

    st.divider()

    st.success(
        "Aplicația este conectată la baza DTC locală."
    )


# =========================================================
# DTC DIAGNOSIS
# =========================================================

elif menu == "🔎 DTC Diagnosis":

    st.title(
        "🔎 Diagnosticare DTC"
    )

    st.write(
        "Introdu codul citit cu testerul."
    )

    manufacturers = [
        "GENERIC"
    ] + get_manufacturers()

    col1, col2 = st.columns(
        [2, 1]
    )

    with col1:

        dtc_input = st.text_input(
            "Cod DTC",
            placeholder="Exemplu: P0299",
            key="diagnosis_code"
        )

    with col2:

        manufacturer = st.selectbox(
            "Producător",
            manufacturers,
            key="diagnosis_manufacturer"
        )

    search_button = st.button(
        "🔍 Diagnosticare",
        type="primary",
        use_container_width=True
    )

    if search_button:

        code = normalize_dtc(
            dtc_input
        )

        if not code:

            st.warning(
                "Introdu un cod DTC."
            )

        elif not validate_dtc(code):

            st.error(
                f"Codul `{code}` nu are un format DTC valid."
            )

        else:

            result = search_dtc(
                code,
                manufacturer
            )

            if result is None:

                st.warning(
                    f"Codul {code} nu a fost găsit în baza DTC."
                )

                st.info(
                    """
                    Codul poate fi:
                    - specific unui producător
                    - rar
                    - sau absent din baza actuală.
                    """
                )

            else:

                (
                    result_code,
                    result_manufacturer,
                    description,
                    dtc_type,
                    locale,
                    is_generic,
                    source_file
                ) = result

                st.success(
                    f"Cod găsit: {result_code}"
                )

                st.header(
                    result_code
                )

                st.subheader(
                    description
                )

                col1, col2, col3 = st.columns(3)

                with col1:

                    if result_manufacturer == "GENERIC":

                        st.metric(
                            "Definiție",
                            "Generic"
                        )

                    else:

                        st.metric(
                            "Producător",
                            result_manufacturer
                        )

                with col2:

                    st.metric(
                        "Sistem",
                        {
                            "P": "Powertrain",
                            "B": "Body",
                            "C": "Chassis",
                            "U": "Network"
                        }.get(
                            dtc_type,
                            dtc_type
                        )
                    )

                with col3:

                    if is_generic:

                        st.metric(
                            "Tip",
                            "Generic"
                        )

                    else:

                        st.metric(
                            "Tip",
                            "Manufacturer"
                        )

                st.divider()

                st.subheader(
                    "📋 Descriere"
                )

                st.write(
                    description
                )

                st.divider()

                st.subheader(
                    "🧠 Diagnostic"
                )

                st.info(
                    """
                    În această etapă avem definiția DTC.

                    Următorul modul pe care îl construim va adăuga
                    simptome, cauze, teste, valori de verificat și
                    proceduri de reparație.
                    """
                )

                st.subheader(
                    "📚 Sursă"
                )

                st.caption(
                    f"Producător: {result_manufacturer}"
                )

                st.caption(
                    f"Tip DTC: {dtc_type}"
                )

                st.caption(
                    f"Sursă internă: {source_file}"
                )


# =========================================================
# DTC SEARCH
# =========================================================

elif menu == "🔍 DTC Search":

    st.title(
        "🔍 Căutare în baza DTC"
    )

    st.write(
        """
        Poți căuta după cod sau după cuvinte din descriere.
        """
    )

    keyword = st.text_input(
        "Caută",
        placeholder="Exemplu: turbo, pressure, P0299"
    )

    limit = st.slider(
        "Număr maxim rezultate",
        min_value=10,
        max_value=100,
        value=25
    )

    search_button = st.button(
        "🔍 Caută în baza DTC",
        type="primary"
    )

    if search_button:

        if not keyword.strip():

            st.warning(
                "Introdu un termen de căutare."
            )

        else:

            results = search_dtc_text(
                keyword,
                limit
            )

            if results.empty:

                st.warning(
                    "Nu au fost găsite rezultate."
                )

            else:

                st.success(
                    f"Au fost găsite {len(results)} rezultate."
                )

                results_display = results.copy()

                results_display[
                    "Tip"
                ] = results_display[
                    "type"
                ].map(
                    {
                        "P": "Powertrain",
                        "B": "Body",
                        "C": "Chassis",
                        "U": "Network"
                    }
                )

                results_display[
                    "Definiție"
                ] = results_display[
                    "is_generic"
                ].map(
                    {
                        1: "Generic",
                        0: "Producător"
                    }
                )

                results_display = results_display[
                    [
                        "code",
                        "manufacturer",
                        "description",
                        "Tip",
                        "Definiție"
                    ]
                ]

                results_display.columns = [
                    "Cod",
                    "Producător",
                    "Descriere",
                    "Tip",
                    "Definiție"
                ]

                st.dataframe(
                    results_display,
                    use_container_width=True,
                    hide_index=True
                )


# =========================================================
# VEHICLE SEARCH
# =========================================================

elif menu == "🚗 Vehicle Search":

    st.title(
        "🚗 Identificare vehicul"
    )

    st.write(
        "Selectează vehiculul."
    )

    brands = list(
        VEHICLES.keys()
    )

    brand = st.selectbox(
        "1️⃣ Marcă",
        ["Selectează marca"] + brands
    )

    if brand != "Selectează marca":

        models = get_models(
            brand
        )

        model = st.selectbox(
            "2️⃣ Model",
            ["Selectează modelul"] + models
        )

        if model != "Selectează modelul":

            years = get_years(
                brand,
                model
            )

            year = st.selectbox(
                "3️⃣ An",
                ["Selectează anul"] + years
            )

            if year != "Selectează anul":

                engines = get_engines(
                    brand,
                    model,
                    year
                )

                engine = st.selectbox(
                    "4️⃣ Motor",
                    ["Selectează motorul"] + engines
                )

                if engine != "Selectează motorul":

                    st.divider()

                    st.success(
                        "Vehicul selectat"
                    )

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:

                        st.metric(
                            "Marcă",
                            brand
                        )

                    with col2:

                        st.metric(
                            "Model",
                            model
                        )

                    with col3:

                        st.metric(
                            "An",
                            year
                        )

                    with col4:

                        st.metric(
                            "Motor",
                            engine
                        )

                    st.divider()

                    st.subheader(
                        "🔎 Diagnostic pentru vehicul"
                    )

                    st.info(
                        """
                        Asocierea exactă dintre vehicul,
                        motor, ECU și DTC va fi adăugată
                        în următoarea etapă.
                        """)


# =========================================================
# REPAIR CASES
# =========================================================

elif menu == "🧰 Repair Cases":

    st.title(
        "🧰 Cazuri reale de service"
    )

    st.markdown(
        """
        Aici vom construi baza de experiență reală din service-uri.
        """
    )

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "📋 Date caz"
        )

        st.markdown(
            """
            - Vehicul
            - Motor
            - Cod motor
            - Kilometraj
            - Coduri DTC
            - Simptome
            - Valori live
            - Teste efectuate
            """
        )

    with col2:

        st.subheader(
            "🛠️ Rezultat"
        )

        st.markdown(
            """
            - Cauză confirmată
            - Reparație
            - Piese schimbate
            - Fotografii
            - Documente
            - Rezultat după reparație
            """
        )

    st.divider()

    st.warning(
        "Modulul de cazuri reale va fi conectat la Supabase într-o etapă următoare."
    )


# =========================================================
# DATABASE
# =========================================================

elif menu == "📊 Database":

    st.title(
        "📊 Baza de date DTC"
    )

    stats = get_database_statistics()

    if stats:

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Coduri unice",
                f"{stats['unique_codes']:,}"
            )

        with col2:

            st.metric(
                "Definiții",
                f"{stats['total_definitions']:,}"
            )

        with col3:

            st.metric(
                "Producători",
                stats["manufacturers"]
            )

        with col4:

            st.metric(
                "Generice",
                f"{stats['generic_codes']:,}"
            )

        st.divider()

        st.subheader(
            "🏭 Producători disponibili"
        )

        manufacturers = get_manufacturers()

        if manufacturers:

            st.dataframe(
                pd.DataFrame(
                    {
                        "Producător": manufacturers
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        st.subheader(
            "🔎 Test rapid DTC"
        )

        test_code = st.text_input(
            "Introdu un cod pentru test",
            placeholder="P0420"
        )

        if test_code:

            test_result = search_dtc(
                test_code
            )

            if test_result:

                (
                    code,
                    manufacturer,
                    description,
                    dtc_type,
                    locale,
                    is_generic,
                    source_file
                ) = test_result

                st.success(
                    f"{code} — {description}"
                )

            else:

                st.warning(
                    "Codul nu a fost găsit."
                )

    else:

        show_database_error()


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Auto Diagnosis PRO • DTC Diagnosis Platform"
)
