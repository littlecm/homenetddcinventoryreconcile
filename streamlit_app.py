import streamlit as st
import pandas as pd
import requests
from io import StringIO

# Constants
VINSOLUTIONS_BASE_URL = "https://feeds.amp.auto/feeds/vinsolutions/"
DEALERDOTCOM_URL = "https://feeds.amp.auto/feeds/coxautomotive/dealerdotcom.csv"
API_BASE_URL = "https://cws.gm.com/vs-cws/vehshop/v2/vehicle"

# Helper functions
def download_csv(url):
    response = requests.get(url)
    if response.ok:
        return pd.read_csv(StringIO(response.text))
    else:
        st.error("Failed to download data. Please check the URL and try again.")
        return pd.DataFrame()

def get_api_data(vin):
    api_url = f"{API_BASE_URL}?vin={vin}&postalCode=48640&locale=en_US"
    response = requests.get(api_url, headers={
        "authority": "cws.gm.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })
    if response.ok:
        return response.json()
    else:
        return None

# Available filenames excluding 'nooverlay'
vinsolutions_filenames = [
    "curtisgarberchevroletcadillac-13992.csv",
    "delraybuickgmc-5877.csv",
    "garberacuraofrochester-9965.csv",
    "garberautomall-3888.csv",
    "garberbayroad-3884.csv",
    "garberbuick-3882.csv",
    "garberbuickgmcoffortpierce-6581.csv",
    "garberchevroletbuickchesaning-17699.csv",
    "garberchevrolethighland-3746.csv",
    "garberchevroletlinwood-10117.csv",
    "garberchevroletmidland-8710.csv",
    "GarberChevroletSaginaw-13623.csv",
    "garberchevroletsubaru-10288.csv",
    "garberhonda-13327.csv",
    "garberrandallbuickgmccadillac.csv",
    "garberrandallchevrolet.csv",
    "nissanofbradenton-14486.csv",
    "porscheaudirochester-9967.csv",
    "sunrisechevroletglendaleheights-3886.csv"
]

# Application
st.title("VIN Reconciliation Tool")

# User Inputs
selected_filename = st.selectbox("Select a VinSolutions CSV filename:", vinsolutions_filenames)
selected_type = st.selectbox("Select the vehicle type:", ["All", "New", "Used"])
dealerdotcom_data = download_csv(DEALERDOTCOM_URL)
dealer_ids = dealerdotcom_data['dealer_id'].unique()
selected_dealer_id = st.selectbox("Select a Dealer ID:", dealer_ids)

if st.button("Reconcile Data"):
    vinsolutions_data = download_csv(VINSOLUTIONS_BASE_URL + selected_filename)
    if selected_type != "All":
        vinsolutions_data = vinsolutions_data[vinsolutions_data['Type'] == selected_type]
    dealerdotcom_filtered = dealerdotcom_data[(dealerdotcom_data['dealer_id'] == selected_dealer_id) & (dealerdotcom_data['type'] == "Used")]

    vinsolutions_vins = set(vinsolutions_data['VIN'].tolist())
    dealerdotcom_vins = set(dealerdotcom_filtered['vin'].tolist())

    # Reconcile VINs
    common_vins = vinsolutions_vins.intersection(dealerdotcom_vins)
    unique_vinsolutions = vinsolutions_vins - dealerdotcom_vins
    unique_dealerdotcom = dealerdotcom_vins - vinsolutions_vins

    results = []
    for vin in common_vins:
        results.append({'VIN': vin, 'Result': "Common"})
    for vin in unique_vinsolutions.union(unique_dealerdotcom):
        api_data = get_api_data(vin)
        if api_data:
            if "mathBox" in api_data and "recallInfo" in api_data["mathBox"] and "This vehicle is temporarily unavailable" in api_data["mathBox"]["recallInfo"]:
                results.append({'VIN': vin, 'Result': "Vehicle with Recall"})
                continue
            if "inventoryStatus" in api_data:
                inventory_status = api_data["inventoryStatus"].get("name")
                if inventory_status:
                    if inventory_status == "Rtl_Intrans" and vin in unique_dealerdotcom:
                        results.append({'VIN': vin, 'Result': "In Transit - Not expected in HomeNet"})
                    elif inventory_status == "EligRtlStkCT":
                        results.append({'VIN': vin, 'Result': "Courtesy Vehicle"})
                    else:
                        results.append({'VIN': vin, 'Result': f"Other Inventory Status: {inventory_status}"})
                else:
                    if vin in unique_dealerdotcom:
                        results.append({'VIN': vin, 'Result': "Exclusive to Dealer.com Website"})
                    else:
                        results.append({'VIN': vin, 'Result': "Exclusive to HomeNet"})
        else:
            results.append({'VIN': vin, 'Result': "API request failed"})

    results_df = pd.DataFrame(results)
    st.dataframe(results_df)

    # Summary breakdown
    summary_df = results_df['Result'].value_counts().reset_index()
    summary_df.columns = ['Issue', 'Count']
    st.dataframe(summary_df)
