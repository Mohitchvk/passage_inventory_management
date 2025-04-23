import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import StringIO

import json
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
# creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)


# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# creds = ServiceAccountCredentials.from_json_keyfile_name(".gitignore/inventory-management-457621-40cc2bc0291b.json", scope)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open("Inventory Tracking").sheet1

# --- Helpers ---
def get_column_letter(n):
    result = ''
    while n >= 0:
        result = chr(n % 26 + ord('A')) + result
        n = n // 26 - 1
    return result

def load_data():
    return pd.DataFrame(sheet.get_all_records())

def update_sheet_column(col_index, data):
    col_letter = get_column_letter(col_index)
    update_range = f"{col_letter}2:{col_letter}{len(data)+1}"
    sheet.batch_update([{
        'range': update_range,
        'values': [[v] for v in data]
    }])

# --- Load and Cache Data ---
@st.cache_data(show_spinner=False)
def get_cached_data():
    return load_data()

df = get_cached_data()
date_columns = df.columns[2:]

# --- UI ---
st.title("📦 Inventory Manager")

selected_date = st.selectbox(" Select a date:", date_columns)

# Load editable state
if 'session_data' not in st.session_state:
    st.session_state['session_data'] = {}

if selected_date not in st.session_state['session_data']:
    quantities = [int(df.at[i, selected_date]) if str(df.at[i, selected_date]).isdigit() else 0 for i in range(len(df))]
    comments = ["" if str(df.at[i, selected_date]).isdigit() else str(df.at[i, selected_date]) for i in range(len(df))]
    st.session_state['session_data'][selected_date] = {'quantities': quantities, 'comments': comments}

q_data = st.session_state['session_data'][selected_date]

# --- Inventory Table ---
st.subheader(f"Update Inventory - {selected_date}")
for i, row in df.iterrows():
    item = row['Items']
    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 2, 5])

    with col1:
        st.text(item)
    with col2:
        if st.button("➖", key=f"minus_{selected_date}_{i}"):
            q_data['quantities'][i] = max(0, q_data['quantities'][i] - 1)
    with col3:
        if st.button("➕", key=f"plus_{selected_date}_{i}"):
            q_data['quantities'][i] += 1
    with col4:
        q_data['quantities'][i] = st.number_input(
            "Qty", value=q_data['quantities'][i], step=1, key=f"qty_{selected_date}_{i}"
        )
    with col5:
        q_data['comments'][i] = st.text_input(
            "Comment", value=q_data['comments'][i], key=f"comment_{selected_date}_{i}"
        )

# --- Submit Updates ---
if st.button(" Update Google Sheet & Download CSV"):
    final_values = []
    export_rows = []
    for i in range(len(df)):
        comment = q_data['comments'][i]
        qty = q_data['quantities'][i]
        val = comment if comment else qty
        final_values.append(val)

        if (comment and comment.strip()) or (isinstance(qty, int) and qty > 0):
            export_rows.append((df.at[i, 'Items'], comment if comment else qty))

    try:
        update_sheet_column(df.columns.get_loc(selected_date), final_values)
        get_cached_data.clear()
        st.success("✅ Sheet updated successfully.")

        # Prepare CSV
        csv_df = pd.DataFrame(export_rows, columns=["Items", "Quantity/Comment"])
        csv_buffer = StringIO()
        csv_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="⬇️ Download Today's Inventory CSV",
            data=csv_buffer.getvalue(),
            file_name=f"{selected_date.replace('/', '-')}_inventory.csv",
            mime='text/csv'
        )
    except Exception as e:
        st.error(f"❌ Error updating sheet: {e}")
