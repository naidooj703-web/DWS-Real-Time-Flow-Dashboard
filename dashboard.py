import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client


# ============================================================
# DWS REAL-TIME FLOW DASHBOARD
# ============================================================

st.set_page_config(
    page_title="DWS Real-Time Flow Dashboard",
    page_icon="🌊",
    layout="wide"
)


# ============================================================
# SETTINGS
# ============================================================

DATA_FOLDER = Path(__file__).resolve().parent

CATALOGUE_FILE = DATA_FOLDER / "NWRM_WQUANT_CAT.csv"


# ============================================================
# MONITORED DWS STATIONS
# ============================================================

MONITORED_STATIONS = [
    "A1H001",
    "A1R001",
    "A2H006",
    "A2H012",
    "A2H013",
    "A2H014",
    "A2H019",
    "A2H021",
    "A2H023",
    "A2H044",
    "A2H045",
    "A2H048",
    "A2H049",
    "A2H050",
    "A2H055",
    "A2H059",
    "A2H060",
    "A2H083",
    "A2H094",
    "C1H006"
]


# ============================================================
# SUPABASE CONNECTION
# ============================================================

@st.cache_resource
def get_supabase():

    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]

    return create_client(
        supabase_url,
        supabase_key
    )


try:

    supabase = get_supabase()

except Exception as e:

    st.error(
        "Could not connect to the DWS online database."
    )

    st.code(str(e))

    st.stop()


# ============================================================
# TITLE
# ============================================================

st.title(
    "🌊 DWS Real-Time Flow Dashboard"
)

st.caption(
    "Department of Water and Sanitation — "
    "Unaudited Real-Time Hydrological Data"
)


# ============================================================
# LOAD STATION CATALOGUE
# ============================================================

@st.cache_data
def load_catalogue():

    if not CATALOGUE_FILE.exists():

        return pd.DataFrame(
            columns=[
                "station_code",
                "latitude",
                "longitude",
                "station_name"
            ]
        )


    try:

        raw = pd.read_csv(
            CATALOGUE_FILE,
            header=None,
            low_memory=False
        )

    except Exception as e:

        st.error(
            f"Could not read {CATALOGUE_FILE.name}: {e}"
        )

        return pd.DataFrame(
            columns=[
                "station_code",
                "latitude",
                "longitude",
                "station_name"
            ]
        )


    records = []


    # --------------------------------------------------------
    # DWS CATALOGUE STRUCTURE
    #
    # 5  = latitude
    # 6  = longitude
    # 9  = station code
    # 10 = station code
    # 13 = station name
    # --------------------------------------------------------

    for _, row in raw.iterrows():

        try:

            if len(row) < 14:
                continue


            code_1 = str(
                row.iloc[9]
            ).strip().upper()


            code_2 = str(
                row.iloc[10]
            ).strip().upper()


            station_code = None


            if code_1 in MONITORED_STATIONS:

                station_code = code_1


            elif code_2 in MONITORED_STATIONS:

                station_code = code_2


            if station_code is None:

                continue


            latitude = pd.to_numeric(
                row.iloc[5],
                errors="coerce"
            )


            longitude = pd.to_numeric(
                row.iloc[6],
                errors="coerce"
            )


            if pd.isna(latitude):
                continue


            if pd.isna(longitude):
                continue


            station_name = str(
                row.iloc[13]
            ).strip()


            records.append({

                "station_code":
                    station_code,

                "latitude":
                    float(latitude),

                "longitude":
                    float(longitude),

                "station_name":
                    station_name

            })


        except Exception:

            continue


    catalogue = pd.DataFrame(
        records
    )


    if not catalogue.empty:

        catalogue = catalogue.drop_duplicates(
            subset=["station_code"],
            keep="first"
        )


    return catalogue


# ============================================================
# LOAD CATALOGUE
# ============================================================

catalogue = load_catalogue()


# ============================================================
# LOAD LIVE DATA FROM SUPABASE
# ============================================================

@st.cache_data(ttl=60)
def load_station_data():

    data = {}


    try:

        response = (
            supabase
            .table("station_observations")
            .select(
                "station_code,"
                "observation_time,"
                "flow_m3s,"
                "stage_m"
            )
            .in_(
                "station_code",
                MONITORED_STATIONS
            )
            .order(
                "observation_time",
                desc=False
            )
            .execute()
        )


        rows = response.data


        if not rows:

            return data


        all_data = pd.DataFrame(
            rows
        )


        if all_data.empty:

            return data


        all_data["observation_time"] = pd.to_datetime(
            all_data["observation_time"],
            errors="coerce"
        )


        all_data["flow_m3s"] = pd.to_numeric(
            all_data["flow_m3s"],
            errors="coerce"
        )


        all_data["stage_m"] = pd.to_numeric(
            all_data["stage_m"],
            errors="coerce"
        )


        all_data = all_data.dropna(
            subset=["observation_time"]
        )


        for code in MONITORED_STATIONS:

            df = all_data[
                all_data["station_code"] == code
            ].copy()


            if df.empty:

                continue


            df = df.sort_values(
                "observation_time"
            )


            df = df.rename(
                columns={
                    "observation_time":
                        "datetime"
                }
            )


            data[code] = df[
                [
                    "datetime",
                    "stage_m",
                    "flow_m3s"
                ]
            ].reset_index(
                drop=True
            )


    except Exception as e:

        st.error(
            "Could not load station observations "
            "from Supabase."
        )

        st.code(str(e))


    return data


station_data = load_station_data()


# ============================================================
# SUMMARY
# ============================================================

st.divider()


col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "Stations",
        len(MONITORED_STATIONS)
    )


with col2:

    st.metric(
        "Stations with Data",
        len(station_data)
    )


with col3:

    mapped_count = 0


    if not catalogue.empty:

        mapped_count = len(
            set(
                catalogue["station_code"]
            )
            &
            set(
                station_data.keys()
            )
        )


    st.metric(
        "Stations Mapped",
        mapped_count
    )


with col4:

    st.metric(
        "History",
        "30 days"
    )


# ============================================================
# CREATE MAP DATA
# ============================================================

map_records = []


for code in MONITORED_STATIONS:

    if code not in station_data:

        continue


    coord = catalogue[
        catalogue["station_code"] == code
    ]


    if coord.empty:

        continue


    df = station_data[code]


    if df.empty:

        continue


    latest = df.iloc[-1]


    map_records.append({

        "Station":
            code,

        "Station Name":
            coord.iloc[0][
                "station_name"
            ],

        "Latitude":
            coord.iloc[0][
                "latitude"
            ],

        "Longitude":
            coord.iloc[0][
                "longitude"
            ],

        "Flow (m³/s)":
            latest[
                "flow_m3s"
            ],

        "Stage (m)":
            latest[
                "stage_m"
            ],

        "Date/time":
            latest[
                "datetime"
            ]

    })


map_df = pd.DataFrame(
    map_records
)


# ============================================================
# MAP
# ============================================================

st.divider()

st.subheader(
    "📍 Real-Time DWS Stations"
)


if not map_df.empty:

    fig_map = px.scatter_map(

        map_df,

        lat="Latitude",

        lon="Longitude",

        hover_name="Station",

        text="Station",

        hover_data={

            "Station Name":
                True,

            "Flow (m³/s)":
                ":.3f",

            "Stage (m)":
                ":.3f",

            "Date/time":
                True,

            "Latitude":
                ":.5f",

            "Longitude":
                ":.5f"

        },

        zoom=5,

        height=650
    )


    fig_map.update_layout(

        map_style="carto-positron",

        margin={
            "l": 0,
            "r": 0,
            "t": 0,
            "b": 0
        }

    )


    st.plotly_chart(
        fig_map,
        use_container_width=True
    )


else:

    st.warning(
        "No station coordinates were matched "
        "to the real-time station data."
    )


# ============================================================
# STATION SELECTOR
# ============================================================

st.divider()

st.subheader(
    "📊 Station Data"
)


if not station_data:

    st.error(
        "No DWS real-time station data found "
        "in the online database."
    )

    st.stop()


selected_station = st.selectbox(

    "Select station",

    sorted(
        station_data.keys()
    )
)


df = station_data[
    selected_station
].copy()


# ============================================================
# STATION NAME
# ============================================================

coord = catalogue[
    catalogue["station_code"] ==
    selected_station
]


if not coord.empty:

    station_name = coord.iloc[0][
        "station_name"
    ]

else:

    station_name = selected_station


st.markdown(
    f"### {selected_station}"
)


st.caption(
    station_name
)


# ============================================================
# LATEST OBSERVATION
# ============================================================

latest = df.iloc[-1]


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Latest Flow",
        f"{latest['flow_m3s']:.3f} m³/s"
    )


with col2:

    st.metric(
        "Latest Stage",
        f"{latest['stage_m']:.3f} m"
    )


with col3:

    st.metric(

        "Observation",

        latest[
            "datetime"
        ].strftime(
            "%Y-%m-%d %H:%M"
        )

    )


# ============================================================
# FLOW GRAPH
# ============================================================

st.divider()

st.subheader(
    "🌊 Flow — Last 30 Days"
)


fig_flow = px.line(

    df,

    x="datetime",

    y="flow_m3s",

    labels={

        "datetime":
            "Date / Time",

        "flow_m3s":
            "Flow (m³/s)"

    }
)


fig_flow.update_layout(

    height=450,

    hovermode="x unified"

)


st.plotly_chart(

    fig_flow,

    use_container_width=True

)


# ============================================================
# STAGE GRAPH
# ============================================================

st.divider()

st.subheader(
    "📏 Stage — Last 30 Days"
)


fig_stage = px.line(

    df,

    x="datetime",

    y="stage_m",

    labels={

        "datetime":
            "Date / Time",

        "stage_m":
            "Stage (m)"

    }
)


fig_stage.update_layout(

    height=450,

    hovermode="x unified"

)


st.plotly_chart(

    fig_stage,

    use_container_width=True

)


# ============================================================
# LATEST OBSERVATIONS
# ============================================================

st.divider()

st.subheader(
    "📋 Latest Observations"
)


display_df = df.sort_values(

    "datetime",

    ascending=False

).copy()


display_df["datetime"] = (

    display_df[
        "datetime"
    ]

    .dt.strftime(
        "%Y-%m-%d %H:%M"
    )

)


st.dataframe(

    display_df[
        [
            "datetime",
            "stage_m",
            "flow_m3s"
        ]
    ].rename(

        columns={

            "datetime":
                "Date / Time",

            "stage_m":
                "Stage (m)",

            "flow_m3s":
                "Flow (m³/s)"

        }

    ),

    use_container_width=True,

    height=400

)


# ============================================================
# FOOTER
# ============================================================

st.divider()


st.caption(

    "Source: DWS Unaudited Real-Time "
    "Hydrological Data. "
    "Data are subject to verification."

)