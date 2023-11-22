import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
from babel.numbers import format_currency
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
sns.set(style='dark')
import json


def create_daily_orders_df(df_all):
    daily_orders_df = df_all.resample(rule='D', on='order_purchase_timestamp').agg({
        "order_id": "nunique",
        "price": "sum"
    })
    daily_orders_df = daily_orders_df.reset_index()
    daily_orders_df.rename(columns={
        "order_id": "order_count",
        "price": "revenue"
    }, inplace=True)
    
    return daily_orders_df


def create_bystate_df(df_all):
    bystate_df = df_all.groupby(by="customer_state").customer_id.nunique().reset_index()
    bystate_df.rename(columns={
        "customer_id": "customer_count",
        'customer_state': 'state'
    }, inplace=True)
    
    return bystate_df

def create_df_rfm(df_all, gdf, state_id):
    df_rfm = df_all.groupby(by=["customer_unique_id","customer_state","customer_city"], as_index=False).agg({
        "order_purchase_timestamp": "max", # mengambil tanggal order terakhir
        "order_id": "nunique", # menghitung jumlah order
        "price": "sum" # menghitung jumlah revenue yang dihasilkan
    })

    df_rfm.columns = ["customer_unique_id","state", "city","max_order_timestamp", "frequency", "monetary"]

    # menghitung kapan terakhir pelanggan melakukan transaksi (hari)
    df_rfm["max_order_timestamp"] = df_rfm["max_order_timestamp"].dt.date
    recent_date = df_all["order_purchase_timestamp"].dt.date.max()
    df_rfm["recency"] = df_rfm["max_order_timestamp"].apply(lambda x: (recent_date - x).days)
    df_rfm.drop("max_order_timestamp", axis=1, inplace=True)
    df_rfm.sort_values(by="frequency", ascending=False).head(10)

    # state name
    df_rfm['state_name'] = df_rfm['state'].map(state_id)

    # menghitung RFM per state
    df_rfm_state=df_rfm.groupby(by=["state","state_name"], as_index=False).agg({
        "customer_unique_id": "nunique",
        "frequency": ["sum",'max'],
        "monetary": ["sum",'max'],
        "recency": ['median','min'],
    })
    df_rfm_state.columns=["state", "state_name", "count_customer", "total_frequency", "max_frequency", "total_monetary", "max_monetary", "median_recency", "min_recency"]
    df_rfm_state.sort_values(by="total_monetary", ascending=False)

    df_rfm_state_with_gdf = df_rfm_state.merge(
        right=gdf,
        left_on="state",
        right_on="id",
        how="left",
    )

    return df_rfm, df_rfm_state, df_rfm_state_with_gdf

def create_geojson_brazil():
    brazil_geo_json_path = '../data/geojson/brazil_geo.json'
    geojson_brazil = json.load(open(brazil_geo_json_path, "r"))
    state_id = {}
    for feature in geojson_brazil["features"]:
        state_id[feature["id"]] = feature['properties']['name']

    return geojson_brazil, state_id


# main
df_all = pd.read_csv("./df_all.csv")
gdf = pd.read_csv("./gdf.csv")

datetime_columns = ['order_purchase_timestamp','shipping_limit_date']
df_all.sort_values(by="order_purchase_timestamp", inplace=True)
df_all.reset_index(inplace=True)
for column in datetime_columns:
    df_all[column] = pd.to_datetime(df_all[column])


min_date = df_all["order_purchase_timestamp"].min()
max_date = df_all["order_purchase_timestamp"].max()

with st.sidebar:
    # Menambahkan logo perusahaan
    st.image("https://cdn-icons-png.flaticon.com/512/197/197386.png")
    
    # Mengambil start_date & end_date dari date_input
    start_date, end_date = st.date_input(
        label='Rentang Waktu',min_value=min_date,
        max_value=max_date,
        value=[min_date, max_date]
    )

main_df = df_all[
    (df_all["order_purchase_timestamp"] >= str(start_date)) & 
    (df_all["order_purchase_timestamp"] <= str(end_date))
]

daily_orders_df = create_daily_orders_df(main_df)
bystate_df = create_bystate_df(main_df)
geojson_brazil, state_id = create_geojson_brazil()
df_rfm, df_rfm_state, df_rfm_state_with_gdf = create_df_rfm(main_df, gdf, state_id)





st.header('Brazilian E-Commerce Analysis :sparkles:')
st.text('by Mohammad Zulkifli Katili')




st.subheader('Daily Orders')
col1, col2 = st.columns(2)

with col1:
    total_orders = daily_orders_df.order_count.sum()
    st.metric("Total orders", value=total_orders)

with col2:
    total_revenue = format_currency(daily_orders_df.revenue.sum(), "AUD", locale='es_CO') 
    st.metric("Total Revenue", value=total_revenue)

fig, ax = plt.subplots(figsize=(16, 8))
ax.plot(
    daily_orders_df["order_purchase_timestamp"],
    daily_orders_df["order_count"],
    marker='o', 
    linewidth=2,
    color="#90CAF9"
)
ax.tick_params(axis='y', labelsize=20)
ax.tick_params(axis='x', labelsize=15)
st.pyplot(fig)





st.subheader("Customer Demographics")
fig, ax = plt.subplots(figsize=(20, 10))
colors = ["#90CAF9", "#D3D3D3", "#D3D3D3", "#D3D3D3", "#D3D3D3", "#D3D3D3", "#D3D3D3", "#D3D3D3"]
sns.barplot(
    x="customer_count", 
    y="state",
    data=bystate_df.sort_values(by="customer_count", ascending=False),
    palette=colors,
    ax=ax
)
ax.set_title("Number of Customer by States", loc="center", fontsize=30)
ax.set_ylabel(None)
ax.set_xlabel(None)
ax.tick_params(axis='y', labelsize=20)
ax.tick_params(axis='x', labelsize=15)
st.pyplot(fig)





st.subheader("Best State Based on RFM Parameters")

# ["state", "state_name", "count_customer", "total_frequency", "max_frequency", "total_monetary", "max_monetary", "median_recency", "min_recency"

col1, col2, col3 = st.columns(3)
 
with col1:
    avg_recency = round(df_rfm_state.median_recency.mean(), 1)
    st.metric("Average Recency (days)", value=avg_recency)
 
with col2:
    avg_frequency = round(df_rfm_state.total_frequency.mean(), 2)
    st.metric("Average Frequency", value=avg_frequency)
 
with col3:
    avg_frequency = format_currency(df_rfm_state.total_monetary.mean(), "BRA", locale='es_CO') 
    st.metric("Average Monetary", value=avg_frequency)
 
df_rfm_state['percentage_monetary'] = ((df_rfm_state['total_monetary'] / df_rfm_state['total_monetary'].sum()) * 100).round(1)




st.subheader("Recency")
# Create the bar plot
fig = px.bar(
    df_rfm_state,
    x='state_name',
    y='median_recency',
    text='median_recency',  # Display percentage values on top of bars
    title='Median Recency (Aggregate) of Customer per State'
)
# Add a line trace for 'min_recency'
line_trace = go.Scatter(
    x=df_rfm_state['state_name'],
    y=df_rfm_state['min_recency'],
    mode='lines',
    name='Min Recency (Individu)',
    line=dict(color='red', dash='solid')  # Customize line color and style
)
# Add the line trace to the figure
fig.add_trace(line_trace)
# Customize the layout to make the chart more readable
fig.update_layout(
    yaxis=dict(title='Days'),
    xaxis=dict(title='State'),
    barmode='group'
)
# Show the figure
st.plotly_chart(fig)


fig = px.choropleth_mapbox(
    df_rfm_state,
    locations="state",
    geojson=geojson_brazil,
    color="median_recency",
    mapbox_style="carto-positron",
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
    opacity=0.5,
)
# Scatter plot code with size based on min_recency
scatter_fig = px.scatter_mapbox(
    df_rfm_state_with_gdf,
    lat='centroid_latitude',
    lon='centroid_longitude',
    hover_data=["state_name", "min_recency","median_recency"],
    size='min_recency',  # Set the size based on min_recency values
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
)
# Gabungkan peta choropleth dan scatter plot
fig.add_trace(scatter_fig.data[0])
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
# show
st.plotly_chart(fig)



st.subheader("Frequency")
df_rfm_state['percentage_frequency'] = ((df_rfm_state['total_frequency'] / df_rfm_state['total_frequency'].sum()) * 100).round(1)

# Create the bar plot
fig = px.bar(
    df_rfm_state,
    x='state_name',
    y='total_frequency',
    text='percentage_frequency',  # Display percentage values on top of bars
    title='Total transaction (Frequency) per State'
)

# Customize the layout to make the chart more readable
fig.update_layout(yaxis=dict(title='Transactions'),
                  xaxis=dict(title='State'),
                  barmode='group')
# Use texttemplate to format the text with one decimal place
fig.update_traces(texttemplate='%{text:.1f}%')
# Show the figure
st.plotly_chart(fig)


fig = px.choropleth_mapbox(
    df_rfm_state,
    locations="state",
    geojson=geojson_brazil,
    color="total_frequency",
    hover_name="state_name",
    hover_data=["state", "total_frequency"],
    mapbox_style="carto-positron",
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
    opacity=0.5,
)

# Buat scatter plot dari titik tengah menggunakan Plotly Express
scatter_fig = px.scatter_mapbox(
    df_rfm_state_with_gdf,
    lat='centroid_latitude',
    lon='centroid_longitude',
    hover_data=["state_name"],
    size='max_frequency',  # Set the size based on min_recency values
    mapbox_style="carto-positron",
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
)

# Gabungkan peta choropleth dan scatter plot
fig.add_trace(scatter_fig.data[0])
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig)



st.subheader("Monetary")
df_rfm_state['percentage_monetary'] = ((df_rfm_state['total_monetary'] / df_rfm_state['total_monetary'].sum()) * 100).round(1)

# Create the bar plot
fig = px.bar(
    df_rfm_state,
    x='state_name',
    y='total_monetary',
    text='percentage_monetary',  # Display percentage values on top of bars
    title='Total Monetary per State'
)

# Customize the layout to make the chart more readable
fig.update_layout(yaxis=dict(title='Brazilian Reals (R$)'),
                  xaxis=dict(title='State'),
                  barmode='group')

# Use texttemplate to format the text with one decimal place
fig.update_traces(texttemplate='%{text:.1f}%')

# Show the figure
st.plotly_chart(fig)

fig = px.choropleth_mapbox(
    df_rfm_state,
    locations="state",
    geojson=geojson_brazil,
    color="total_monetary",
    hover_name="state_name",
    hover_data=["state", "total_monetary"],
    mapbox_style="carto-positron",
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
    opacity=0.5,
)
# Buat scatter plot dari titik tengah menggunakan Plotly Express
scatter_fig = px.scatter_mapbox(
    df_rfm_state_with_gdf,
    lat='centroid_latitude',
    lon='centroid_longitude',
    hover_data=["state_name"],
    size='max_monetary',  # Set the size based on min_recency values
    mapbox_style="carto-positron",
    center={"lat": -14.4095261, "lon": -51.31668},
    zoom=3,
)
# Gabungkan peta choropleth dan scatter plot
fig.add_trace(scatter_fig.data[0])
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig)



st.caption('Copyright (c) Mohammad Zulkifli Katili 2023')