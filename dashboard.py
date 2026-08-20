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
# LOAD ALL DATA FOR ONE STATION USING PAGINATION
# ============================================================

def load_one_station(station_code):

    page_size = 1000

    start = 0

    all_records = []


    while True:

        try:

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

                .eq(
                    "station_code",
                    station_code
                )

                .order(
                    "observation_time",
                    desc=False
                )

                .range(
                    start,
                    start + page_size - 1
                )

                .execute()

            )

        except Exception as e:

            return None, str(e)


        records = response.data or []


        if not records:

            break


        all_records.extend(
            records
        )


        # ----------------------------------------------------
        # If fewer than page_size were returned, this is the
        # final page.
        # ----------------------------------------------------

        if len(records) < page_size:

            break


        start += page_size


    if not all_records:

        return None, "No records returned"


    df = pd.DataFrame(
        all_records
    )


    if df.empty:

        return None, "Empty response"


    # ========================================================
    # NORMALISE STATION CODE
    # ========================================================

    df["station_code"] = (

        df["station_code"]

        .astype("string")

        .str.strip()

        .str.upper()

    )


    # ========================================================
    # NORMALISE DATETIME
    # ========================================================

    df["observation_time"] = pd.to_datetime(

        df["observation_time"],

        errors="coerce",

        utc=True

    )


    # ========================================================
    # NORMALISE NUMERIC FIELDS
    # ========================================================

    for column in [

        "flow_m3s",
        "stage_m",
        "latitude",
        "longitude"

    ]:

        df[column] = pd.to_numeric(

            df[column],

            errors="coerce"

        )


    # ========================================================
    # REMOVE INVALID TIMESTAMPS
    # ========================================================

    df = df.dropna(

        subset=[
            "observation_time"
        ]

    )


    if df.empty:

        return None, "No valid timestamps"


    # ========================================================
    # RENAME DATETIME
    # ========================================================

    df = df.rename(

        columns={

            "observation_time":
                "datetime"

        }

    )


    # ========================================================
    # SORT CHRONOLOGICALLY
    # ========================================================

    df = df.sort_values(

        "datetime",

        ascending=True

    )


    # ========================================================
    # REMOVE DUPLICATE OBSERVATIONS
    #
    # Keep this only if the same timestamp occurs more than
    # once for a station.
    # ========================================================

    df = df.drop_duplicates(

        subset=[
            "station_code",
            "datetime"
        ],

        keep="last"

    )


    return (

        df.reset_index(
            drop=True
        ),

        None

    )


# ============================================================
# LOAD ALL STATIONS
# ============================================================

@st.cache_data(ttl=60)
def load_station_data():

    station_data = {}

    station_errors = {}


    for station_code in MONITORED_STATIONS:

        df, error = load_one_station(
            station_code
        )


        if error is not None:

            station_errors[
                station_code
            ] = error

            continue


        if df is not None and not df.empty:

            station_data[
                station_code
            ] = df


    return (
        station_data,
        station_errors
    )


station_data, station_errors = (
    load_station_data()
)


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


    for station_code in station_data:

        df = station_data[
            station_code
        ]


        coordinate_records = df.dropna(

            subset=[
                "latitude",
                "longitude"
            ]

        )


        if not coordinate_records.empty:

            mapped_count += 1


    st.metric(
        "Stations Mapped",
        mapped_count
    )


with col4:

    st.metric(
        "Refresh",
        "5 min"
    )


# ============================================================
# MISSING STATIONS
# ============================================================

missing_stations = [

    code

    for code in MONITORED_STATIONS

    if code not in station_data

]


if missing_stations:

    st.warning(

        "Stations with no usable data: "
        + ", ".join(missing_stations)

    )


# ============================================================
# MAP DATA
# ============================================================

map_records = []


for station_code in MONITORED_STATIONS:

    if station_code not in station_data:

        continue


    df = station_data[
        station_code
    ]


    if df.empty:

        continue


    # Latest observation

    latest = df.iloc[-1]


    # Latest available coordinates

    coordinate_records = df.dropna(

        subset=[
            "latitude",
            "longitude"
        ]

    )


    if coordinate_records.empty:

        continue


    coordinate_record = (
        coordinate_records.iloc[-1]
    )


    latitude = coordinate_record[
        "latitude"
    ]


    longitude = coordinate_record[
        "longitude"
    ]


    if pd.isna(latitude) or pd.isna(longitude):

        continue


    # Station name

    station_name = latest.get(

        "station_name",

        station_code

    )


    if pd.isna(station_name):

        station_name = station_code


    map_records.append({

        "Station":
            station_code,

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


    # Smaller station dots

    fig_map.update_traces(

        marker=dict(
            size=7
        ),

        textposition="top center",

        textfont=dict(
            size=11
        )

    )


    st.plotly_chart(

        fig_map,

        use_container_width=True

    )


else:

    st.warning(
        "No station coordinates are available."
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
        "No DWS real-time station data found."
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


# Make absolutely sure graph data are chronological

df = df.sort_values(
    "datetime",
    ascending=True
)


# ============================================================
# LATEST OBSERVATION
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
# LATEST METRICS
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

    observation_time = latest["datetime"]


    st.metric(

        "Observation",

        observation_time.strftime(
            "%Y-%m-%d %H:%M"
        )

    )


# ============================================================
# PERIOD SELECTOR
# ============================================================

st.divider()

st.subheader(
    "📅 Analysis Period"
)


period_options = {

    "24 Hours":
        pd.Timedelta(hours=24),

    "7 Days":
        pd.Timedelta(days=7),

    "30 Days":
        pd.Timedelta(days=30)

}


selected_period = st.selectbox(

    "Select period",

    list(
        period_options.keys()
    ),

    index=2

)


# ============================================================
# FILTER PERIOD
# ============================================================

latest_datetime = df[
    "datetime"
].max()


start_datetime = (

    latest_datetime

    - period_options[
        selected_period
    ]

)


period_df = df[

    df["datetime"] >= start_datetime

].copy()


# ============================================================
# X-AXIS SETTINGS
# ============================================================

if selected_period == "24 Hours":

    tick_format = "%H:%M"

    dtick_value = (
        3 *
        60 *
        60 *
        1000
    )


elif selected_period == "7 Days":

    tick_format = "%d %b"

    dtick_value = (
        24 *
        60 *
        60 *
        1000
    )


else:

    tick_format = "%d %b"

    dtick_value = (
        5 *
        24 *
        60 *
        60 *
        1000
    )


# ============================================================
# FLOW GRAPH
# ============================================================

st.divider()

st.subheader(
    f"🌊 Flow — Last {selected_period}"
)


if not period_df.empty:

    fig_flow = px.line(

        period_df,

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

        hovermode="x unified",

        xaxis=dict(

            title="Date / Time",

            tickformat=tick_format,

            dtick=dtick_value

        )

    )


    st.plotly_chart(

        fig_flow,

        use_container_width=True

    )


else:

    st.warning(
        "No observations available."
    )


# ============================================================
# STAGE GRAPH
# ============================================================

st.divider()

st.subheader(
    f"📏 Stage — Last {selected_period}"
)


if not period_df.empty:

    fig_stage = px.line(

        period_df,

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

        hovermode="x unified",

        xaxis=dict(

            title="Date / Time",

            tickformat=tick_format,

            dtick=dtick_value

        )

    )


    st.plotly_chart(

        fig_stage,

        use_container_width=True

    )


else:

    st.warning(
        "No observations available."
    )


# ============================================================
# PERIOD SUMMARY
# ============================================================

st.divider()

st.subheader(
    f"📊 {selected_period} Summary"
)


if not period_df.empty:

    summary_col1, summary_col2, summary_col3 = (
        st.columns(3)
    )


    with summary_col1:

        max_flow = period_df[
            "flow_m3s"
        ].max()


        if pd.notna(max_flow):

            st.metric(

                "Maximum Flow",

                f"{max_flow:.3f} m³/s"

            )

        else:

            st.metric(
                "Maximum Flow",
                "N/A"
            )


    with summary_col2:

        min_flow = period_df[
            "flow_m3s"
        ].min()


        if pd.notna(min_flow):

            st.metric(

                "Minimum Flow",

                f"{min_flow:.3f} m³/s"

            )

        else:

            st.metric(
                "Minimum Flow",
                "N/A"
            )


    with summary_col3:

        mean_flow = period_df[
            "flow_m3s"
        ].mean()


        if pd.notna(mean_flow):

            st.metric(

                "Mean Flow",

                f"{mean_flow:.3f} m³/s"

            )

        else:

            st.metric(
                "Mean Flow",
                "N/A"
            )


# ============================================================
# LATEST OBSERVATIONS
# ============================================================

st.divider()

st.subheader(
    "📋 Latest Observations"
)


display_df = period_df.sort_values(

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

    "Source: DWS Unaudited Real-Time Hydrological Data. "
    "Data are subject to verification."

)