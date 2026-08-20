import streamlit as st
from streamlit_autorefresh import st_autorefresh
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
# AUTOMATIC REFRESH
# ============================================================

REFRESH_INTERVAL_MINUTES = 5

st_autorefresh(
    interval=REFRESH_INTERVAL_MINUTES * 60 * 1000,
    key="dws_dashboard_refresh"
)

# ============================================================
# MONITORED STATIONS
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

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
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
# LOAD LIVE DATA
# ============================================================

@st.cache_data(ttl=60)
def load_station_data():

    response = (
        supabase
        .table("station_observations")
        .select(
            "station_code,"
            "observation_time,"
            "flow_m3s,"
            "stage_m,"
            "latitude,"
            "longitude,"
            "station_name"
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

    if not response.data:

        return {}


    all_data = pd.DataFrame(
        response.data
    )


    if all_data.empty:

        return {}


    # --------------------------------------------------------
    # CLEAN FIELDS
    # --------------------------------------------------------

    all_data["station_code"] = (
        all_data["station_code"]
        .astype(str)
        .str.strip()
        .str.upper()
    )


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


    all_data["latitude"] = pd.to_numeric(
        all_data["latitude"],
        errors="coerce"
    )


    all_data["longitude"] = pd.to_numeric(
        all_data["longitude"],
        errors="coerce"
    )


    all_data = all_data.dropna(
        subset=["observation_time"]
    )


    station_data = {}


    # --------------------------------------------------------
    # SPLIT INTO STATIONS
    # --------------------------------------------------------

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


        station_data[code] = df.reset_index(
            drop=True
        )


    return station_data


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

    for code in station_data:

        df = station_data[code]

        if not df.empty:

            latest = df.iloc[-1]

            if (
                pd.notna(latest["latitude"])
                and
                pd.notna(latest["longitude"])
            ):

                mapped_count += 1


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


    df = station_data[code]


    if df.empty:

        continue


    latest = df.iloc[-1]


    # --------------------------------------------------------
    # REQUIRE COORDINATES
    # --------------------------------------------------------

    latitude = latest["latitude"]

    longitude = latest["longitude"]


    if pd.isna(latitude) or pd.isna(longitude):

        continue


    station_name = latest.get(
        "station_name",
        code
    )


    if pd.isna(station_name):

        station_name = code


    map_records.append({

        "Station":
            code,

        "Station Name":
            station_name,

        "Latitude":
            float(latitude),

        "Longitude":
            float(longitude),

        "Flow (m³/s)":
            latest["flow_m3s"],

        "Stage (m)":
            latest["stage_m"],

        "Date/time":
            latest["datetime"]

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
        "No station coordinates are available "
        "for the live station data."
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
    sorted(station_data.keys())
)


df = station_data[
    selected_station
].copy()


# ============================================================
# STATION NAME
# ============================================================

latest = df.iloc[-1]


station_name = latest.get(
    "station_name",
    selected_station
)


if pd.isna(station_name):

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

col1, col2, col3 = st.columns(3)


with col1:

    flow = latest["flow_m3s"]

    if pd.notna(flow):

        st.metric(
            "Latest Flow",
            f"{flow:.3f} m³/s"
        )

    else:

        st.metric(
            "Latest Flow",
            "N/A"
        )


with col2:

    stage = latest["stage_m"]

    if pd.notna(stage):

        st.metric(
            "Latest Stage",
            f"{stage:.3f} m"
        )

    else:

        st.metric(
            "Latest Stage",
            "N/A"
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
    display_df["datetime"]
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
    "Source: DWS Unaudited Real-Time Hydrological Data. "
    "Data are subject to verification."
)