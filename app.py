import streamlit as st
import pandas as pd
import re


# =========================================================
# CONFIGURARE PAGINĂ
# =========================================================

st.set_page_config(
    page_title="Auto Diagnosis PRO",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# DATE DEMO
# =========================================================
# Aceste date sunt temporare.
# În etapa următoare le vom înlocui cu baza DTC reală.
# =========================================================

VEHICLES = {
    "Volkswagen": {
        "Golf": {
            "2018": ["1.6 TDI", "2.0 TDI", "1.4 TSI"],
            "2019": ["1.6 TDI", "2.0 TDI", "1.5 TSI"],
            "2020": ["2.0 TDI", "1.5 TSI"],
        },
        "Passat": {
            "2018": ["1.6 TDI", "2.0 TDI"],
            "2019": ["2.0 TDI"],
            "2020": ["2.0 TDI", "1.5 TSI"],
        },
    },

    "BMW": {
        "Seria 3": {
            "2018": ["320d", "330i"],
            "2019": ["320d", "330i"],
            "2020": ["320d", "330i"],
        },
        "Seria 5": {
            "2018": ["520d", "530d"],
            "2019": ["520d", "530d"],
            "2020": ["520d", "530e"],
        },
    },

    "Audi": {
        "A4": {
            "2018": ["2.0 TDI", "2.0 TFSI"],
            "2019": ["2.0 TDI", "2.0 TFSI"],
            "2020": ["2.0 TDI", "2.0 TFSI"],
        },
        "A6": {
            "2018": ["2.0 TDI", "3.0 TDI"],
            "2019": ["2.0 TDI", "3.0 TDI"],
            "2020": ["2.0 TDI", "3.0 TDI"],
        },
    },

    "Ford": {
        "Focus": {
            "2018": ["1.5 TDCi", "1.0 EcoBoost"],
            "2019": ["1.5 EcoBlue", "1.0 EcoBoost"],
            "2020": ["1.5 EcoBlue", "1.0 EcoBoost"],
        },
        "Mondeo": {
            "2018": ["2.0 TDCi", "2.0 EcoBoost"],
            "2019": ["2.0 EcoBlue"],
            "2020": ["2.0 EcoBlue"],
        },
    },
}


# =========================================================
# BAZĂ DTC DEMO
# =========================================================
# Vom adăuga ulterior mii de coduri din bazele open-source.
# =========================================================

DTC_DATABASE = {

    "P0299": {
        "title": "Turbocharger/Supercharger Underboost",
        "description": (
            "Presiunea de supraalimentare măsurată este mai mică "
            "decât presiunea solicitată de ECU."
        ),
        "system": "Motor / Supraalimentare",
        "severity": "Ridicată",

        "symptoms": [
            "Pierdere de putere",
            "Motorul intră în limp mode",
            "Accelerație slabă",
            "Consum crescut de combustibil",
            "Martor Check Engine"
        ],

        "causes": [
            "Furtun intercooler fisurat",
            "Pierderi pe circuitul de vacuum",
            "Actuator turbo defect",
            "Geometrie variabilă blocată",
            "Electrovalvă de control turbo defectă",
            "Senzor MAP cu valori incorecte",
            "Probleme ale turbinei"
        ],

        "checks": [
            "Verificarea furtunurilor de admisie",
            "Verificarea intercoolerului",
            "Verificarea vacuumului",
            "Compararea presiunii MAP cerute cu cea reală",
            "Testarea actuatorului turbinei",
            "Verificarea electrovalvei de comandă",
            "Verificarea geometriei variabile"
        ],

        "repair": [
            "Repararea sau înlocuirea furtunului deteriorat",
            "Remedierea pierderilor de vacuum",
            "Curățarea sau repararea mecanismului VGT",
            "Înlocuirea electrovalvei dacă este defectă",
            "Înlocuirea actuatorului dacă testarea confirmă defectul",
            "Înlocuirea turbinei numai după confirmarea defectului"
        ],

        "difficulty": "Medie - Ridicată",
        "estimated_time": "1 - 6 ore",
    },


    "P0101": {
        "title": "Mass Air Flow Sensor Range/Performance",
        "description": (
            "Semnalul senzorului MAF nu corespunde valorilor "
            "așteptate de ECU pentru condițiile de funcționare."
        ),
        "system": "Admisie / Management motor",
        "severity": "Medie",

        "symptoms": [
            "Ralanti instabil",
            "Pierdere de putere",
            "Consum crescut",
            "Pornire dificilă",
            "Check Engine"
        ],

        "causes": [
            "Senzor MAF murdar",
            "Senzor MAF defect",
            "Filtru de aer foarte murdar",
            "Pierdere de aer după MAF",
            "Probleme la cablaj",
            "Probleme de alimentare electrică"
        ],

        "checks": [
            "Verificarea filtrului de aer",
            "Inspectarea traseului de admisie",
            "Verificarea conectorului MAF",
            "Citirea valorilor MAF live",
            "Compararea valorilor reale cu valorile calculate"
        ],

        "repair": [
            "Curățarea senzorului cu produs adecvat",
            "Repararea traseului de admisie",
            "Remedierea cablajului",
            "Înlocuirea senzorului MAF dacă este confirmat defect"
        ],

        "difficulty": "Scăzută - Medie",
        "estimated_time": "30 minute - 2 ore",
    },


    "P0300": {
        "title": "Random/Multiple Cylinder Misfire Detected",
        "description": (
            "ECU a detectat rateuri de aprindere pe unul sau mai mulți cilindri."
        ),
        "system": "Motor / Aprindere",
        "severity": "Ridicată",

        "symptoms": [
            "Motorul funcționează neregulat",
            "Trepidații",
            "Pierdere de putere",
            "Check Engine intermitent sau permanent",
            "Consum crescut",
            "Miros de combustibil nears"
        ],

        "causes": [
            "Bujii uzate",
            "Bobine de inducție defecte",
            "Injector defect",
            "Presiune combustibil incorectă",
            "Compresie scăzută",
            "Probleme de admisie",
            "Probleme de sincronizare"
        ],

        "checks": [
            "Citirea contoarelor de misfire",
            "Verificarea bujiilor",
            "Schimbarea bobinelor între cilindri pentru test",
            "Verificarea injectoarelor",
            "Măsurarea presiunii combustibilului",
            "Test de compresie",
            "Verificarea sincronizării motorului"
        ],

        "repair": [
            "Înlocuirea bujiilor",
            "Înlocuirea bobinei defecte",
            "Repararea sau înlocuirea injectorului",
            "Remedierea problemei de alimentare",
            "Remedierea problemei mecanice"
        ],

        "difficulty": "Medie - Ridicată",
        "estimated_time": "1 - 8 ore",
    },


    "P0401": {
        "title": "Exhaust Gas Recirculation Insufficient Flow",
        "description": (
            "ECU detectează un debit insuficient al sistemului EGR."
        ),
        "system": "EGR / Emisii",
        "severity": "Medie",

        "symptoms": [
            "Check Engine",
            "Putere redusă",
            "Ralanti instabil",
            "Consum crescut",
            "Emisii crescute"
        ],

        "causes": [
            "EGR înfundat",
            "Canale EGR blocate",
            "Supapă EGR defectă",
            "Probleme de vacuum",
            "Senzor poziție EGR defect",
            "Probleme de cablaj"
        ],

        "checks": [
            "Citirea valorilor EGR",
            "Verificarea poziției supapei",
            "Inspectarea conductelor EGR",
            "Verificarea vacuumului",
            "Verificarea conectorilor",
            "Verificarea depunerilor de carbon"
        ],

        "repair": [
            "Curățarea sistemului EGR",
            "Curățarea canalelor",
            "Repararea vacuumului",
            "Înlocuirea EGR dacă este defectă"
        ],

        "difficulty": "Medie",
        "estimated_time": "1 - 5 ore",
    },


    "P0420": {
        "title": "Catalyst System Efficiency Below Threshold",
        "description": (
            "Eficiența catalizatorului este estimată de ECU ca fiind "
            "sub pragul acceptat."
        ),
        "system": "Emisii / Catalizator",
        "severity": "Medie",

        "symptoms": [
            "Check Engine",
            "Uneori consum crescut",
            "Miros neobișnuit al gazelor de evacuare",
            "Performanță redusă în unele situații"
        ],

        "causes": [
            "Catalizator degradat",
            "Sondă lambda defectă",
            "Pierdere pe evacuare",
            "Amestec prea bogat",
            "Rateuri de aprindere",
            "Probleme de temperatură"
        ],

        "checks": [
            "Verificarea parametrilor sondelor lambda",
            "Verificarea temperaturii catalizatorului",
            "Verificarea pierderilor pe evacuare",
            "Verificarea misfire-urilor",
            "Analiza fuel trims"
        ],

        "repair": [
            "Remedierea pierderii pe evacuare",
            "Remedierea problemei de amestec",
            "Înlocuirea sondei dacă este confirmată defectă",
            "Înlocuirea catalizatorului după confirmarea diagnosticului"
        ],

        "difficulty": "Medie - Ridicată",
        "estimated_time": "1 - 6 ore",
    }
}


# =========================================================
# FUNCȚII
# =========================================================

def normalize_dtc(code):
    """Normalizează codul DTC."""

    if not code:
        return ""

    code = str(code).strip().upper()
    code = re.sub(r"\s+", "", code)

    return code


def validate_dtc(code):
    """Verifică formatul general al unui cod DTC."""

    code = normalize_dtc(code)

    pattern = r"^[PBCU][0-9A-F]{4}$"

    return bool(re.fullmatch(pattern, code))


def get_dtc(code):
    """Caută codul în baza DTC."""

    code = normalize_dtc(code)

    return DTC_DATABASE.get(code)


def get_years(brand, model):
    """Returnează anii disponibili."""

    if brand not in VEHICLES:
        return []

    if model not in VEHICLES[brand]:
        return []

    return list(VEHICLES[brand][model].keys())


def get_engines(brand, model, year):
    """Returnează motoarele disponibile."""

    if (
        brand not in VEHICLES
        or model not in VEHICLES[brand]
        or year not in VEHICLES[brand][model]
    ):
        return []

    return VEHICLES[brand][model][year]


def show_list(items):
    """Afișează o listă cu bullet points."""

    for item in items:
        st.markdown(f"- {item}")


# =========================================================
# HEADER
# =========================================================

st.title("🔧 Auto Diagnosis PRO")

st.markdown(
    """
    ### Platformă pentru diagnoză auto

    Caută coduri DTC, identifică simptomele, cauzele posibile,
    verificările recomandate și soluțiile de reparație.
    """
)

st.divider()


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("🔧 Auto Diagnosis PRO")

st.sidebar.markdown(
    """
    **Versiune:** 1.0

    Modul actual:
    - DTC Diagnosis
    - Vehicle Selection
    - Diagnostic Procedure
    """
)

st.sidebar.divider()

menu = st.sidebar.radio(
    "Meniu",
    [
        "🏠 Dashboard",
        "🔎 DTC Diagnosis",
        "🚗 Vehicle Search",
        "🧰 Repair Cases",
        "📊 Database",
    ]
)


# =========================================================
# DASHBOARD
# =========================================================

if menu == "🏠 Dashboard":

    st.header("🏠 Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Coduri DTC",
            len(DTC_DATABASE)
        )

    with col2:
        st.metric(
            "Mărci",
            len(VEHICLES)
        )

    with col3:
        st.metric(
            "Modele",
            sum(
                len(models)
                for models in VEHICLES.values()
            )
        )

    with col4:
        st.metric(
            "Cazuri service",
            0
        )

    st.divider()

    st.subheader("🚀 Ce putem face")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            """
            ### 🔎 Diagnostic DTC

            Introdu un cod de eroare și primești:

            - descriere
            - simptome
            - cauze
            - verificări
            - reparații
            """
        )

    with col2:

        st.markdown(
            """
            ### 🚗 Identificare vehicul

            Selectează:

            - marca
            - model
            - an
            - motor

            iar ulterior vom lega aceste date
            de codurile DTC specifice vehiculului.
            """
        )

    st.success(
        "Aplicația este funcțională. Următorul pas este conectarea bazei reale de DTC."
    )


# =========================================================
# DTC DIAGNOSIS
# =========================================================

elif menu == "🔎 DTC Diagnosis":

    st.header("🔎 Diagnosticare cod DTC")

    st.write(
        "Introdu codul de eroare citit cu testerul."
    )

    col1, col2 = st.columns([3, 1])

    with col1:

        dtc_input = st.text_input(
            "Cod DTC",
            placeholder="Exemplu: P0299",
            key="dtc_search"
        )

    with col2:

        st.write("")
        st.write("")

        search_button = st.button(
            "🔍 Caută",
            use_container_width=True
        )

    if search_button:

        code = normalize_dtc(dtc_input)

        if not code:

            st.warning(
                "Introdu un cod DTC."
            )

        elif not validate_dtc(code):

            st.error(
                f"Codul `{code}` nu are un format DTC valid."
            )

        else:

            data = get_dtc(code)

            if data is None:

                st.warning(
                    f"Codul **{code}** este valid, dar nu există încă în baza locală."
                )

                st.info(
                    """
                    Acest lucru se va rezolva când vom importa
                    baza DTC open-source.
                    """
                )

            else:

                st.success(
                    f"Cod DTC găsit: **{code}**"
                )

                st.header(
                    f"{code} — {data['title']}"
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "Sistem",
                        data["system"]
                    )

                with col2:
                    st.metric(
                        "Severitate",
                        data["severity"]
                    )

                with col3:
                    st.metric(
                        "Dificultate",
                        data["difficulty"]
                    )

                st.divider()

                st.subheader("📋 Descriere")

                st.write(
                    data["description"]
                )

                st.subheader("⚠️ Simptome")

                show_list(
                    data["symptoms"]
                )

                st.subheader("🔍 Cauze posibile")

                show_list(
                    data["causes"]
                )

                st.subheader("🧪 Verificări recomandate")

                for index, check in enumerate(
                    data["checks"],
                    start=1
                ):

                    st.markdown(
                        f"**{index}.** {check}"
                    )

                st.subheader("🛠️ Soluții / Reparații")

                show_list(
                    data["repair"]
                )

                st.divider()

                col1, col2 = st.columns(2)

                with col1:

                    st.info(
                        f"⏱️ Timp estimat: {data['estimated_time']}"
                    )

                with col2:

                    st.warning(
                        "⚠️ Nu înlocui componente costisitoare înainte de confirmarea diagnosticului."
                    )


# =========================================================
# VEHICLE SEARCH
# =========================================================

elif menu == "🚗 Vehicle Search":

    st.header("🚗 Identificare vehicul")

    st.write(
        "Selectează vehiculul pentru a vedea informațiile disponibile."
    )

    brands = list(VEHICLES.keys())

    brand = st.selectbox(
        "1️⃣ Marcă",
        ["Selectează marca"] + brands
    )

    if brand != "Selectează marca":

        models = list(VEHICLES[brand].keys())

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

                    st.info(
                        """
                        Următoarea etapă va fi legarea vehiculului
                        de codurile DTC specifice motorului și ECU-ului.
                        """
                    )


# =========================================================
# REPAIR CASES
# =========================================================

elif menu == "🧰 Repair Cases":

    st.header("🧰 Cazuri reale de reparație")

    st.write(
        """
        Aici vom construi baza de experiență reală din service-uri:
        """
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            """
            ### 📋 Fiecare caz poate conține:

            - vehicul
            - motor
            - cod motor
            - kilometraj
            - cod DTC
            - simptome
            - valori live
            - teste efectuate
            - cauza confirmată
            - reparația efectuată
            - piese schimbate
            - fotografii
            - documente PDF
            - rezultat final
            """
        )

    with col2:

        st.markdown(
            """
            ### 🧠 În viitor

            Cazurile reale vor putea fi folosite pentru:

            - identificarea cauzelor frecvente
            - comparație între cazuri
            - estimarea reparației
            - diagnostic asistat
            - statistici pe modele și motoare
            """
        )

    st.divider()

    st.warning(
        "Baza de cazuri reale va fi construită într-o etapă următoare."
    )


# =========================================================
# DATABASE
# =========================================================

elif menu == "📊 Database":

    st.header("📊 Baza de date")

    st.subheader("Coduri DTC disponibile")

    rows = []

    for code, data in DTC_DATABASE.items():

        rows.append(
            {
                "DTC": code,
                "Descriere": data["title"],
                "Sistem": data["system"],
                "Severitate": data["severity"],
                "Dificultate": data["difficulty"],
                "Timp estimat": data["estimated_time"],
            }
        )

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.subheader("Mărci disponibile")

    vehicle_rows = []

    for brand, models in VEHICLES.items():

        for model, years in models.items():

            for year, engines in years.items():

                for engine in engines:

                    vehicle_rows.append(
                        {
                            "Marcă": brand,
                            "Model": model,
                            "An": year,
                            "Motor": engine
                        }
                    )

    vehicle_df = pd.DataFrame(
        vehicle_rows
    )

    st.dataframe(
        vehicle_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Auto Diagnosis PRO • Platformă de diagnoză auto"
)
