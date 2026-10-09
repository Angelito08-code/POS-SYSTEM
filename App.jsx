import React, { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:5000/api';

export default function PosApp() {
  const [items, setItems] = useState([]);
  const [settings, setSettings] = useState({
    store_name: 'R-TECH COMPUTER CENTER',
    tin_number: '123-456-789-00000',
    tax_rate_services: 4.0,
    tax_rate_inventory: 5.0,
  });

  const [cart, setCart] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [customerType, setCustomerType] = useState('Regular Customer');
  const [siNumber, setSiNumber] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [cashTendered, setCashTendered] = useState(0);
  const [receiptText, setReceiptText] = useState(null);

  useEffect(() => {
    fetchSettings();
    fetchItems();
  }, []);

  const fetchSettings = async () => {
    const res = await fetch(`${API_BASE}/settings`);
    const data = await res.json();
    setSettings(data);
  };

  const fetchItems = async () => {
    const res = await fetch(`${API_BASE}/items`);
    const data = await res.json();
    setItems(data);
  };

  const addToCart = (item) => {
    if (item.category !== 'Services' && item.stock === 0) {
      alert(`Item '${item.name}' is out of stock!`);
      return;
    }

    setCart((prevCart) => {
      const existingIndex = prevCart.findIndex((c) => c.id === item.id);
      if (existingIndex > -1) {
        const updated = [...prevCart];
        const currentQty = updated[existingIndex].qty;
        if (item.category !== 'Services' && item.stock !== -1 && currentQty >= item.stock) {
          alert(`Stock limit reached for '${item.name}'`);
          return prevCart;
        }
        updated[existingIndex].qty += 1;
        return updated;
      }
      return [...prevCart, { ...item, qty: 1, discountType: 'none', discountValue: 0 }];
    });
  };

  const updateQty = (id, delta) => {
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.id === id) {
            const newQty = item.qty + delta;
            return newQty > 0 ? { ...item, qty: newQty } : null;
          }
          return item;
        })
        .filter(Boolean)
    );
  };

  const handleBarcodeScan = (e) => {
    if (e.key === 'Enter') {
      const match = items.find(
        (i) =>
          (i.barcode && i.barcode === searchQuery.trim()) ||
          i.name.toLowerCase().includes(searchQuery.toLowerCase().trim())
      );
      if (match) {
        addToCart(match);
        setSearchQuery('');
      } else {
        alert('Item not found');
      }
    }
  };

  // Tax and Calculation Logic
  let subtotal = 0;
  let taxServices = 0;
  let taxInventory = 0;

  const processedCart = cart.map((item) => {
    const baseTotal = item.price * item.qty;
    let discAmt = 0;
    if (item.discountType === 'percentage') {
      discAmt = baseTotal * (item.discountValue / 100);
    } else if (item.discountType === 'fixed') {
      discAmt = item.discountValue * item.qty;
    }
    const itemSubtotal = Math.max(0, baseTotal - discAmt);
    subtotal += itemSubtotal;

    if (customerType === 'Government Customer') {
      if (item.category === 'Services') {
        taxServices += itemSubtotal * (settings.tax_rate_services / 100);
      } else {
        taxInventory += itemSubtotal * (settings.tax_rate_inventory / 100);
      }
    }

    return { ...item, subtotal: itemSubtotal };
  });

  const totalTax = taxServices + taxInventory;
  const totalDue = subtotal + totalTax;
  const changeAmount = cashTendered - totalDue;

  const handleCheckout = async () => {
    if (!siNumber) return alert('Please enter an SI Number before checkout.');
    if (cashTendered < totalDue) return alert('Kulang ang ibinigay na cash ng customer.');

    const nowStr = new Date().toISOString().replace('T', ' ').substring(0, 19);

    const salePayload = {
      date_time: nowStr,
      si_number: siNumber,
      customer_name: customerName || customerType,
      total: totalDue,
      items: processedCart,
    };

    const res = await fetch(`${API_BASE}/sales`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(salePayload),
    });

    if (res.ok) {
      let receipt = '='.repeat(42) + '\n';
      receipt += settings.store_name.padStart((42 + settings.store_name.length) / 2) + '\n';
      receipt += `TIN: ${settings.tin_number}\n`;
      receipt += '='.repeat(42) + '\n';
      receipt += `SI Number: ${siNumber}\nDate/Time: ${nowStr}\nCustomer:${customerName || customerType}\n`;
      receipt += '-'.repeat(42) + '\n';
      processedCart.forEach((item) => {
        receipt += `${item.name.substring(0, 15).padEnd(16)} ${String(item.qty).padEnd(3)} ₱${item.subtotal.toFixed(2)}\n`;
      });
      receipt += '-'.repeat(42) + '\n';
      receipt += `TOTAL DUE: ₱ ${totalDue.toFixed(2)}\n`;
      receipt += `Cash Tendered: ₱ ${cashTendered.toFixed(2)}\n`;
      receipt += `Change: ₱ ${changeAmount.toFixed(2)}\n`;
      receipt += '='.repeat(42) + '\nSALAMAT SA PAGTANGKILIK!\n`;

      setReceiptText(receipt);
      setCart([]);
      setSiNumber('');
      setCashTendered(0);
      fetchItems();
    }
  };

  return (
    <div style={{ padding: 20, fontFamily: 'sans-serif', backgroundColor: '#f9f9f9' }}>
      {/* HEADER */}
      <header style={{ background: '#fff', padding: 15, borderRadius: 8, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0 }}>💻 {settings.store_name}</h2>
          <small>TIN: {settings.tin_number} | Services Tax: {settings.tax_rate_services}% | Inventory Tax: {settings.tax_rate_inventory}%</small>
        </div>
      </header>

      {/* MAIN LAYOUT */}
      <div style={{ display: 'flex', gap: 20 }}>
        {/* LEFT CATALOG */}
        <div style={{ flex: 1.3, background: '#fff', padding: 20, borderRadius: 8 }}>
          <h3>🔍 Search & Add to Cart</h3>
          <input
            type="text"
            placeholder="Scan barcode or type item code..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleBarcodeScan}
            style={{ width: '100%', padding: 10, boxSizing: 'border-box', marginBottom: 20 }}
          />

          <h3>Catalog Items</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#eee' }}>
                <th style={{ padding: 8, textAlign: 'left' }}>Item</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Category</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Price</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Stock</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} style={{ borderBottom: '1px solid #ddd' }}>
                  <td style={{ padding: 8 }}>{item.name}</td>
                  <td style={{ padding: 8 }}>{item.category}</td>
                  <td style={{ padding: 8 }}>₱{item.price.toFixed(2)}</td>
                  <td style={{ padding: 8 }}>{item.stock === -1 ? 'Unli' : item.stock}</td>
                  <td style={{ padding: 8 }}>
                    <button onClick={() => addToCart(item)} style={{ cursor: 'pointer', background: '#0d6efd', color: '#fff', border: 'none', padding: '5px 10px', borderRadius: 4 }}>
                      ➕ Add
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* RIGHT CART */}
        <div style={{ flex: 1, background: '#fff', padding: 20, borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>🛒 Current Order</h3>
            <button onClick={() => setCart([])} style={{ background: '#dc3545', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: 4, cursor: 'pointer' }}>
              Clear Cart
            </button>
          </div>

          <div style={{ margin: '15px 0' }}>
            <label>Customer Type: </label>
            <select value={customerType} onChange={(e) => setCustomerType(e.target.value)} style={{ width: '100%', padding: 8, margin: '5px 0 15px' }}>
              <option>Regular Customer</option>
              <option>Government Customer</option>
            </select>

            <input
              type="text"
              placeholder="SI Number (Sales Invoice #)"
              value={siNumber}
              onChange={(e) => setSiNumber(e.target.value)}
              style={{ width: '100%', padding: 8, margin: '5px 0', boxSizing: 'border-box' }}
            />
            <input
              type="text"
              placeholder="Customer Name"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              style={{ width: '100%', padding: 8, margin: '5px 0', boxSizing: 'border-box' }}
            />
          </div>

          {processedCart.length === 0 ? (
            <p>Cart is empty.</p>
          ) : (
            processedCart.map((item) => (
              <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #eee' }}>
                <div>
                  <strong>{item.name}</strong> <br />
                  <small>₱{item.price.toFixed(2)} x {item.qty}</small>
                </div>
                <div>
                  <button onClick={() => updateQty(item.id, 1)}>➕</button>
                  <button onClick={() => updateQty(item.id, -1)}>➖</button>
                </div>
              </div>
            ))
          )}

          <hr style={{ margin: '20px 0' }} />
          <p>Subtotal: ₱{subtotal.toFixed(2)}</p>
          {customerType === 'Government Customer' && (
            <p>Tax: ₱{totalTax.toFixed(2)}</p>
          )}
          <h3>TOTAL DUE: ₱{totalDue.toFixed(2)}</h3>

          <label>Cash Tendered (₱):</label>
          <input
            type="number"
            value={cashTendered}
            onChange={(e) => setCashTendered(parseFloat(e.target.value) || 0)}
            style={{ width: '100%', padding: 8, margin: '5px 0 15px', boxSizing: 'border-box' }}
          />

          <p style={{ color: changeAmount >= 0 ? 'green' : 'red', fontWeight: 'bold' }}>
            {changeAmount >= 0 ? `Change: ₱${changeAmount.toFixed(2)}` : `Short: ₱${Math.abs(changeAmount).toFixed(2)}`}
          </p>

          <button
            onClick={handleCheckout}
            style={{ width: '100%', padding: 12, background: '#198754', color: '#fff', border: 'none', borderRadius: 4, fontSize: 16, cursor: 'pointer' }}
          >
            ✔ COMPLETE SALE / CHECKOUT
          </button>
        </div>
      </div>

      {/* RECEIPT MODAL */}
      {receiptText && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ background: '#fff', padding: 20, borderRadius: 8, textAlign: 'center' }}>
            <h3>🖨️ Receipt Preview</h3>
            <pre style={{ textAlign: 'left', background: '#eee', padding: 15, fontFamily: 'monospace' }}>{receiptText}</pre>
            <button onClick={() => window.print()} style={{ background: '#0d6efd', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: 4, cursor: 'pointer', marginRight: 10 }}>
              Print Receipt
            </button>
            <button onClick={() => setReceiptText(null)} style={{ background: '#6c757d', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: 4, cursor: 'pointer' }}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
