import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import csv

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="R-TECH COMPUTER CENTER POS SYSTEM",
    page_icon="💻",
    layout="wide"
)

# ---------------------------------------------------------
# DATABASE & SETTINGS MANAGEMENT
# ---------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect("pos_rtech_computer.db")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER DEFAULT -1,
            barcode TEXT UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_time TEXT NOT NULL,
            subtotal REAL DEFAULT 0,
            non_vat_sales REAL DEFAULT 0,
            vat_amount REAL DEFAULT 0,
            total REAL NOT NULL,
            cash REAL NOT NULL,
            change_amount REAL NOT NULL
        )
    ''')
     
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            item_name TEXT,
            price REAL,
            quantity INTEGER,
            subtotal REAL,
            FOREIGN KEY (sale_id) REFERENCES sales(id)
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
            ("Mineral Water 500ml", "Inventory", 15.00, 40, "480001234569"),
            ("Cup Noodles", "Inventory", 30.00, 25, "480001234570"),
            ("In-ear Earphones", "Inventory", 120.00, 10, "480001234571"),
            ("16GB USB Flash Drive", "Inventory", 250.00, 8, "480001234572"),
            ("A4 Bond Paper (10s)", "Inventory", 15.00, 100, "480001234573")
        ]
        cursor.executemany("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, ?, ?, ?, ?)", default_items)
        conn.commit()
    conn.close()

def load_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM settings")
        rows = dict(cursor.fetchall())
    except Exception:
        rows = {}
    conn.close()
    
    return {
        "store_name": rows.get("store_name", "R-TECH COMPUTER CENTER"),
        "tin_number": rows.get("tin_number", "123-456-789-00000"),
        "tax_rate_services": float(rows.get("tax_rate_services", 4.0)),
        "tax_rate_inventory": float(rows.get("tax_rate_inventory", 5.0))
    }

def save_setting_db(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []
if "barcode_input" not in st.session_state:
    st.session_state.barcode_input = ""

settings = load_settings()

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
    st.subheader("Add / Edit Services")
    conn = get_db_connection()
    
    with st.form("service_form"):
        s_name = st.text_input("Service Name")
        s_price = st.number_input("Price (₱)", min_value=0.0, step=1.0)
        submitted = st.form_submit_button("Add New Service")
        if submitted and s_name:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, 'Services', ?, -1, NULL)", (s_name, s_price))
            conn.commit()
            st.success("Service added!")
            st.rerun()

    st.divider()
    st.subheader("Existing Services")
    df_serv = pd.read_sql("SELECT id, name, price FROM items WHERE category='Services'", conn)
    conn.close()
    
    if not df_serv.empty:
        st.dataframe(df_serv, use_container_width=True)
        del_id = st.selectbox("Select Service ID to Delete", options=[0] + list(df_serv["id"]))
        if del_id != 0 and st.button("🗑️ Delete Selected Service"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE id=?", (del_id,))
            conn.commit()
            conn.close()
            st.success("Service deleted.")
            st.rerun()

@st.dialog("📦 Manage Inventory", width="large")
def inventory_manager_dialog():
    st.subheader("Add / Edit Inventory Item")
    conn = get_db_connection()
    
    with st.form("inventory_form"):
        i_name = st.text_input("Item Name")
        i_price = st.number_input("Price (₱)", min_value=0.0, step=1.0)
        i_stock = st.number_input("Stock Quantity", min_value=0, step=1, value=10)
        i_barcode = st.text_input("Barcode (Optional)")
        submitted = st.form_submit_button("Add Inventory Item")
        if submitted and i_name:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, 'Inventory', ?, ?, ?)", 
                           (i_name, i_price, i_stock, i_barcode if i_barcode else None))
            conn.commit()
            st.success("Inventory item added!")
            st.rerun()

    st.divider()
    st.subheader("Existing Inventory")
    df_inv = pd.read_sql("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory'", conn)
    conn.close()
    
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True)
        del_id = st.selectbox("Select Item ID to Delete", options=[0] + list(df_inv["id"]), key="del_inv_select")
        if del_id != 0 and st.button("🗑️ Delete Selected Item"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE id=?", (del_id,))
            conn.commit()
            conn.close()
            st.success("Item deleted.")
            st.rerun()

@st.dialog("🏷️ Edit Item Discount")
def edit_discount_dialog(index, item):
    st.write(f"Editing discount for: **{item['name']}**")
    dtype = st.selectbox("Discount Type", options=["none", "percentage", "fixed"], index=["none", "percentage", "fixed"].index(item['discount_type']))
    val = st.number_input("Discount Value (% or ₱)", value=float(item['discount_value']))

    if st.button("Apply Discount"):
        st.session_state.cart[index]['discount_type'] = dtype
        st.session_state.cart[index]['discount_value'] = val if dtype != 'none' else 0.0
        st.success("Discount applied!")
        st.rerun()

@st.dialog("🧾 Receipt Preview", width="medium")
def receipt_preview_dialog(receipt_text):
    st.text_area("Receipt Output", value=receipt_text, height=400)
    st.download_button("📥 Download Receipt Text", data=receipt_text, file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain")

# ---------------------------------------------------------
# MAIN HEADER BAR
# ---------------------------------------------------------
header_col1, header_col2 = st.columns([3, 2])
with header_col1:
    st.markdown(f"## 💻 {settings['store_name']}")
    st.caption(f"TIN: {settings['tin_number']} | Services Tax: {settings['tax_rate_services']}% | Inventory Tax: {settings['tax_rate_inventory']}%")

with header_col2:
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        if st.button("⚙️ Settings"):
            tax_settings_dialog()
    with btn_col2:
        if st.button("🖨️ Services"):
            services_manager_dialog()
    with btn_col3:
        if st.button("📦 Inventory"):
            inventory_manager_dialog()

st.divider()

# ---------------------------------------------------------
# CORE APP LAYOUT (SPLIT SCREEN: CATALOG & CART)
# ---------------------------------------------------------
left_col, right_col = st.columns([1.3, 1])

with left_col:
    # Barcode Scanner / Quick Search section
    with st.form("barcode_form", clear_on_submit=True):
        b_col1, b_col2 = st.columns([4, 1])
        with b_col1:
            scanned_code = st.text_input("Barcode Scanner / Search", placeholder="Scan barcode or type item code...", key="scan_input")
        with b_col2:
            st.write("") # spacing alignment
            submitted_scan = st.form_submit_button("Scan / Add", use_container_width=True)

        if submitted_scan and scanned_code:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price, stock, category FROM items WHERE barcode=? OR name LIKE ?", (scanned_code, f"%{scanned_code}%"))
            db_item = cursor.fetchone()
            conn.close()

            if db_item:
                item_id, name, price, stock, cat = db_item
                if cat == "Inventory" and stock == 0:
                    st.error(f"Item '{name}' is out of stock!")
                else:
                    # Check if already in cart
                    found = False
                    for c_item in st.session_state.cart:
                        if c_item['id'] == item_id:
                            if cat == "Inventory" and stock != -1 and c_item['qty'] >= stock:
                                st.warning(f"Stock limit reached for '{name}'.")
                            else:
                                c_item['qty'] += 1
                            found = True
                            break
                    if not found:
                        st.session_state.cart.append({
                            'id': item_id, 'name': name, 'price': price, 'qty': 1, 'category': cat,
                            'discount_type': 'none', 'discount_value': 0.0
                        })
                    st.success(f"Added: {name}")
                    st.rerun()
            else:
                st.error(f"Item not found: {scanned_code}")

    # Tabs for Services, Inventory, and Daily Sales
    tab_serv, tab_inv, tab_sales = st.tabs(["🖨️ Services", "📦 Inventory", "📊 Daily Sales"])

    conn = get_db_connection()

    with tab_serv:
        st.subheader("Available Services")
        df_services = pd.read_sql("SELECT id, name, price FROM items WHERE category='Services'", conn)
        st.dataframe(df_services, use_container_width=True, hide_index=True)
        
        selected_serv_id = st.selectbox("Select Service to Add", options=[0] + list(df_services["id"]), key="sel_serv")
        if st.button("Add Selected Service to Order"):
            if selected_serv_id != 0:
                row = df_services[df_services["id"] == selected_serv_id].iloc[0]
                found = False
                for c_item in st.session_state.cart:
                    if c_item['id'] == row['id']:
                        c_item['qty'] += 1
                        found = True
                        break
                if not found:
                    st.session_state.cart.append({
                        'id': row['id'], 'name': row['name'], 'price': row['price'], 'qty': 1, 'category': 'Services',
                        'discount_type': 'none', 'discount_value': 0.0
                    })
                st.rerun()

    with tab_inv:
        st.subheader("Available Inventory")
        df_inventory = pd.read_sql("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory'", conn)
        st.dataframe(df_inventory, use_container_width=True, hide_index=True)
        
        selected_inv_id = st.selectbox("Select Inventory Item to Add", options=[0] + list(df_inventory["id"]), key="sel_inv")
        if st.button("Add Selected Item to Order"):
            if selected_inv_id != 0:
                row = df_inventory[df_inventory["id"] == selected_inv_id].iloc[0]
                if row['stock'] == 0:
                    st.error("Item is out of stock!")
                else:
                    found = False
                    for c_item in st.session_state.cart:
                        if c_item['id'] == row['id']:
                            if row['stock'] != -1 and c_item['qty'] >= row['stock']:
                                st.warning("Stock limit reached.")
                            else:
                                c_item['qty'] += 1
                            found = True
                            break
                    if not found:
                        st.session_state.cart.append({
                            'id': row['id'], 'name': row['name'], 'price': row['price'], 'qty': 1, 'category': 'Inventory',
                            'discount_type': 'none', 'discount_value': 0.0
                        })
                    st.rerun()

    with tab_sales:
        st.subheader("Daily Sales History")
        df_sales = pd.read_sql("SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount FROM sales ORDER BY id DESC", conn)
        st.dataframe(df_sales, use_container_width=True, hide_index=True)

    conn.close()

with right_col:
    st.markdown("### 🛒 Current Order")
    
    if st.button("Clear Cart"):
        st.session_state.cart = []
        st.rerun()

    # Render Cart Items
    if not st.session_state.cart:
        st.info("Cart is empty.")
    else:
        subtotal = 0.0
        tax_services = 0.0
        tax_inventory = 0.0

        customer_type = st.selectbox("Customer Type", ["Regular Customer", "Government Customer"])

        for idx, item in enumerate(st.session_state.cart):
            base_total = item['price'] * item['qty']
            disc_amt = 0.0
            if item['discount_type'] == 'percentage':
                disc_amt = base_total * (item['discount_value'] / 100.0)
            elif item['discount_type'] == 'fixed':
                disc_amt = item['discount_value'] * item['qty']
            
            if disc_amt > base_total:
                disc_amt = base_total
                
            item_subtotal = base_total - disc_amt
            item['subtotal'] = item_subtotal

            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.write(f"**{item['name']}** (₱{item['price']:,.2f} x {item['qty']})")
                if item['discount_type'] != 'none':
                    st.caption(f"Disc: {item['discount_value']}{'%' if item['discount_type']=='percentage':'₱'} (-₱{disc_amt:,.2f})")
            with cols[1]:
                if st.button("➕", key=f"inc_{idx}"):
                    item['qty'] += 1
                    st.rerun()
            with cols[2]:
                if st.button("➖", key=f"dec_{idx}"):
                    item['qty'] -= 1
                    if item['qty'] <= 0:
                        st.session_state.cart.pop(idx)
                    st.rerun()
            with cols[3]:
                if st.button("🏷️", key=f"disc_{idx}"):
                    edit_discount_dialog(idx, item)

            subtotal += item_subtotal

            if customer_type == "Government Customer":
                if item['category'] == "Services":
                    tax_services += item_subtotal * (settings['tax_rate_services'] / 100.0)
                elif item['category'] == "Inventory":
                    tax_inventory += item_subtotal * (settings['tax_rate_inventory'] / 100.0)

        total_tax = tax_services + tax_inventory
        total_due = subtotal + total_tax

        st.divider()
        st.write(f"**Subtotal:** ₱ {subtotal:,.2f}")
        if customer_type == "Government Customer":
            st.write(f"**Services Tax ({settings['tax_rate_services']}%):** ₱ {tax_services:,.2f}")
            st.write(f"**Inventory Tax ({settings['tax_rate_inventory']}%):** ₱ {tax_inventory:,.2f}")
        st.markdown(f"### **TOTAL DUE:** ₱ {total_due:,.2f}")

        cash_tendered = st.number_input("Cash Tendered (₱)", min_value=0.0, step=10.0, value=0.0)
        change_amount = cash_tendered - total_due

        if cash_tendered > 0:
            if change_amount >= 0:
                st.success(f"Change: ₱ {change_amount:,.2f}")
            else:
                st.error(f"Insufficient Cash! Short by: ₱ {abs(change_amount):,.2f}")

        if st.button("✔ COMPLETE SALE / CHECKOUT", type="primary", use_container_width=True):
            if cash_tendered < total_due:
                st.error("Kulang ang ibinigay na cash ng customer.")
            else:
                date_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                non_vat_sales = subtotal if customer_type == "Regular Customer" else 0.0

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sales (date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (date_time_str, subtotal, non_vat_sales, total_tax, total_due, cash_tendered, change_amount))
                
                sale_id = cursor.lastrowid

                for item in st.session_state.cart:
                    cursor.execute('''
                        INSERT INTO sales_details (sale_id, item_name, price, quantity, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (sale_id, item['name'], item['price'], item['qty'], item['subtotal']))

                    if item['category'] == 'Inventory':
                        cursor.execute('''
                            UPDATE items SET stock = stock - ? WHERE id = ? AND stock != -1
                        ''', (item['qty'], item['id']))

                conn.commit()
                conn.close()

                # Build receipt string
                receipt_text = "=" * 42 + "\n"
                receipt_text += f"{settings['store_name']:^42}\n"
                receipt_text += f"TIN: {settings['tin_number']:^42}\n"
                receipt_text += "=" * 42 + "\n"
                receipt_text += f"Sale ID: #{sale_id}\n"
                receipt_text += f"Date/Time: {date_time_str}\n"
                receipt_text += f"Customer: {customer_type}\n"
                receipt_text += "-" * 42 + "\n"
                for item in st.session_state.cart:
                    receipt_text += f"{item['name'][:15]:<16} {item['qty']:<3} ₱{item['subtotal']:<9.2f}\n"
                receipt_text += "-" * 42 + "\n"
                receipt_text += f"TOTAL DUE: ₱ {total_due:,.2f}\n"
                receipt_text += f"Cash Tendered: ₱ {cash_tendered:,.2f}\n"
                receipt_text += f"Change: ₱ {change_amount:,.2f}\n"
                receipt_text += "=" * 42 + "\n"
                receipt_text += f"{'SALAMAT SA PAGTANGKILIK!':^42}\n"

                st.session_state.cart = []
                st.success(f"Sale completed successfully! Change: ₱ {change_amount:,.2f}")
                receipt_preview_dialog(receipt_text)
