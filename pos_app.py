import streamlit as st
import streamlit.components.v1 as components
import psycopg2
import pandas as pd
import os
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
# DATABASE & SETTINGS FUNCTIONS (SUPABASE / POSTGRESQL)
# ---------------------------------------------------------
def get_db_connection():
    host = None
    database = None
    user = None
    password = None
    port = "5432"

    try:
        if "supabase" in st.secrets:
            db_config = st.secrets["supabase"]
            host = db_config.get("host")
            database = db_config.get("database")
            user = db_config.get("user")
            password = db_config.get("password")
            port = str(db_config.get("port", "5432"))
    except Exception:
        pass

    if not host:
        host = os.environ.get("SUPABASE_HOST")
        database = os.environ.get("SUPABASE_DATABASE")
        user = os.environ.get("SUPABASE_USER")
        password = os.environ.get("SUPABASE_PASSWORD")
        port = os.environ.get("SUPABASE_PORT", "5432")

    if not host or not database or not user or not password:
        st.error("🚨 **Database Configuration Error:** Kulang o walang laman ang iyong Supabase Environment Variables sa Render dashboard!")
        st.info("Pumunta sa iyong **Render Dashboard > Environment** at siguraduhing naidagdag mo ang mga sumusunod:\n- `SUPABASE_HOST`\n- `SUPABASE_DATABASE`\n- `SUPABASE_USER`\n- `SUPABASE_PASSWORD`\n- `SUPABASE_PORT`")
        st.stop()

    conn = psycopg2.connect(
        host=host,
        database=database,
        user=user,
        password=password,
        port=port
    )
    return conn

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
            ("Mineral Water 500ml", "Inventory", 15.00, 40, "480001234569"),
            ("Cup Noodles", "Inventory", 30.00, 25, "480001234570"),
            ("In-ear Earphones", "Inventory", 120.00, 10, "480001234571"),
            ("16GB USB Flash Drive", "Inventory", 250.00, 8, "480001234572"),
            ("A4 Bond Paper (10s)", "Inventory", 15.00, 100, "480001234573")
        ]
        cursor.executemany("INSERT INTO items (name, category, price, stock, barcode) VALUES (%s, %s, %s, %s, %s)", default_items)
        conn.commit()
    conn.close()

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

def save_setting_db(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

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
            st.success("Service added to Supabase!")

    st.divider()
    st.subheader("Edit / Delete Services")
    conn = get_db_connection()
    df_serv = pd.read_sql("SELECT id, name, price FROM items WHERE category='Services'", conn)
    conn.close()
    
    if not df_serv.empty:
        st.dataframe(df_serv, use_container_width=True, hide_index=True)
        
        edit_id = st.selectbox("Select Service ID to Edit", options=[0] + list(df_serv["id"]), key="edit_serv_select")
        if edit_id != 0:
            selected_row = df_serv[df_serv["id"] == edit_id].iloc[0]
            with st.form("edit_serv_form"):
                e_name = st.text_input("Edit Service Name", value=selected_row["name"])
                e_price = st.number_input("Edit Price (₱)", value=float(selected_row["price"]), min_value=0.0, step=1.0)
                update_sub = st.form_submit_button("💾 Update Service")
                if update_sub:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE items SET name=%s, price=%s WHERE id=%s", (e_name, e_price, edit_id))
                    conn.commit()
                    conn.close()
                    st.success("Service updated successfully!")

        st.divider()
        del_id = st.selectbox("Select Service ID to Delete", options=[0] + list(df_serv["id"]), key="del_serv_select")
        if del_id != 0 and st.button("🗑️ Delete Selected Service"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE id=%s", (del_id,))
            conn.commit()
            conn.close()
            st.success("Service deleted.")

@st.dialog("📦 Manage Inventory", width="large")
def inventory_manager_dialog():
    st.subheader("Add New Inventory Item")
    with st.form("inventory_form", clear_on_submit=True):
        i_name = st.text_input("Item Name")
        i_price = st.number_input("Price (₱)", min_value=0.0, step=1.0, value=0.0)
        i_stock = st.number_input("Stock Quantity", min_value=0, step=1, value=0)
        i_barcode = st.text_input("Barcode (Optional)")
        submitted = st.form_submit_button("Add Inventory Item")
        if submitted and i_name:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (%s, 'Inventory', %s, %s, %s)", 
                           (i_name, i_price, i_stock, i_barcode if i_barcode else None))
            conn.commit()
            conn.close()
            st.success("Inventory item added to Supabase!")

    st.divider()
    st.subheader("Edit / Delete Inventory")
    conn = get_db_connection()
    df_inv = pd.read_sql("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory'", conn)
    conn.close()
    
    if not df_inv.empty:
        st.dataframe(df_inv, use_container_width=True, hide_index=True)
        
        edit_inv_id = st.selectbox("Select Item ID to Edit", options=[0] + list(df_inv["id"]), key="edit_inv_select")
        if edit_inv_id != 0:
            selected_inv_row = df_inv[df_inv["id"] == edit_inv_id].iloc[0]
            with st.form("edit_inv_form"):
                ei_name = st.text_input("Edit Item Name", value=selected_inv_row["name"])
                ei_price = st.number_input("Edit Price (₱)", value=float(selected_inv_row["price"]), min_value=0.0, step=1.0)
                ei_stock = st.number_input("Edit Stock", value=int(selected_inv_row["stock"]), min_value=0, step=1)
                current_bc = selected_inv_row["barcode"]
                ei_barcode = st.text_input("Edit Barcode", value=str(current_bc) if pd.notna(current_bc) else "")
                update_inv_sub = st.form_submit_button("💾 Update Inventory Item")
                if update_inv_sub:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE items SET name=%s, price=%s, stock=%s, barcode=%s WHERE id=%s", 
                                   (ei_name, ei_price, ei_stock, ei_barcode if ei_barcode else None, edit_inv_id))
                    conn.commit()
                    conn.close()
                    st.success("Inventory item updated successfully!")

        st.divider()
        del_inv_id = st.selectbox("Select Item ID to Delete", options=[0] + list(df_inv["id"]), key="del_inv_select")
        if del_inv_id != 0 and st.button("🗑️ Delete Selected Item", key="btn_del_inv"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items WHERE id=%s", (del_inv_id,))
            conn.commit()
            conn.close()
            st.success("Item deleted.")

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

@st.dialog("🧾 Receipt Preview & Print", width="medium")
def receipt_preview_dialog(receipt_text):
    html_receipt = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Courier New', Courier, monospace;
                background-color: #ffffff;
                color: #000000;
                margin: 0;
                padding: 10px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .receipt-box {{
                background: #ffffff;
                padding: 10px;
                width: 100%;
                max-width: 320px;
                white-space: pre-wrap;
                font-size: 13px;
                line-height: 1.2;
            }}
            .print-btn {{
                display: block;
                width: 100%;
                max-width: 320px;
                padding: 12px;
                background-color: #ff4b4b;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 15px;
                text-align: center;
            }}
            .print-btn:hover {{
                background-color: #e03e3e;
            }}
            @media print {{
                body * {{
                    visibility: hidden;
                }}
                .receipt-box, .receipt-box * {{
                    visibility: visible;
                }}
                .receipt-box {{
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 100%;
                    border: none;
                    padding: 0;
                }}
                .print-btn {{
                    display: none;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="receipt-box">{receipt_text}</div>
        <button class="print-btn" onclick="window.print()">🖨️ Print to Any Printer</button>
    </body>
    </html>
    """
    components.html(html_receipt, height=450, scrolling=True)
    
    st.download_button(
        "📥 Download Receipt Text File", 
        data=receipt_text, 
        file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 
        mime="text/plain"
    )

# ---------------------------------------------------------
# MAIN HEADER BAR
# ---------------------------------------------------------
header_col1, header_col2, header_col3 = st.columns([0.6, 2.4, 2])

with header_col1:
    try:
        st.image("RTECH Logo.png", width=65)
    except Exception:
        st.markdown("### 💻")

with header_col2:
    st.markdown(f"## {settings['store_name']}")
    st.caption(f"TIN: {settings['tin_number']} | Services Tax: {settings['tax_rate_services']}% | Inventory Tax: {settings['tax_rate_inventory']}%")

with header_col3:
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("⚙️ Settings"):
            tax_settings_dialog()
    with b2:
        if st.button("🖨️ Services"):
            services_manager_dialog()
    with b3:
        if st.button("📦 Inventory"):
            inventory_manager_dialog()

st.divider()

# ---------------------------------------------------------
# CORE APP LAYOUT (SPLIT SCREEN: CATALOG & CART)
# ---------------------------------------------------------
left_col, right_col = st.columns([1.3, 1])

with left_col:
    with st.form("barcode_form", clear_on_submit=True):
        b_col1, b_col2 = st.columns([4, 1])
        with b_col1:
            scanned_code = st.text_input("Barcode Scanner / Search", placeholder="Scan barcode or type item code...", key="scan_input")
        with b_col2:
            st.write("")
            submitted_scan = st.form_submit_button("Scan / Add")

        if submitted_scan and scanned_code:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, name, price, stock, category FROM items WHERE barcode = %s", (scanned_code,))
            db_item = cursor.fetchone()
            
            if not db_item:
                cursor.execute("SELECT id, name, price, stock, category FROM items WHERE name ILIKE %s", (scanned_code,))
                db_item = cursor.fetchone()
                
            if not db_item:
                cursor.execute("SELECT id, name, price, stock, category FROM items WHERE name ILIKE %s", (f"%{scanned_code}%",))
                db_item = cursor.fetchone()
                
            conn.close()

            if db_item:
                item_id, name, price, stock, cat = db_item
                if cat == "Inventory" and stock == 0:
                    st.error(f"Item '{name}' is out of stock!")
                else:
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

    tab_serv, tab_inv, tab_sales = st.tabs(["🖨️ Services", "📦 Inventory", "📊 Daily Sales"])

    with tab_serv:
        st.subheader("Available Services")
        conn = get_db_connection()
        df_services = pd.read_sql("SELECT id, name, price FROM items WHERE category='Services'", conn)
        conn.close()

        if df_services.empty:
            st.info("No services available.")
        else:
            for _, row in df_services.iterrows():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.write(f"**{row['name']}**")
                with c2:
                    st.write(f"₱{row['price']:,.2f}")
                with c3:
                    if st.button("➕ Add", key=f"srv_btn_{row['id']}"):
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
        conn = get_db_connection()
        df_inventory = pd.read_sql("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory'", conn)
        conn.close()

        if df_inventory.empty:
            st.info("No inventory items available.")
        else:
            for _, row in df_inventory.iterrows():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                with c1:
                    st.write(f"**{row['name']}**")
                with c2:
                    st.write(f"Stock: {row['stock'] if row['stock'] != -1 else 'Unli'}")
                with c3:
                    st.write(f"₱{row['price']:,.2f}")
                with c4:
                    if st.button("➕ Add", key=f"inv_btn_{row['id']}"):
                        if row['stock'] == 0:
                            st.error("Out of stock!")
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
        st.subheader("Daily Sales History & Management")
        
        f_col1, f_col2 = st.columns([1, 2])
        with f_col1:
            enable_date_filter = st.checkbox("Filter by Date")
        
        selected_filter_date = None
        if enable_date_filter:
            with f_col2:
                selected_filter_date = st.date_input("Select Sales Date", value=datetime.today())

        conn = get_db_connection()
        if enable_date_filter and selected_filter_date:
            date_str = selected_filter_date.strftime("%Y-%m-%d")
            query = "SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount FROM sales WHERE date_time LIKE %s ORDER BY id DESC"
            df_sales = pd.read_sql(query, conn, params=(f"{date_str}%",))
        else:
            query = "SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount FROM sales ORDER BY id DESC"
            df_sales = pd.read_sql(query, conn)
        conn.close()

        if df_sales.empty:
            st.info("No sales records found.")
        else:
            st.dataframe(df_sales, use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("Edit or Delete Sale Record")
            
            sale_ids = list(df_sales["id"])
            selected_sale_id = st.selectbox("Select Sale ID to Manage", options=[0] + sale_ids, key="manage_sale_select")
            
            if selected_sale_id != 0:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT date_time, subtotal, total, cash, change_amount FROM sales WHERE id=%s", (selected_sale_id,))
                sale_data = cursor.fetchone()
                
                df_details = pd.read_sql("SELECT item_name, price, quantity, subtotal FROM sales_details WHERE sale_id=%s", conn, params=(selected_sale_id,))
                conn.close()
                
                if sale_data:
                    curr_date_time, curr_subtotal, curr_total, curr_cash, curr_change = sale_data
                    
                    st.write(f"**Items inside Sale #{selected_sale_id}:**")
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    
                    with st.form(f"edit_sale_form_{selected_sale_id}"):
                        st.write(f"Editing Details for Sale ID: **#{selected_sale_id}**")
                        e_datetime = st.text_input("Date & Time (YYYY-MM-DD HH:MM:SS)", value=curr_date_time)
                        e_total = st.number_input("Total Amount (₱)", value=float(curr_total), min_value=0.0, step=1.0)
                        e_cash = st.number_input("Cash Tendered (₱)", value=float(curr_cash), min_value=0.0, step=1.0)
                        
                        e_change = e_cash - e_total
                        st.info(f"Updated Change Calculation: ₱{e_change:,.2f}")
                        
                        update_sale_btn = st.form_submit_button("💾 Save Changes")
                        if update_sale_btn:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE sales 
                                SET date_time=%s, total=%s, cash=%s, change_amount=%s 
                                WHERE id=%s
                            ''', (e_datetime, e_total, e_cash, e_change, selected_sale_id))
                            conn.commit()
                            conn.close()
                            st.success(f"Sale #{selected_sale_id} updated successfully!")
                            st.rerun()

                    if st.button(f"🗑️ Delete Sale #{selected_sale_id}", type="secondary", key=f"del_sale_btn_{selected_sale_id}"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM sales_details WHERE sale_id=%s", (selected_sale_id,))
                        cursor.execute("DELETE FROM sales WHERE id=%s", (selected_sale_id,))
                        conn.commit()
                        conn.close()
                        st.success(f"Sale #{selected_sale_id} has been deleted.")
                        st.rerun()

with right_col:
    st.markdown("### 🛒 Current Order")
    
    if st.button("Clear Cart"):
        st.session_state.cart = []
        st.rerun()

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
                    disc_symbol = '%' if item['discount_type'] == 'percentage' else '₱'
                    st.caption(f"Disc: {item['discount_value']}{disc_symbol} (-₱{disc_amt:,.2f})")
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (date_time_str, subtotal, non_vat_sales, total_tax, total_due, cash_tendered, change_amount))
                
                sale_id = cursor.fetchone()[0]

                for item in st.session_state.cart:
                    cursor.execute('''
                        INSERT INTO sales_details (sale_id, item_name, price, quantity, subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (sale_id, item['name'], item['price'], item['qty'], item['subtotal']))

                    if item['category'] == 'Inventory':
                        cursor.execute('''
                            UPDATE items SET stock = stock - %s WHERE id = %s AND stock != -1
                        ''', (item['qty'], item['id']))

                conn.commit()
                conn.close()

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
                st.success(f"Sale completed successfully! Saved to Supabase. Change: ₱ {change_amount:,.2f}")
                receipt_preview_dialog(receipt_text)
