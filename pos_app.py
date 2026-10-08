import streamlit as str_lit
import streamlit as st
import streamlit.components.v1 as components
import psycopg2
import pandas as pd
import os
import io
from datetime import datetime

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="R-TECH COMPUTER CENTER POS SYSTEM",
    page_icon="💻",
    layout="wide"
)

# ---------------------------------------------------------
# DATABASE CONNECTION (SUPABASE / POSTGRESQL URI)
# ---------------------------------------------------------
def get_db_connection():
    database_url = None
    try:
        if "supabase" in st.secrets and "url" in st.secrets["supabase"]:
            database_url = st.secrets["supabase"]["url"]
    except Exception:
        pass

    if not database_url:
        database_url = os.environ.get("DATABASE_URL") or "postgresql://postgres.ylwczrmidyndkvhgnblg:IzoMeELhcSr4Uhq5@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

    if not database_url:
        st.error("🚨 **Database Configuration Error:** Kulang o walang laman ang iyong `DATABASE_URL` sa Render Environment Variables!")
        st.info("Pumunta sa iyong **Render Dashboard > Environment**, gumawa ng variable na may pangalang **`DATABASE_URL`**, at ilagay ang buong URI connection string mula sa iyong Supabase database.")
        st.stop()

    try:
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        st.error(f"🚨 **Database Connection Failed:** {e}")
        st.info("Tip: Siguraduhing ginagamit mo ang Supabase **Connection Pooler URL (Port 6543)** upang maiwasan ang IPv6 network issues sa Render.")
        st.stop()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT -1,
            barcode TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            date_time TEXT NOT NULL,
            si_number TEXT,
            customer_name TEXT,
            total REAL NOT NULL
        )
    ''')
    
    # Safe column migrations if table already exists without si_number or customer_name
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS si_number TEXT;")
        cursor.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS customer_name TEXT;")
        conn.commit()
    except Exception:
        conn.rollback()
     
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_details (
            id SERIAL PRIMARY KEY,
            sale_id INTEGER REFERENCES sales(id),
            item_name TEXT,
            price REAL,
            quantity INTEGER,
            subtotal REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        default_items = [
            ("B&W Print (per page)", "Services", 5.00, -1, None),
            ("Color Print (per page)", "Services", 10.00, -1, None),
            ("Document Scanning", "Services", 15.00, -1, None),
            ("Lamination (per doc)", "Services", 30.00, -1, None),
            ("Rush ID Picture", "Services", 100.00, -1, None),
            ("Format Laptop/PC", "Services", 500.00, -1, None),
            ("Pancit Canton", "Inventory", 25.00, 50, "480001234567"),
            ("Cobra Energy Drink", "Inventory", 35.00, 30, "480001234568"),
            ("Mineral Water 500ml", "Inventory", 15.00, 40, "480001234569")
        ]
        cursor.executemany("INSERT INTO items (name, category, price, stock, barcode) VALUES (%s, %s, %s, %s, %s)", default_items)
        conn.commit()
    conn.close()

# ---------------------------------------------------------
# CATEGORIES LIST
# ---------------------------------------------------------
INVENTORY_CATEGORIES = sorted([
    "ACCESSORIES", "AMD Motherboard", "AMD Processor", "BROTHER INK",
    "BROTHER PRINTER", "CABLES", "CANON CARTRIDGE", "CANON INK",
    "CASING", "COMLINK", "CPU FAN", "DAHUA", "EPSON INK",
    "EPSON MAINTENANCE BOX", "EPSON PRINTER", "EXTERNAL CASE FOR SSD",
    "EXTERNAL DRIVE", "FLASH DRIVE", "HDD", "HDMI CABLE", "HEADPHONE",
    "HIKVISION", "HP INK", "Intel Motherboard", "Intel Processor",
    "Inventory", "KEYBOARD AND MOUSE", "LAPTOP CHARGER", "MICRO SD",
    "MONITOR", "POWER SUPPLY", "PROJECTOR & ACCESSORIES", "RAM",
    "RAM SODIMM", "SSD", "SPEAKER", "TAPO CCTV", "TPLINK", "UGREEN",
    "UPS", "WIFI ADAPTER"
], key=str.upper)

# ---------------------------------------------------------
# CACHED DATA FUNCTIONS
# ---------------------------------------------------------
@st.cache_data
def load_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM settings")
        rows = dict(cursor.fetchall())
    except Exception:
        conn.rollback()
        rows = {}
    conn.close()
    
    return {
        "store_name": rows.get("store_name", "R-TECH COMPUTER CENTER"),
        "tin_number": rows.get("tin_number", "123-456-789-00000"),
        "tax_rate_services": float(rows.get("tax_rate_services", 4.0)),
        "tax_rate_inventory": float(rows.get("tax_rate_inventory", 5.0))
    }

@st.cache_data
def load_services():
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, name, price FROM items WHERE category='Services' ORDER BY id ASC", conn)
    conn.close()
    return df

@st.cache_data
def load_inventory():
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, barcode, name, category, price, stock FROM items WHERE category != 'Services' ORDER BY id ASC", conn)
    conn.close()
    return df

@st.cache_data
def load_all_items():
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, name, category, price, stock FROM items ORDER BY id ASC", conn)
    conn.close()
    return df

def save_setting_db(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, str(value)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

# ---------------------------------------------------------
# RUN INITIALIZATIONS & LOAD SETTINGS
# ---------------------------------------------------------
init_db()
settings = load_settings()

# ---------------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []
if "barcode_input" not in st.session_state:
    st.session_state.barcode_input = ""

# ---------------------------------------------------------
# DIALOGS (MODALS)
# ---------------------------------------------------------
@st.dialog("⚙️ Tax & Store Settings")
def tax_settings_dialog():
    s = load_settings()
    store_name = st.text_input("Store Name", value=s["store_name"])
    tin_number = st.text_input("TIN Number", value=s["tin_number"])
    tax_serv = st.number_input("Services Tax Rate (%)", value=s["tax_rate_services"])
    tax_inv = st.number_input("Inventory Tax Rate (%)", value=s["tax_rate_inventory"])

    if st.button("💾 Save Settings", type="primary"):
        save_setting_db("store_name", store_name)
        save_setting_db("tin_number", tin_number)
        save_setting_db("tax_rate_services", tax_serv)
        save_setting_db("tax_rate_inventory", tax_inv)
        st.success("Settings saved successfully!")
        st.rerun()

@st.dialog("🖨️ Manage Services", width="large")
def services_manager_dialog():
    st.subheader("Add New Service")
    with st.form("service_form", clear_on_submit=True):
        s_name = st.text_input("Service Name")
        s_price = st.number_input("Price (₱)", min_value=0.0, step=1.0, value=0.0)
        submitted = st.form_submit_button("Add New Service")
        if submitted and s_name:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (%s, 'Services', %s, -1, NULL)", (s_name, s_price))
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.success("Service added to Supabase!")

    st.divider()
    st.subheader("Edit / Delete Services")
    df_serv = load_services()
    
    if not df_serv.empty:
        st.dataframe(df_serv, use_container_width=True, hide_index=True)
        
        edit_id = st.selectbox("Select Service ID to Edit", options=[0] + sorted(list(df_serv["id"])), key="edit_serv_select")
        if edit_id != 0:
            selected_row = df_serv[df_serv["id"] == edit_id].iloc[0]
            with st.form("edit_serv_form"):
                e_id = st.number_input("Edit Service ID", value=int(selected_row["id"]), min_value=1, step=1)
                e_name = st.text_input("Edit Service Name", value=selected_row["name"])
                e_price = st.number_input("Edit Price (₱)", value=float(selected_row["price"]), min_value=0.0, step=1.0)
                update_sub = st.form_submit_button("💾 Update Service")
                if update_sub:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE items SET id=%s, name=%s, price=%s WHERE id=%s", (e_id, e_name, e_price, edit_id))
                    conn.commit()
                    conn.close()
                    st.cache_data.clear()
                    st.success("Service updated successfully!")

        st.divider()
        del_id = st.selectbox("Select Service ID to Delete", options=[0] + sorted(list(df_serv["id"])), key="del_serv_select")
        if del_id != 0 and st.button("🗑️ Delete Selected Service"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE id=%s", (del_id,))
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.success("Service deleted.")

@st.dialog("📦 Manage Inventory", width="large")
def inventory_manager_dialog():
    st.subheader("Add New Inventory Item")
    with st.form("inventory_form", clear_on_submit=True):
        i_name = st.text_input("Item Name")
        i_category = st.selectbox("Category", options=INVENTORY_CATEGORIES)
        i_price = st.number_input("Price (₱)", min_value=0.0, step=1.0, value=0.0)
        i_stock = st.number_input("Stock Quantity", min_value=-1, step=1, value=0)
        i_barcode = st.text_input("Barcode (Optional)")
        submitted = st.form_submit_button("Add Inventory Item")
        if submitted and i_name:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (%s, %s, %s, %s, %s)", 
                           (i_name, i_category, i_price, i_stock, i_barcode if i_barcode
