const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const databaseUrl = process.env.DATABASE_URL || 'postgresql://postgres.ylwczrmidyndkvhgnblg:IzoMeELhcSr4Uhq5@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres';

const pool = new Pool({
  connectionString: databaseUrl,
  ssl: { rejectUnauthorized: false }
});

// Database Initialization
async function initDb() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS items (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER DEFAULT -1,
        barcode TEXT UNIQUE
      );

      CREATE TABLE IF NOT EXISTS sales (
        id SERIAL PRIMARY KEY,
        date_time TEXT NOT NULL,
        si_number TEXT,
        customer_name TEXT,
        total REAL NOT NULL
      );

      CREATE TABLE IF NOT EXISTS sales_details (
        id SERIAL PRIMARY KEY,
        sale_id INTEGER REFERENCES sales(id),
        item_name TEXT,
        price REAL,
        quantity INTEGER,
        subtotal REAL
      );

      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );
    `);

    await client.query(`
      ALTER TABLE sales ADD COLUMN IF NOT EXISTS si_number TEXT;
      ALTER TABLE sales ADD COLUMN IF NOT EXISTS customer_name TEXT;
    `);

    const { rows } = await client.query('SELECT COUNT(*) FROM items');
    if (parseInt(rows[0].count, 10) === 0) {
      const defaultItems = [
        ['B&W Print (per page)', 'Services', 5.00, -1, null],
        ['Color Print (per page)', 'Services', 10.00, -1, null],
        ['Document Scanning', 'Services', 15.00, -1, null],
        ['Lamination (per doc)', 'Services', 30.00, -1, null],
        ['Rush ID Picture', 'Services', 100.00, -1, null],
        ['Format Laptop/PC', 'Services', 500.00, -1, null],
        ['Pancit Canton', 'Inventory', 25.00, 50, '480001234567'],
        ['Cobra Energy Drink', 'Inventory', 35.00, 30, '480001234568'],
        ['Mineral Water 500ml', 'Inventory', 15.00, 40, '480001234569']
      ];
      for (const item of defaultItems) {
        await client.query(
          'INSERT INTO items (name, category, price, stock, barcode) VALUES ($1, $2, $3, $4, $5)',
          item
        );
      }
    }
  } catch (err) {
    console.error('DB Init Error:', err);
  } finally {
    client.release();
  }
}
initDb();

// --- API ENDPOINTS ---

app.get('/api/settings', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT key, value FROM settings');
    const settings = {};
    rows.forEach(r => settings[r.key] = r.value);
    res.json({
      store_name: settings.store_name || 'R-TECH COMPUTER CENTER',
      tin_number: settings.tin_number || '123-456-789-00000',
      tax_rate_services: parseFloat(settings.tax_rate_services || 4.0),
      tax_rate_inventory: parseFloat(settings.tax_rate_inventory || 5.0)
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/settings', async (req, res) => {
  const { store_name, tin_number, tax_rate_services, tax_rate_inventory } = req.body;
  try {
    const settings = { store_name, tin_number, tax_rate_services, tax_rate_inventory };
    for (const [key, value] of Object.entries(settings)) {
      await pool.query(
        'INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value',
        [key, String(value)]
      );
    }
    res.json({ message: 'Settings saved' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/items', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT * FROM items ORDER BY id ASC');
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/items', async (req, res) => {
  const { name, category, price, stock, barcode } = req.body;
  try {
    await pool.query(
      'INSERT INTO items (name, category, price, stock, barcode) VALUES ($1, $2, $3, $4, $5)',
      [name, category, price, stock ?? -1, barcode || null]
    );
    res.json({ message: 'Item added' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/sales', async (req, res) => {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const { date_time, si_number, customer_name, total, items } = req.body;

    const saleRes = await client.query(
      'INSERT INTO sales (date_time, si_number, customer_name, total) VALUES ($1, $2, $3, $4) RETURNING id',
      [date_time, si_number, customer_name, total]
    );
    const saleId = saleRes.rows[0].id;

    for (const item of items) {
      await client.query(
        'INSERT INTO sales_details (sale_id, item_name, price, quantity, subtotal) VALUES ($1, $2, $3, $4, $5)',
        [saleId, item.name, item.price, item.qty, item.subtotal]
      );

      if (item.category !== 'Services') {
        await client.query(
          'UPDATE items SET stock = stock - $1 WHERE id = $2 AND stock != -1',
          [item.qty, item.id]
        );
      }
    }

    await client.query('COMMIT');
    res.json({ message: 'Checkout successful', saleId });
  } catch (err) {
    await client.query('ROLLBACK');
    res.status(500).json({ error: err.message });
  } finally {
    client.release();
  }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));
