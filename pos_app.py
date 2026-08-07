import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
import csv

# Pillow library para sa pag-load at pag-edit ng logo
try:
    from PIL import Image, ImageTk, ImageDraw, ImageChops
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

class RTechComputerCenterPOS:
    def __init__(self, root):
        self.root = root
        self.root.geometry("1280x740")
        self.root.minsize(1100, 680)

        # Default Settings (Services: 4%, Inventory: 5%)
        self.store_name = "R-TECH COMPUTER CENTER"
        self.tin_number = "123-456-789-00000"
        self.tax_rate_services = 4.0  # 4% para sa Services
        self.tax_rate_inventory = 5.0  # 5% para sa Inventory

        # Setup Database & Load Settings
        self.init_db()
        self.load_settings_from_db()

        self.root.title(f"{self.store_name} POS SYSTEM")

        # Theme Configuration
        self.style = ttk.Style()
        if os.name == 'nt':
            self.style.theme_use('clam')
         
        # Configure Treeview Colors and Fonts
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.style.configure("Treeview", font=("Segoe UI", 10), rowheight=25)
        self.style.map('Treeview', background=[('selected', '#0284c7')], foreground=[('selected', 'white')])

        # Cart data
        self.cart = []

        # Load Logo Image
        self.logo_img = None
        self.load_logo()

        # Build GUI
        self.create_layout()
        self.load_items()
        self.load_sales_data()

        # Auto Focus sa Barcode Scanner pagkabukas
        self.root.after(500, lambda: self.entry_barcode.focus_set())

    def load_logo(self):
        """Loads, resizes, and adds a smooth circular white background to the R-TECH Logo"""
        possible_logos = ["RTECH Logo.jpg", "RTECH Logo.png", "logo.jpg", "logo.png"]
        logo_filename = None
         
        for alt in possible_logos:
            if os.path.exists(alt):
                logo_filename = alt
                break

        if logo_filename and HAS_PILLOW:
            try:
                canvas_size = (52, 52)
                logo_size = (42, 42)

                canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(canvas)
                draw.ellipse((0, 0, canvas_size[0] - 1, canvas_size[1] - 1), fill="white")

                logo = Image.open(logo_filename).convert("RGBA")
                logo = logo.resize(logo_size, Image.Resampling.LANCZOS)

                circle_mask = Image.new("L", logo_size, 0)
                ImageDraw.Draw(circle_mask).ellipse((0, 0, logo_size[0], logo_size[1]), fill=255)

                alpha = ImageChops.multiply(logo.split()[3], circle_mask)
                offset = ((canvas_size[0] - logo_size[0]) // 2, (canvas_size[1] - logo_size[1]) // 2)
                canvas.paste(logo, offset, mask=alpha)

                self.logo_img = ImageTk.PhotoImage(canvas)
            except Exception as e:
                print(f"Error sa pag-load ng logo: {e}")

    # ---------------------------------------------------------
    # DATABASE MANAGEMENT & SETTINGS
    # ---------------------------------------------------------
    def init_db(self):
        self.conn = sqlite3.connect("pos_rtech_computer.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER DEFAULT -1,
                barcode TEXT UNIQUE
            )
        ''')

        try:
            self.cursor.execute("ALTER TABLE items ADD COLUMN barcode TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

        self.cursor.execute('''
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

        try:
            self.cursor.execute("ALTER TABLE sales ADD COLUMN subtotal REAL DEFAULT 0")
            self.cursor.execute("ALTER TABLE sales ADD COLUMN non_vat_sales REAL DEFAULT 0")
            self.cursor.execute("ALTER TABLE sales ADD COLUMN vat_amount REAL DEFAULT 0")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
         
        self.cursor.execute('''
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

        # TABLE PARA SA TAX AT STORE SETTINGS
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        self.cursor.execute("SELECT COUNT(*) FROM items")
        if self.cursor.fetchone()[0] == 0:
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
            self.cursor.executemany("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, ?, ?, ?, ?)", default_items)
            self.conn.commit()

    def load_settings_from_db(self):
        try:
            self.cursor.execute("SELECT key, value FROM settings")
            rows = dict(self.cursor.fetchall())

            if 'store_name' in rows:
                self.store_name = rows['store_name']
            if 'tin_number' in rows:
                self.tin_number = rows['tin_number']
            if 'tax_rate_services' in rows:
                self.tax_rate_services = float(rows['tax_rate_services'])
            if 'tax_rate_inventory' in rows:
                self.tax_rate_inventory = float(rows['tax_rate_inventory'])
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_setting(self, key, value):
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    # ---------------------------------------------------------
    # TAX & STORE SETTINGS WINDOW
    # ---------------------------------------------------------
    def open_tax_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Tax & Store Settings")
        settings_win.geometry("420x380")
        settings_win.grab_set()
        settings_win.configure(bg="#f1f5f9")

        tk.Label(settings_win, text="⚙️ Store & Tax Settings", font=("Segoe UI", 13, "bold"), bg="#f1f5f9", fg="#0284c7").pack(pady=10)

        form_frame = tk.Frame(settings_win, bg="white", padx=15, pady=15, bd=1, relief="solid")
        form_frame.pack(fill="both", expand=True, padx=15, pady=5)

        tk.Label(form_frame, text="Store Name:", font=("Segoe UI", 9, "bold"), bg="white", fg="#1e293b").pack(anchor="w")
        entry_store = tk.Entry(form_frame, font=("Segoe UI", 10), width=30)
        entry_store.pack(fill="x", pady=(2, 8))
        entry_store.insert(0, self.store_name)

        tk.Label(form_frame, text="TIN Number:", font=("Segoe UI", 9, "bold"), bg="white", fg="#1e293b").pack(anchor="w")
        entry_tin = tk.Entry(form_frame, font=("Segoe UI", 10), width=30)
        entry_tin.pack(fill="x", pady=(2, 8))
        entry_tin.insert(0, self.tin_number)

        tk.Label(form_frame, text="Services Tax Rate (%):", font=("Segoe UI", 9, "bold"), bg="white", fg="#1e293b").pack(anchor="w")
        entry_tax_serv = tk.Entry(form_frame, font=("Segoe UI", 10), width=30)
        entry_tax_serv.pack(fill="x", pady=(2, 8))
        entry_tax_serv.insert(0, str(self.tax_rate_services))

        tk.Label(form_frame, text="Inventory Tax Rate (%):", font=("Segoe UI", 9, "bold"), bg="white", fg="#1e293b").pack(anchor="w")
        entry_tax_inv = tk.Entry(form_frame, font=("Segoe UI", 10), width=30)
        entry_tax_inv.pack(fill="x", pady=(2, 12))
        entry_tax_inv.insert(0, str(self.tax_rate_inventory))

        def save_changes():
            try:
                s_name = entry_store.get().strip()
                t_num = entry_tin.get().strip()
                t_serv = float(entry_tax_serv.get().strip())
                t_inv = float(entry_tax_inv.get().strip())

                if not s_name or not t_num:
                    messagebox.showwarning("Warning", "Lahat ng fields ay kailangang punan.", parent=settings_win)
                    return

                self.store_name = s_name
                self.tin_number = t_num
                self.tax_rate_services = t_serv
                self.tax_rate_inventory = t_inv

                self.save_setting('store_name', s_name)
                self.save_setting('tin_number', t_num)
                self.save_setting('tax_rate_services', t_serv)
                self.save_setting('tax_rate_inventory', t_inv)

                # Update UI Headers
                self.root.title(f"{self.store_name} POS SYSTEM")
                self.lbl_title_store.config(text=self.store_name)
                self.lbl_subtitle_tax.config(text=f"POS SYSTEM (TIN: {self.tin_number} | Serv: {self.tax_rate_services}% | Inv: {self.tax_rate_inventory}%)")

                messagebox.showinfo("Success", "Matagumpay na nai-save ang bagong settings!", parent=settings_win)
                settings_win.destroy()
                self.update_cart_display()
            except ValueError:
                messagebox.showerror("Error", "Mali ang format ng Tax Rate. Maglagay ng tamang numero.", parent=settings_win)

        btn_save = tk.Button(form_frame, text="💾 I-save ang Settings", font=("Segoe UI", 10, "bold"), bg="#22c55e", fg="white", relief="flat", cursor="hand2", command=save_changes)
        btn_save.pack(fill="x", pady=(5, 0))

    # ---------------------------------------------------------
    # MANAGE SERVICES WINDOW
    # ---------------------------------------------------------
    def open_services_manager(self):
        serv_win = tk.Toplevel(self.root)
        serv_win.title("Manage Services")
        serv_win.geometry("820x520")
        serv_win.grab_set()
        serv_win.configure(bg="#f1f5f9")

        tk.Label(serv_win, text="🖨️ Manage Services", font=("Segoe UI", 13, "bold"), bg="#f1f5f9", fg="#0284c7").pack(pady=10)

        main_container = tk.Frame(serv_win, bg="#f1f5f9")
        main_container.pack(fill="both", expand=True, padx=15, pady=5)

        form_frame = tk.Frame(main_container, bg="white", padx=12, pady=12, bd=1, relief="solid")
        form_frame.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(form_frame, text="Detalye ng Serbisyo", font=("Segoe UI", 10, "bold"), bg="white", fg="#1e293b").pack(anchor="w", pady=(0, 5))

        tk.Label(form_frame, text="Pangalan ng Serbisyo:", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_name = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_name.pack(fill="x", pady=(2, 8))

        tk.Label(form_frame, text="Presyo (₱):", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_price = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_price.pack(fill="x", pady=(2, 12))

        selected_item_id = tk.IntVar(value=0)

        def clear_form():
            selected_item_id.set(0)
            e_name.delete(0, tk.END)
            e_price.delete(0, tk.END)

        def refresh_serv_tree():
            for r in tree_all.get_children():
                tree_all.delete(r)
            self.cursor.execute("SELECT id, name, price FROM items WHERE category='Services' ORDER BY id DESC")
            for row in self.cursor.fetchall():
                tree_all.insert("", "end", values=(row[0], row[1], f"₱ {row[2]:,.2f}"))

        def add_item_db():
            name = e_name.get().strip()
            price_str = e_price.get().strip()

            if not name or not price_str:
                messagebox.showwarning("Warning", "Punan ang Pangalan at Presyo.", parent=serv_win)
                return

            try:
                price = float(price_str)
            except ValueError:
                messagebox.showerror("Error", "Dapat numero ang Presyo.", parent=serv_win)
                return

            try:
                self.cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, 'Services', ?, -1, NULL)",
                                    (name, price))
                self.conn.commit()
                messagebox.showinfo("Success", "Matagumpay na naidagdag ang serbisyo!", parent=serv_win)
                clear_form()
                refresh_serv_tree()
                self.load_items()
            except Exception as e:
                messagebox.showerror("Error", f"Hindi naidagdag ang serbisyo: {e}", parent=serv_win)

        def update_item_db():
            item_id = selected_item_id.get()
            if item_id == 0:
                messagebox.showwarning("Warning", "Pumili muna ng serbisyo sa listahan na i-eedit.", parent=serv_win)
                return

            name = e_name.get().strip()
            price_str = e_price.get().strip()

            if not name or not price_str:
                messagebox.showwarning("Warning", "Punan ang Pangalan at Presyo.", parent=serv_win)
                return

            try:
                price = float(price_str)
            except ValueError:
                messagebox.showerror("Error", "Dapat numero ang Presyo.", parent=serv_win)
                return

            try:
                self.cursor.execute("UPDATE items SET name=?, price=? WHERE id=?",
                                    (name, price, item_id))
                self.conn.commit()
                messagebox.showinfo("Success", "Matagumpay na na-update ang serbisyo!", parent=serv_win)
                clear_form()
                refresh_serv_tree()
                self.load_items()
            except Exception as e:
                messagebox.showerror("Error", f"Hindi na-update ang serbisyo: {e}", parent=serv_win)

        def delete_item_db():
            item_id = selected_item_id.get()
            if item_id == 0:
                messagebox.showwarning("Warning", "Pumili muna ng serbisyo sa listahan na buburahin.", parent=serv_win)
                return

            if messagebox.askyesno("Kumpirmahin", "Sigurado ka bang gusto mong tanggalin ang serbisyong ito?", parent=serv_win):
                try:
                    self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
                    self.conn.commit()
                    messagebox.showinfo("Success", "Matagumpay na natanggal ang serbisyo.", parent=serv_win)
                    clear_form()
                    refresh_serv_tree()
                    self.load_items()
                except Exception as e:
                    messagebox.showerror("Error", f"Hindi ma-delete ang serbisyo: {e}", parent=serv_win)

        def export_services_to_excel():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files (Excel compatible)", "*.csv"), ("All Files", "*.*")],
                title="I-save ang Services bilang Excel"
            )
            if file_path:
                try:
                    self.cursor.execute("SELECT id, name, price FROM items WHERE category='Services' ORDER BY id ASC")
                    rows = self.cursor.fetchall()
                    with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Service ID", "Service Name", "Price"])
                        for row in rows:
                            writer.writerow(row)
                    messagebox.showinfo("Success", f"Matagumpay na na-export ang services sa:\n{file_path}", parent=serv_win)
                except Exception as e:
                    messagebox.showerror("Export Error", f"Nagka-error sa pag-export: {e}", parent=serv_win)

        btn_add = tk.Button(form_frame, text="➕ Magdagdag", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="white", relief="flat", cursor="hand2", command=add_item_db)
        btn_add.pack(fill="x", pady=2)

        btn_upd = tk.Button(form_frame, text="✏️ I-update", font=("Segoe UI", 9, "bold"), bg="#ca8a04", fg="white", relief="flat", cursor="hand2", command=update_item_db)
        btn_upd.pack(fill="x", pady=2)

        btn_del = tk.Button(form_frame, text="🗑️ Tanggalin", font=("Segoe UI", 9, "bold"), bg="#ef4444", fg="white", relief="flat", cursor="hand2", command=delete_item_db)
        btn_del.pack(fill="x", pady=2)

        btn_clr = tk.Button(form_frame, text="🧹 I-clear ang Form", font=("Segoe UI", 9), bg="#64748b", fg="white", relief="flat", cursor="hand2", command=clear_form)
        btn_clr.pack(fill="x", pady=(10, 2))

        right_outer_frame = tk.Frame(main_container, bg="white", padx=5, pady=5, bd=1, relief="solid")
        right_outer_frame.pack(side="right", fill="both", expand=True)

        right_top_bar = tk.Frame(right_outer_frame, bg="white")
        right_top_bar.pack(fill="x", padx=5, pady=5)

        tk.Label(right_top_bar, text="Listahan ng mga Serbisyo", font=("Segoe UI", 10, "bold"), bg="white", fg="#0284c7").pack(side="left")
        btn_export_serv = tk.Button(right_top_bar, text="📥 I-export sa CSV", font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white", relief="flat", cursor="hand2", padx=10, command=export_services_to_excel)
        btn_export_serv.pack(side="right")

        tree_container = tk.Frame(right_outer_frame, bg="white")
        tree_container.pack(fill="both", expand=True)

        tree_all = ttk.Treeview(tree_container, columns=("ID", "Name", "Price"), show="headings")
        tree_all.heading("ID", text="ID")
        tree_all.heading("Name", text="Service Name")
        tree_all.heading("Price", text="Price")

        tree_all.column("ID", width=50, anchor="center")
        tree_all.column("Name", width=280)
        tree_all.column("Price", width=100, anchor="e")

        sc_serv = ttk.Scrollbar(tree_container, orient="vertical", command=tree_all.yview)
        tree_all.configure(yscrollcommand=sc_serv.set)

        tree_all.pack(side="left", fill="both", expand=True)
        sc_serv.pack(side="right", fill="y")

        def on_select_item(event):
            selected = tree_all.selection()
            if not selected:
                return
            vals = tree_all.item(selected[0], 'values')
            item_id = vals[0]
            selected_item_id.set(int(item_id))

            self.cursor.execute("SELECT name, price FROM items WHERE id=?", (item_id,))
            res = self.cursor.fetchone()
            if res:
                e_name.delete(0, tk.END)
                e_name.insert(0, res[0])
                e_price.delete(0, tk.END)
                e_price.insert(0, str(res[1]))

        tree_all.bind("<<TreeviewSelect>>", on_select_item)
        refresh_serv_tree()

    # ---------------------------------------------------------
    # MANAGE INVENTORY WINDOW
    # ---------------------------------------------------------
    def open_inventory_manager(self):
        inv_win = tk.Toplevel(self.root)
        inv_win.title("Manage Inventory")
        inv_win.geometry("920x580")
        inv_win.grab_set()
        inv_win.configure(bg="#f1f5f9")

        tk.Label(inv_win, text="📦 Manage Inventory", font=("Segoe UI", 13, "bold"), bg="#f1f5f9", fg="#0284c7").pack(pady=10)

        main_container = tk.Frame(inv_win, bg="#f1f5f9")
        main_container.pack(fill="both", expand=True, padx=15, pady=5)

        form_frame = tk.Frame(main_container, bg="white", padx=12, pady=12, bd=1, relief="solid")
        form_frame.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(form_frame, text="Detalye ng Inventory Item", font=("Segoe UI", 10, "bold"), bg="white", fg="#1e293b").pack(anchor="w", pady=(0, 5))

        tk.Label(form_frame, text="Pangalan:", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_name = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_name.pack(fill="x", pady=(2, 8))

        tk.Label(form_frame, text="Presyo (₱):", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_price = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_price.pack(fill="x", pady=(2, 8))

        tk.Label(form_frame, text="Stock:", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_stock = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_stock.pack(fill="x", pady=(2, 8))
        e_stock.insert(0, "0")

        tk.Label(form_frame, text="Barcode (Opsiyonal):", font=("Segoe UI", 9), bg="white").pack(anchor="w")
        e_barcode = tk.Entry(form_frame, font=("Segoe UI", 10), width=25)
        e_barcode.pack(fill="x", pady=(2, 12))

        selected_item_id = tk.IntVar(value=0)

        def clear_form():
            selected_item_id.set(0)
            e_name.delete(0, tk.END)
            e_price.delete(0, tk.END)
            e_stock.delete(0, tk.END)
            e_stock.insert(0, "0")
            e_barcode.delete(0, tk.END)

        def refresh_inv_tree():
            for r in tree_all.get_children():
                tree_all.delete(r)
            self.cursor.execute("SELECT id, name, price, stock, barcode FROM items WHERE category='Inventory' ORDER BY id DESC")
            for row in self.cursor.fetchall():
                bc = row[4] if row[4] else "N/A"
                tree_all.insert("", "end", values=(row[0], row[1], f"₱ {row[2]:,.2f}", row[3], bc))

        def add_item_db():
            name = e_name.get().strip()
            price_str = e_price.get().strip()
            stock_str = e_stock.get().strip()
            bc = e_barcode.get().strip() or None

            if not name or not price_str or not stock_str:
                messagebox.showwarning("Warning", "Punan ang Pangalan, Presyo, at Stock.", parent=inv_win)
                return

            try:
                price = float(price_str)
                stock = int(stock_str)
            except ValueError:
                messagebox.showerror("Error", "Dapat numero ang Presyo at Stock.", parent=inv_win)
                return

            try:
                self.cursor.execute("INSERT INTO items (name, category, price, stock, barcode) VALUES (?, 'Inventory', ?, ?, ?)",
                                    (name, price, stock, bc))
                self.conn.commit()
                messagebox.showinfo("Success", "Matagumpay na naidagdag ang item!", parent=inv_win)
                clear_form()
                refresh_inv_tree()
                self.load_items()
            except Exception as e:
                messagebox.showerror("Error", f"Hindi naidagdag ang item: {e}", parent=inv_win)

        def update_item_db():
            item_id = selected_item_id.get()
            if item_id == 0:
                messagebox.showwarning("Warning", "Pumili muna ng item sa listahan na i-eedit.", parent=inv_win)
                return

            name = e_name.get().strip()
            price_str = e_price.get().strip()
            stock_str = e_stock.get().strip()
            bc = e_barcode.get().strip() or None

            if not name or not price_str or not stock_str:
                messagebox.showwarning("Warning", "Punan ang Pangalan, Presyo, at Stock.", parent=inv_win)
                return

            try:
                price = float(price_str)
                stock = int(stock_str)
            except ValueError:
                messagebox.showerror("Error", "Dapat numero ang Presyo at Stock.", parent=inv_win)
                return

            try:
                self.cursor.execute("UPDATE items SET name=?, price=?, stock=?, barcode=? WHERE id=?",
                                    (name, price, stock, bc, item_id))
                self.conn.commit()
                messagebox.showinfo("Success", "Matagumpay na na-update ang item!", parent=inv_win)
                clear_form()
                refresh_inv_tree()
                self.load_items()
            except Exception as e:
                messagebox.showerror("Error", f"Hindi na-update ang item: {e}", parent=inv_win)

        def delete_item_db():
            item_id = selected_item_id.get()
            if item_id == 0:
                messagebox.showwarning("Warning", "Pumili muna ng item sa listahan na buburahin.", parent=inv_win)
                return

            if messagebox.askyesno("Kumpirmahin", "Sigurado ka bang gusto mong tanggalin ang item na ito?", parent=inv_win):
                try:
                    self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
                    self.conn.commit()
                    messagebox.showinfo("Success", "Matagumpay na natanggal ang item.", parent=inv_win)
                    clear_form()
                    refresh_inv_tree()
                    self.load_items()
                except Exception as e:
                    messagebox.showerror("Error", f"Hindi ma-delete ang item: {e}", parent=inv_win)

        def export_inventory_to_excel():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files (Excel compatible)", "*.csv"), ("All Files", "*.*")],
                title="I-save ang Inventory bilang Excel"
            )
            if file_path:
                try:
                    self.cursor.execute("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory' ORDER BY id ASC")
                    rows = self.cursor.fetchall()
                    with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Item ID", "Barcode", "Item Name", "Price", "Stock"])
                        for row in rows:
                            writer.writerow(row)
                    messagebox.showinfo("Success", f"Matagumpay na na-export ang inventory sa:\n{file_path}", parent=inv_win)
                except Exception as e:
                    messagebox.showerror("Export Error", f"Nagka-error sa pag-export: {e}", parent=inv_win)

        btn_add = tk.Button(form_frame, text="➕ Magdagdag", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="white", relief="flat", cursor="hand2", command=add_item_db)
        btn_add.pack(fill="x", pady=2)

        btn_upd = tk.Button(form_frame, text="✏️ I-update", font=("Segoe UI", 9, "bold"), bg="#ca8a04", fg="white", relief="flat", cursor="hand2", command=update_item_db)
        btn_upd.pack(fill="x", pady=2)

        btn_del = tk.Button(form_frame, text="🗑️ Tanggalin", font=("Segoe UI", 9, "bold"), bg="#ef4444", fg="white", relief="flat", cursor="hand2", command=delete_item_db)
        btn_del.pack(fill="x", pady=2)

        btn_clr = tk.Button(form_frame, text="🧹 I-clear ang Form", font=("Segoe UI", 9), bg="#64748b", fg="white", relief="flat", cursor="hand2", command=clear_form)
        btn_clr.pack(fill="x", pady=(10, 2))

        right_outer_frame = tk.Frame(main_container, bg="white", padx=5, pady=5, bd=1, relief="solid")
        right_outer_frame.pack(side="right", fill="both", expand=True)

        right_top_bar = tk.Frame(right_outer_frame, bg="white")
        right_top_bar.pack(fill="x", padx=5, pady=5)

        tk.Label(right_top_bar, text="Listahan ng Inventory", font=("Segoe UI", 10, "bold"), bg="white", fg="#0284c7").pack(side="left")
        btn_export_inv = tk.Button(right_top_bar, text="📥 I-export sa CSV", font=("Segoe UI", 9, "bold"), bg="#16a34a", fg="white", relief="flat", cursor="hand2", padx=10, command=export_inventory_to_excel)
        btn_export_inv.pack(side="right")

        tree_container = tk.Frame(right_outer_frame, bg="white")
        tree_container.pack(fill="both", expand=True)

        tree_all = ttk.Treeview(tree_container, columns=("ID", "Name", "Price", "Stock", "Barcode"), show="headings")
        tree_all.heading("ID", text="ID")
        tree_all.heading("Name", text="Item Name")
        tree_all.heading("Price", text="Price")
        tree_all.heading("Stock", text="Stock")
        tree_all.heading("Barcode", text="Barcode")

        tree_all.column("ID", width=40, anchor="center")
        tree_all.column("Name", width=210)
        tree_all.column("Price", width=80, anchor="e")
        tree_all.column("Stock", width=60, anchor="center")
        tree_all.column("Barcode", width=100, anchor="center")

        sc_all = ttk.Scrollbar(tree_container, orient="vertical", command=tree_all.yview)
        tree_all.configure(yscrollcommand=sc_all.set)

        tree_all.pack(side="left", fill="both", expand=True)
        sc_all.pack(side="right", fill="y")

        def on_select_item(event):
            selected = tree_all.selection()
            if not selected:
                return
            vals = tree_all.item(selected[0], 'values')
            item_id = vals[0]
            selected_item_id.set(int(item_id))

            self.cursor.execute("SELECT name, price, stock, barcode FROM items WHERE id=?", (item_id,))
            res = self.cursor.fetchone()
            if res:
                e_name.delete(0, tk.END)
                e_name.insert(0, res[0])
                e_price.delete(0, tk.END)
                e_price.insert(0, str(res[1]))
                e_stock.delete(0, tk.END)
                e_stock.insert(0, str(res[2]))
                e_barcode.delete(0, tk.END)
                if res[3]:
                    e_barcode.insert(0, res[3])

        tree_all.bind("<<TreeviewSelect>>", on_select_item)
        refresh_inv_tree()

    # ---------------------------------------------------------
    # LAYOUT & GUI
    # ---------------------------------------------------------
    def create_layout(self):
        header = tk.Frame(self.root, bg="#0b132b", height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        brand_frame = tk.Frame(header, bg="#0b132b")
        brand_frame.pack(side="left", padx=20, pady=5)

        if self.logo_img:
            logo_lbl = tk.Label(brand_frame, image=self.logo_img, bg="#0b132b")
            logo_lbl.pack(side="left", padx=(0, 15))

        title_box = tk.Frame(brand_frame, bg="#0b132b")
        title_box.pack(side="left")

        self.lbl_title_store = tk.Label(title_box, text=self.store_name, font=("Segoe UI", 16, "bold"), fg="#38bdf8", bg="#0b132b")
        self.lbl_title_store.pack(anchor="w")

        self.lbl_subtitle_tax = tk.Label(title_box, text=f"POS SYSTEM (TIN: {self.tin_number} | Serv: {self.tax_rate_services}% | Inv: {self.tax_rate_inventory}%)", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#0b132b")
        self.lbl_subtitle_tax.pack(anchor="w")

        nav_btns = tk.Frame(header, bg="#0b132b")
        nav_btns.pack(side="right", padx=20, pady=15)

        tax_cfg_btn = tk.Button(nav_btns, text="⚙️ Tax & Store Settings", font=("Segoe UI", 10, "bold"), 
                                bg="#0284c7", fg="white", relief="flat", cursor="hand2",
                                padx=12, command=self.open_tax_settings)
        tax_cfg_btn.pack(side="left", padx=(0, 10))

        serv_manage_btn = tk.Button(nav_btns, text="🖨️ Manage Services", font=("Segoe UI", 10, "bold"), 
                                    bg="#0284c7", fg="white", relief="flat", cursor="hand2",
                                    padx=12, command=self.open_services_manager)
        serv_manage_btn.pack(side="left", padx=(0, 10))

        manage_btn = tk.Button(nav_btns, text="📦 Manage Inventory", font=("Segoe UI", 10, "bold"), 
                               bg="#1d4ed8", fg="white", relief="flat", cursor="hand2",
                               padx=12, command=self.open_inventory_manager)
        manage_btn.pack(side="left")

        self.main_frame = tk.Frame(self.root, bg="#f1f5f9")
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        left_panel = tk.Frame(self.main_frame, bg="#f1f5f9")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 15))

        # BARCODE SCANNER SECTION
        barcode_frame = tk.Frame(left_panel, bg="white", bd=1, relief="solid", padx=10, pady=8)
        barcode_frame.pack(fill="x", pady=(0, 10))

        tk.Label(barcode_frame, text="📷 BARCODE SCANNER / QUICK SEARCH:", font=("Segoe UI", 10, "bold"), bg="white", fg="#0284c7").pack(side="left", padx=(0, 10))
         
        self.entry_barcode = tk.Entry(barcode_frame, font=("Segoe UI", 11, "bold"), bd=1, relief="solid")
        self.entry_barcode.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_barcode.bind("<Return>", self.on_barcode_scanned)

        btn_scan = tk.Button(barcode_frame, text="Add / Scan", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="white", relief="flat", cursor="hand2", padx=15, command=self.on_barcode_scanned)
        btn_scan.pack(side="right")

        # Tabs
        self.notebook = ttk.Notebook(left_panel)
        self.notebook.pack(fill="both", expand=True)

        self.services_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.services_frame, text="    🖨️ Services    ")

        self.inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inventory_frame, text="    📦 Inventory    ")

        self.sales_tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sales_tab_frame, text="    📊 Daily Sales    ")

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # Services View
        self.tree_services = ttk.Treeview(self.services_frame, columns=("ID", "Name", "Price"), show="headings", selectmode="browse")
        self.tree_services.heading("ID", text="ID")
        self.tree_services.heading("Name", text="Service Name")
        self.tree_services.heading("Price", text="Price (₱)")
        self.tree_services.column("ID", width=50, anchor="center")
        self.tree_services.column("Name", width=350)
        self.tree_services.column("Price", width=120, anchor="e")
         
        sc_service = ttk.Scrollbar(self.services_frame, orient="vertical", command=self.tree_services.yview)
        self.tree_services.configure(yscrollcommand=sc_service.set)
         
        self.tree_services.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        sc_service.pack(side="right", fill="y", pady=5, padx=(0,5))
        self.tree_services.bind("<Double-1>", lambda e: self.add_selected_to_cart(self.tree_services, "Services"))

        # Inventory View
        self.tree_inventory = ttk.Treeview(self.inventory_frame, columns=("ID", "Barcode", "Name", "Price", "Stock"), show="headings", selectmode="browse")
        self.tree_inventory.heading("ID", text="ID")
        self.tree_inventory.heading("Barcode", text="Barcode")
        self.tree_inventory.heading("Name", text="Item Name")
        self.tree_inventory.heading("Price", text="Price (₱)")
        self.tree_inventory.heading("Stock", text="Stock")
         
        self.tree_inventory.column("ID", width=40, anchor="center")
        self.tree_inventory.column("Barcode", width=110, anchor="center")
        self.tree_inventory.column("Name", width=250)
        self.tree_inventory.column("Price", width=90, anchor="e")
        self.tree_inventory.column("Stock", width=80, anchor="center")
         
        sc_inv = ttk.Scrollbar(self.inventory_frame, orient="vertical", command=self.tree_inventory.yview)
        self.tree_inventory.configure(yscrollcommand=sc_inv.set)
         
        self.tree_inventory.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)
        sc_inv.pack(side="right", fill="y", pady=5, padx=(0,5))
        self.tree_inventory.bind("<Double-1>", lambda e: self.add_selected_to_cart(self.tree_inventory, "Inventory"))

        # Build Daily Sales Tab
        self.build_sales_tab()

        add_btn = tk.Button(left_panel, text="+ Add Selected to Order (Double Click)", font=("Segoe UI", 11, "bold"), 
                            bg="#0284c7", fg="white", relief="flat", cursor="hand2", pady=8,
                            command=self.add_active_tab_item)
        add_btn.pack(fill="x", pady=(15, 0))

        # RIGHT PANEL: Cart & Checkout
        self.right_panel = tk.Frame(self.main_frame, bg="white", bd=0, relief="flat", width=460)
        self.right_panel.pack(side="right", fill="both")
        self.right_panel.pack_propagate(False)

        cart_header = tk.Frame(self.right_panel, bg="#f8fafc", pady=10, padx=10)
        cart_header.pack(fill="x")
         
        tk.Label(cart_header, text="🛒 Current Order", font=("Segoe UI", 13, "bold"), bg="#f8fafc", fg="#1e293b", anchor="w").pack(side="left")
         
        clear_btn = tk.Button(cart_header, text="Clear All", font=("Segoe UI", 9), bg="#ef4444", fg="white", 
                              relief="flat", cursor="hand2", padx=10, command=self.clear_cart)
        clear_btn.pack(side="right")

        cart_tree_frame = tk.Frame(self.right_panel, bg="white", padx=10, pady=5)
        cart_tree_frame.pack(fill="both", expand=True)

        # In-update ang Cart Treeview para isama ang Discount column
        self.cart_tree = ttk.Treeview(cart_tree_frame, columns=("Name", "Qty", "Price", "Disc", "Subtotal"), show="headings", height=7)
        self.cart_tree.heading("Name", text="Item")
        self.cart_tree.heading("Qty", text="Qty")
        self.cart_tree.heading("Price", text="Price")
        self.cart_tree.heading("Disc", text="Discount")
        self.cart_tree.heading("Subtotal", text="Total")
        
        self.cart_tree.column("Name", width=140)
        self.cart_tree.column("Qty", width=40, anchor="center")
        self.cart_tree.column("Price", width=70, anchor="e")
        self.cart_tree.column("Disc", width=75, anchor="center")
        self.cart_tree.column("Subtotal", width=80, anchor="e")
         
        sc_cart = ttk.Scrollbar(cart_tree_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=sc_cart.set)
         
        self.cart_tree.pack(side="left", fill="both", expand=True)
        sc_cart.pack(side="right", fill="y")
        
        # Double-click para baguhin o maglagay ng discount sa item sa cart
        self.cart_tree.bind("<Double-1>", self.open_edit_discount_window)

        cart_ctrls = tk.Frame(self.right_panel, bg="white", padx=10, pady=2)
        cart_ctrls.pack(fill="x")

        rem_btn = tk.Button(cart_ctrls, text="❌ Remove Selected Item", font=("Segoe UI", 9), bg="#64748b", fg="white", 
                            relief="flat", cursor="hand2", command=self.remove_cart_item)
        rem_btn.pack(side="left", anchor="w")
        
        disc_btn = tk.Button(cart_ctrls, text="🏷️ Edit Discount", font=("Segoe UI", 9), bg="#d97706", fg="white", 
                             relief="flat", cursor="hand2", command=lambda: self.open_edit_discount_window(None))
        disc_btn.pack(side="right", anchor="e")

        # --- CUSTOMER TYPE SELECTION ---
        cust_type_frame = tk.Frame(self.right_panel, bg="white", padx=10, pady=5)
        cust_type_frame.pack(fill="x")
        
        tk.Label(cust_type_frame, text="Customer Type:", font=("Segoe UI", 9, "bold"), bg="white", fg="#1e293b").pack(anchor="w")
        self.customer_type_var = tk.StringVar(value="Regular Customer")
        
        cust_combo = ttk.Combobox(cust_type_frame, textvariable=self.customer_type_var, values=["Regular Customer", "Government Customer"], state="readonly", font=("Segoe UI", 9))
        cust_combo.pack(fill="x", pady=(2, 2))
        cust_combo.bind("<<ComboboxSelected>>", lambda e: self.update_cart_display())

        # PAYMENT BREAKDOWN FRAME
        pay_frame = tk.Frame(self.right_panel, bg="#f8fafc", bd=1, relief="solid", padx=12, pady=8)
        pay_frame.pack(fill="x", padx=10, pady=5)
        pay_frame.columnconfigure(1, weight=1)

        tk.Label(pay_frame, text="Subtotal:", font=("Segoe UI", 9), bg="#f8fafc", fg="#475569").grid(row=0, column=0, sticky="w")
        self.lbl_subtotal = tk.Label(pay_frame, text="₱ 0.00", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b")
        self.lbl_subtotal.grid(row=0, column=1, sticky="e")

        tk.Label(pay_frame, text="Services Tax (4%):", font=("Segoe UI", 9), bg="#f8fafc", fg="#475569").grid(row=1, column=0, sticky="w")
        self.lbl_tax_services = tk.Label(pay_frame, text="₱ 0.00", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#64748b")
        self.lbl_tax_services.grid(row=1, column=1, sticky="e")

        tk.Label(pay_frame, text="Inventory Tax (5%):", font=("Segoe UI", 9), bg="#f8fafc", fg="#475569").grid(row=2, column=0, sticky="w")
        self.lbl_tax_inventory = tk.Label(pay_frame, text="₱ 0.00", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#64748b")
        self.lbl_tax_inventory.grid(row=2, column=1, sticky="e")

        ttk.Separator(pay_frame, orient="horizontal").grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)

        tk.Label(pay_frame, text="TOTAL DUE:", font=("Segoe UI", 11, "bold"), bg="#f8fafc", fg="#1e293b").grid(row=4, column=0, sticky="w")
        self.lbl_total = tk.Label(pay_frame, text="₱ 0.00", font=("Segoe UI", 15, "bold"), fg="#16a34a", bg="#f8fafc")
        self.lbl_total.grid(row=4, column=1, sticky="e")

        tk.Label(pay_frame, text="Cash Tendered (₱):", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b").grid(row=5, column=0, sticky="w", pady=(5,0))
        self.entry_cash = tk.Entry(pay_frame, font=("Segoe UI", 11, "bold"), width=12, justify="right", bd=1, relief="solid")
        self.entry_cash.grid(row=5, column=1, sticky="e", pady=(5,0))
        self.entry_cash.bind("<KeyRelease>", self.calculate_change)

        tk.Label(pay_frame, text="CHANGE:", font=("Segoe UI", 9, "bold"), bg="#f8fafc", fg="#1e293b").grid(row=6, column=0, sticky="w", pady=(5,0))
        self.lbl_change = tk.Label(pay_frame, text="₱ 0.00", font=("Segoe UI", 13, "bold"), fg="#0284c7", bg="#f8fafc")
        self.lbl_change.grid(row=6, column=1, sticky="e", pady=(5,0))

        checkout_btn = tk.Button(self.right_panel, text="✔ COMPLETE SALE / PRINT RECEIPT", font=("Segoe UI", 11, "bold"), 
                                 bg="#22c55e", fg="white", relief="flat", cursor="hand2", pady=8,
                                 command=self.process_checkout)
        checkout_btn.pack(fill="x", padx=10, pady=(5, 10))

    # ---------------------------------------------------------
    # DAILY SALES & EXPORT FUNCTIONALITY
    # ---------------------------------------------------------
    def build_sales_tab(self):
        sales_container = tk.Frame(self.sales_tab_frame, bg="white", padx=10, pady=10)
        sales_container.pack(fill="both", expand=True)

        header_frame = tk.Frame(sales_container, bg="white")
        header_frame.pack(fill="x", pady=(0, 10))

        tk.Label(header_frame, text="📊 Listahan ng Araw-araw na Benta (Daily Sales)", font=("Segoe UI", 11, "bold"), bg="white", fg="#0284c7").pack(side="left")

        action_frame = tk.Frame(sales_container, bg="white")
        action_frame.pack(fill="x", pady=(0, 10))

        tk.Label(action_frame, text="Petsa (YYYY-MM-DD):", font=("Segoe UI", 9, "bold"), bg="white", fg="#334155").pack(side="left", padx=(0, 5))
        
        self.entry_sales_date = tk.Entry(action_frame, font=("Segoe UI", 9), width=12, bd=1, relief="solid")
        self.entry_sales_date.pack(side="left", padx=(0, 5))
        self.entry_sales_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        btn_filter = tk.Button(action_frame, text="🔍 Salain (Filter)", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="white", relief="flat", cursor="hand2", padx=10, command=self.filter_sales_by_date)
        btn_filter.pack(side="left", padx=(0, 5))

        btn_all = tk.Button(action_frame, text="Lahat (Show All)", font=("Segoe UI", 9, "bold"), bg="#64748b", fg="white", relief="flat", cursor="hand2", padx=10, command=self.load_sales_data)
        btn_all.pack(side="left", padx=(0, 15))

        export_btn = tk.Button(action_frame, text="📥 I-export sa CSV", font=("Segoe UI", 9, "bold"), 
                               bg="#16a34a", fg="white", relief="flat", cursor="hand2", padx=10,
                               command=self.export_sales_to_excel)
        export_btn.pack(side="right")

        delete_sale_btn = tk.Button(action_frame, text="🗑️ Tanggalin ang Sale", font=("Segoe UI", 9, "bold"), 
                                    bg="#ef4444", fg="white", relief="flat", cursor="hand2", padx=10,
                                    command=self.delete_selected_sale)
        delete_sale_btn.pack(side="right", padx=(0, 10))

        self.tree_sales = ttk.Treeview(sales_container, columns=("ID", "DateTime", "Subtotal", "Non-VAT", "VAT", "Total", "Cash", "Change"), show="headings")
        self.tree_sales.heading("ID", text="Sale ID")
        self.tree_sales.heading("DateTime", text="Petsa at Oras")
        self.tree_sales.heading("Subtotal", text="Subtotal")
        self.tree_sales.heading("Non-VAT", text="Non-VAT Sales")
        self.tree_sales.heading("VAT", text="VAT Amount")
        self.tree_sales.heading("Total", text="Total Due")
        self.tree_sales.heading("Cash", text="Cash")
        self.tree_sales.heading("Change", text="Change")

        self.tree_sales.column("ID", width=60, anchor="center")
        self.tree_sales.column("DateTime", width=150, anchor="center")
        self.tree_sales.column("Subtotal", width=90, anchor="e")
        self.tree_sales.column("Non-VAT", width=90, anchor="e")
        self.tree_sales.column("VAT", width=80, anchor="e")
        self.tree_sales.column("Total", width=90, anchor="e")
        self.tree_sales.column("Cash", width=90, anchor="e")
        self.tree_sales.column("Change", width=90, anchor="e")

        sc_sales = ttk.Scrollbar(sales_container, orient="vertical", command=self.tree_sales.yview)
        self.tree_sales.configure(yscrollcommand=sc_sales.set)

        self.tree_sales.pack(side="left", fill="both", expand=True)
        sc_sales.pack(side="right", fill="y")

    def load_sales_data(self):
        if hasattr(self, 'tree_sales'):
            for r in self.tree_sales.get_children():
                self.tree_sales.delete(r)
            self.cursor.execute("SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount FROM sales ORDER BY id DESC")
            for row in self.cursor.fetchall():
                self.tree_sales.insert("", "end", values=(
                    row[0], row[1], 
                    f"₱ {row[2]:,.2f}", 
                    f"₱ {row[3]:,.2f}", 
                    f"₱ {row[4]:,.2f}", 
                    f"₱ {row[5]:,.2f}", 
                    f"₱ {row[6]:,.2f}", 
                    f"₱ {row[7]:,.2f}"
                ))

    def filter_sales_by_date(self):
        selected_date = self.entry_sales_date.get().strip()
        if not selected_date:
            messagebox.showwarning("Warning", "Ilagay ang petsa sa format na YYYY-MM-DD.")
            return

        for r in self.tree_sales.get_children():
            self.tree_sales.delete(r)

        self.cursor.execute("""
            SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount 
            FROM sales 
            WHERE date_time LIKE ? 
            ORDER BY id DESC
        """, (f"{selected_date}%",))
        
        rows = self.cursor.fetchall()
        for row in rows:
            self.tree_sales.insert("", "end", values=(
                row[0], row[1], 
                f"₱ {row[2]:,.2f}", 
                f"₱ {row[3]:,.2f}", 
                f"₱ {row[4]:,.2f}", 
                f"₱ {row[5]:,.2f}", 
                f"₱ {row[6]:,.2f}", 
                f"₱ {row[7]:,.2f}"
            ))

    def delete_selected_sale(self):
        selected = self.tree_sales.selection()
        if not selected:
            messagebox.showwarning("Babala", "Pumili muna ng sale record sa listahan na gusto mong tanggalin.")
            return

        item_values = self.tree_sales.item(selected[0], 'values')
        sale_id = item_values[0]

        confirm = messagebox.askyesno("Kumpirmahin ang Pagtanggal", f"Sigurado ka bang gusto mong tanggalin ang Sale ID #{sale_id}?")
        if confirm:
            try:
                self.cursor.execute("DELETE FROM sales_details WHERE sale_id = ?", (sale_id,))
                self.cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
                self.conn.commit()
                
                messagebox.showinfo("Tagumpay", f"Matagumpay na natanggal ang Sale ID #{sale_id}.")
                self.load_sales_data()
            except Exception as e:
                messagebox.showerror("Error", f"Hindi ma-delete ang sale record: {e}")

    def export_sales_to_excel(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files (Excel compatible)", "*.csv"), ("All Files", "*.*")],
            title="I-save ang Daily Sales bilang Excel"
        )
        if not file_path:
            return
         
        try:
            self.cursor.execute("SELECT id, date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount FROM sales ORDER BY id ASC")
            rows = self.cursor.fetchall()
             
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["Sale ID", "Date & Time", "Subtotal", "Non-VAT Sales", "VAT Amount", "Total Due", "Cash Tendered", "Change"])
                for row in rows:
                    writer.writerow(row)
                     
            messagebox.showinfo("Success", f"Matagumpay na na-export ang Daily Sales sa:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Nagka-error sa pag-export: {e}")

    # ---------------------------------------------------------
    # ITEM & CART LOGIC (MAY DISCOUNT FUNCTION)
    # ---------------------------------------------------------
    def load_items(self):
        for r in self.tree_services.get_children():
            self.tree_services.delete(r)
        self.cursor.execute("SELECT id, name, price FROM items WHERE category='Services'")
        for row in self.cursor.fetchall():
            self.tree_services.insert("", "end", values=(row[0], row[1], f"{row[2]:,.2f}"))

        for r in self.tree_inventory.get_children():
            self.tree_inventory.delete(r)
        self.cursor.execute("SELECT id, barcode, name, price, stock FROM items WHERE category='Inventory'")
        for row in self.cursor.fetchall():
            bc = row[1] if row[1] else "N/A"
            self.tree_inventory.insert("", "end", values=(row[0], bc, row[2], f"{row[3]:,.2f}", row[4]))

    def on_tab_change(self, event=None):
        pass

    def add_selected_to_cart(self, tree, category):
        selected = tree.selection()
        if not selected:
            return
        item_vals = tree.item(selected[0], 'values')
        item_id = item_vals[0]

        self.cursor.execute("SELECT name, price, stock, category FROM items WHERE id=?", (item_id,))
        db_item = self.cursor.fetchone()
        if not db_item:
            return

        name, price, stock, cat = db_item

        if cat == "Inventory" and stock == 0:
            messagebox.showerror("Out of Stock", f"Ang item na '{name}' ay walang stock na.")
            return

        for cart_item in self.cart:
            if cart_item['id'] == int(item_id):
                if cat == "Inventory" and stock != -1 and cart_item['qty'] >= stock:
                    messagebox.showwarning("Stock Limit", f"Naabot na ang maximum stock para sa '{name}'.")
                    return
                cart_item['qty'] += 1
                self.update_cart_display()
                return

        # Nagdagdag ng default discount properties ('none', 0)
        self.cart.append({
            'id': int(item_id),
            'name': name,
            'price': price,
            'qty': 1,
            'category': cat,
            'discount_type': 'none',  # 'none', 'percentage', 'fixed'
            'discount_value': 0.0     # halaga ng discount
        })
        self.update_cart_display()

    def add_active_tab_item(self):
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:
            self.add_selected_to_cart(self.tree_services, "Services")
        elif current_tab == 1:
            self.add_selected_to_cart(self.tree_inventory, "Inventory")

    def on_barcode_scanned(self, event=None):
        code = self.entry_barcode.get().strip()
        if not code:
            return

        self.cursor.execute("SELECT id, name, price, stock, category FROM items WHERE barcode=?", (code,))
        db_item = self.cursor.fetchone()
        self.entry_barcode.delete(0, tk.END)

        if not db_item:
            messagebox.showerror("Not Found", f"Walang item na nahanap para sa barcode / search: '{code}'")
            return

        item_id, name, price, stock, cat = db_item

        if cat == "Inventory" and stock == 0:
            messagebox.showerror("Out of Stock", f"Ang item na '{name}' ay walang stock na.")
            return

        for cart_item in self.cart:
            if cart_item['id'] == item_id:
                if cat == "Inventory" and stock != -1 and cart_item['qty'] >= stock:
                    messagebox.showwarning("Stock Limit", f"Naabot na ang maximum stock para sa '{name}'.")
                    return
                cart_item['qty'] += 1
                self.update_cart_display()
                return

        self.cart.append({
            'id': item_id,
            'name': name,
            'price': price,
            'qty': 1,
            'category': cat,
            'discount_type': 'none',
            'discount_value': 0.0
        })
        self.update_cart_display()

    def open_edit_discount_window(self, event=None):
        """Window para mag-input o mag-edit ng discount sa napiling cart item"""
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showwarning("Babala", "Pumili muna ng item sa kasalukuyang order nalalagyan ng discount.")
            return

        idx = self.cart_tree.index(selected[0])
        item = self.cart[idx]

        disc_win = tk.Toplevel(self.root)
        disc_win.title(f"Discount: {item['name']}")
        disc_win.geometry("340x240")
        disc_win.grab_set()
        disc_win.configure(bg="#f1f5f9")

        tk.Label(disc_win, text=f"🏷️ I-apply ang Discount", font=("Segoe UI", 11, "bold"), bg="#f1f5f9", fg="#0284c7").pack(pady=10)

        form_frm = tk.Frame(disc_win, bg="white", padx=12, pady=12, bd=1, relief="solid")
        form_frm.pack(fill="both", expand=True, padx=15, pady=5)

        tk.Label(form_frm, text="Uri ng Discount:", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        
        dtype_var = tk.StringVar(value=item['discount_type'])
        combo_dtype = ttk.Combobox(form_frm, textvariable=dtype_var, values=["none", "percentage", "fixed"], state="readonly", font=("Segoe UI", 9))
        combo_dtype.pack(fill="x", pady=(2, 8))

        tk.Label(form_frm, text="Halaga ng Discount (% o ₱):", font=("Segoe UI", 9, "bold"), bg="white").pack(anchor="w")
        e_val = tk.Entry(form_frm, font=("Segoe UI", 10))
        e_val.pack(fill="x", pady=(2, 12))
        e_val.insert(0, str(item['discount_value']))

        def apply_discount():
            dtype = dtype_var.get()
            try:
                val = float(e_val.get().strip())
            except ValueError:
                val = 0.0

            if dtype == 'percentage' and (val < 0 or val > 100):
                messagebox.showerror("Error", "Ang percentage ay dapat nasa pagitan ng 0 at 100.", parent=disc_win)
                return
            if dtype == 'fixed' and val < 0:
                messagebox.showerror("Error", "Hindi pwedeng maging negatibo ang fixed discount.", parent=disc_win)
                return

            item['discount_type'] = dtype if dtype != 'none' else 'none'
            item['discount_value'] = val if dtype != 'none' else 0.0

            self.update_cart_display()
            disc_win.destroy()

        btn_apply = tk.Button(form_frm, text="✔ I-apply ang Discount", font=("Segoe UI", 9, "bold"), bg="#22c55e", fg="white", relief="flat", cursor="hand2", command=apply_discount)
        btn_apply.pack(fill="x")

    def update_cart_display(self):
        for r in self.cart_tree.get_children():
            self.cart_tree.delete(r)

        subtotal = 0.0
        tax_services = 0.0
        tax_inventory = 0.0

        cust_type = self.customer_type_var.get()

        for item in self.cart:
            base_item_total = item['price'] * item['qty']
            item_discount_amount = 0.0

            # Kinakalkula ang per-item discount bago makuha ang final subtotal ng line item
            if item['discount_type'] == 'percentage':
                item_discount_amount = base_item_total * (item['discount_value'] / 100.0)
            elif item['discount_type'] == 'fixed':
                item_discount_amount = item['discount_value'] * item['qty']

            # Proteksyon laban sa labis na discount
            if item_discount_amount > base_item_total:
                item_discount_amount = base_item_total

            final_item_subtotal = base_item_total - item_discount_amount
            item['subtotal'] = final_item_subtotal  # Save computed subtotal

            # Displey string para sa discount column
            if item['discount_type'] == 'percentage':
                disc_str = f"{item['discount_value']}% (-₱{item_discount_amount:,.2f})"
            elif item['discount_type'] == 'fixed':
                disc_str = f"₱{item['discount_value']} (-₱{item_discount_amount:,.2f})"
            else:
                disc_str = "Wala"

            self.cart_tree.insert("", "end", values=(
                item['name'],
                item['qty'],
                f"₱ {item['price']:,.2f}",
                disc_str,
                f"₱ {final_item_subtotal:,.2f}"
            ))

            subtotal += final_item_subtotal

            if cust_type == "Government Customer":
                if item['category'] == "Services":
                    tax_services += final_item_subtotal * (self.tax_rate_services / 100.0)
                elif item['category'] == "Inventory":
                    tax_inventory += final_item_subtotal * (self.tax_rate_inventory / 100.0)

        total_tax = tax_services + tax_inventory
        total_due = subtotal + total_tax

        self.lbl_subtotal.config(text=f"₱ {subtotal:,.2f}")
        self.lbl_tax_services.config(text=f"₱ {tax_services:,.2f}")
        self.lbl_tax_inventory.config(text=f"₱ {tax_inventory:,.2f}")
        self.lbl_total.config(text=f"₱ {total_due:,.2f}")

        self.calculate_change()

    def remove_cart_item(self):
        selected = self.cart_tree.selection()
        if not selected:
            return
        idx = self.cart_tree.index(selected[0])
        if 0 <= idx < len(self.cart):
            self.cart.pop(idx)
            self.update_cart_display()

    def clear_cart(self):
        self.cart = []
        self.update_cart_display()
        self.entry_cash.delete(0, tk.END)
        self.lbl_change.config(text="₱ 0.00")

    def calculate_change(self, event=None):
        try:
            total_text = self.lbl_total.cget("text").replace("₱", "").replace(",", "").strip()
            total_due = float(total_text)
        except ValueError:
            total_due = 0.0

        cash_text = self.entry_cash.get().strip()
        if not cash_text:
            self.lbl_change.config(text="₱ 0.00")
            return

        try:
            cash = float(cash_text)
            change = cash - total_due
            if change >= 0:
                self.lbl_change.config(text=f"₱ {change:,.2f}", fg="#0284c7")
            else:
                self.lbl_change.config(text=f"₱ {change:,.2f}", fg="#ef4444")
        except ValueError:
            self.lbl_change.config(text="₱ 0.00")

    # ---------------------------------------------------------
    # PRINT RECEIPT & CHECKOUT FUNCTIONALITY
    # ---------------------------------------------------------
    def print_receipt(self, sale_id, cart_items, subtotal, tax_services, tax_inventory, total_due, cash, change, customer_type):
        date_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        receipt_text = "=" * 42 + "\n"
        receipt_text += f"{self.store_name:^42}\n"
        receipt_text += f"TIN: {self.tin_number:^42}\n"
        receipt_text += f"Services Tax: {self.tax_rate_services}% | Inv Tax: {self.tax_rate_inventory}%\n"
        receipt_text += "=" * 42 + "\n"
        receipt_text += f"Sale ID: #{sale_id}\n"
        receipt_text += f"Date/Time: {date_time_str}\n"
        receipt_text += f"Customer: {customer_type}\n"
        receipt_text += "-" * 42 + "\n"
        receipt_text += f"{'Item':<16} {'Qty':<3} {'Price':<7} {'Disc':<7} {'Total':<7}\n"
        receipt_text += "-" * 42 + "\n"

        for item in cart_items:
            name = item['name'][:15]
            qty = item['qty']
            price = item['price']
            subtot = item['subtotal']
            
            disc_desc = "None"
            if item['discount_type'] == 'percentage':
                disc_desc = f"{int(item['discount_value'])}%"
            elif item['discount_type'] == 'fixed':
                disc_desc = f"₱{int(item['discount_value'])}"

            receipt_text += f"{name:<16} {qty:<3} {price:<7.1f} {disc_desc:<7} {subtot:<7.2f}\n"

        receipt_text += "-" * 42 + "\n"
        receipt_text += f"Subtotal: {'₱ ' + f'{subtotal:,.2f}':>31}\n"
        if customer_type == "Government Customer":
            receipt_text += f"Services Tax: {'₱ ' + f'{tax_services:,.2f}':>27}\n"
            receipt_text += f"Inventory Tax: {'₱ ' + f'{tax_inventory:,.2f}':>26}\n"
        receipt_text += f"TOTAL DUE: {'₱ ' + f'{total_due:,.2f}':>29}\n"
        receipt_text += f"Cash Tendered: {'₱ ' + f'{cash:,.2f}':>26}\n"
        receipt_text += f"Change: {'₱ ' + f'{change:,.2f}':>33}\n"
        receipt_text += "=" * 42 + "\n"
        receipt_text += f"{'SALAMAT SA PAGTANGKILIK!':^42}\n"
        receipt_text += "=" * 42 + "\n"

        temp_receipt_path = "temp_receipt.txt"
        try:
            with open(temp_receipt_path, "w", encoding="utf-8") as f:
                f.write(receipt_text)
            
            if os.name == 'nt':
                os.startfile(temp_receipt_path, "print")
            else:
                os.system(f"lpr {temp_receipt_path}")
                
        except Exception as e:
            print(f"Auto-print error: {e}")
            self.show_receipt_preview(sale_id, receipt_text)

    def show_receipt_preview(self, sale_id, receipt_text):
        receipt_win = tk.Toplevel(self.root)
        receipt_win.title(f"Receipt Preview - Sale #{sale_id}")
        receipt_win.geometry("420x620")
        receipt_win.grab_set()

        txt_area = tk.Text(receipt_win, font=("Courier New", 10), bg="white", fg="black", padx=10, pady=10)
        txt_area.pack(fill="both", expand=True, padx=10, pady=10)
        txt_area.insert("1.0", receipt_text)
        txt_area.config(state="disabled")

        btn_frame = tk.Frame(receipt_win, bg="#f1f5f9", pady=10)
        btn_frame.pack(fill="x")

        def save_and_close():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                title="I-save ang Resibo"
            )
            if file_path:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(receipt_text)
                    messagebox.showinfo("Success", f"Matagumpay na nai-save ang resibo sa:\n{file_path}", parent=receipt_win)
                    receipt_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Hindi ma-save ang resibo: {e}", parent=receipt_win)

        btn_print = tk.Button(btn_frame, text="🖨️ I-print Muli", font=("Segoe UI", 10, "bold"), bg="#16a34a", fg="white", relief="flat", cursor="hand2", padx=15, pady=5, command=save_and_close)
        btn_print.pack()

    def process_checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Walang laman ang kasalukuyang order.")
            return

        try:
            total_text = self.lbl_total.cget("text").replace("₱", "").replace(",", "").strip()
            total_due = float(total_text)
        except ValueError:
            total_due = 0.0

        cash_text = self.entry_cash.get().strip()
        if not cash_text:
            messagebox.showerror("Missing Cash", "Pakilagay ang cash tendered ng customer.")
            return

        try:
            cash = float(cash_text)
        except ValueError:
            messagebox.showerror("Invalid Input", "Maglagay ng tamang numero para sa cash tendered.")
            return

        if cash < total_due:
            messagebox.showerror("Insufficient Cash", "Kulang ang ibinigay na cash ng customer.")
            return

        change = cash - total_due
        subtotal_text = self.lbl_subtotal.cget("text").replace("₱", "").replace(",", "").strip()
        subtotal = float(subtotal_text)

        serv_tax_text = self.lbl_tax_services.cget("text").replace("₱", "").replace(",", "").strip()
        inv_tax_text = self.lbl_tax_inventory.cget("text").replace("₱", "").replace(",", "").strip()
        total_tax = float(serv_tax_text) + float(inv_tax_text)

        non_vat_sales = subtotal if self.customer_type_var.get() == "Regular Customer" else 0.0

        date_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute('''
            INSERT INTO sales (date_time, subtotal, non_vat_sales, vat_amount, total, cash, change_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (date_time_str, subtotal, non_vat_sales, total_tax, total_due, cash, change))
        
        sale_id = self.cursor.lastrowid

        for item in self.cart:
            self.cursor.execute('''
                INSERT INTO sales_details (sale_id, item_name, price, quantity, subtotal)
                VALUES (?, ?, ?, ?, ?)
            ''', (sale_id, item['name'], item['price'], item['qty'], item['subtotal']))

            if item['category'] == 'Inventory':
                self.cursor.execute('''
                    UPDATE items SET stock = stock - ? WHERE id = ? AND stock != -1
                ''', (item['qty'], item['id']))

        self.conn.commit()

        cart_snapshot = list(self.cart)
        cust_type = self.customer_type_var.get()

        messagebox.showinfo("Success", f"Matagumpay na nakumpleto ang sale!\nChange: ₱ {change:,.2f}")
        
        self.print_receipt(sale_id, cart_snapshot, subtotal, float(serv_tax_text), float(inv_tax_text), total_due, cash, change, cust_type)

        self.clear_cart()
        self.load_items()
        self.load_sales_data()

if __name__ == "__main__":
    root = tk.Tk()
    app = RTechComputerCenterPOS(root)
    root.mainloop()
