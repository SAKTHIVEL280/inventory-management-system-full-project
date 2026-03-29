/**
 * GRN (Goods Receipt Notes) Page
 * List, create, confirm GRNs. Confirms add stock to ledger.
 * 
 * Fixes applied:
 * - unit_price handling: consistent paise throughout (user enters rupees, converted to paise)
 * - GRN detail modal to inspect items before confirm
 * - Proper product filtering when linked to PO
 * - PO pending quantities shown for context
 * - Link uses new route /masters/suppliers
 * - Better validation and error messaging
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { purchaseApi, type GoodsReceiptNote, type CreateGRNPayload, type PurchaseOrder, type GRNItemResponse } from '../api/purchase';
import { apiClient } from '../api/client';
import { toast } from 'sonner';

interface ProductOption { id: string; name: string; product_code: string; purchase_price: number; gst_rate: number; }
interface SupplierOption { id: string; company_name: string; supplier_code: string; }

/** Internal line item — unit_price always in PAISE */
interface GRNLineItem {
  product_id: string;
  purchase_order_item_id?: string;
  quantity: number;
  unit_price: number;      // paise
  discount_percent: number;
  gst_rate: number;
  // Display-only context from PO
  po_ordered_qty?: number;
  po_received_qty?: number;
}

const GRNPage = () => {
  const [searchParams] = useSearchParams();
  const [grns, setGRNs] = useState<GoodsReceiptNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [suppliers, setSuppliers] = useState<SupplierOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null);
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([]);

  // GRN Detail modal state
  const [detailGRN, setDetailGRN] = useState<GoodsReceiptNote | null>(null);
  const [detailItems, setDetailItems] = useState<GRNItemResponse[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [supplierId, setSupplierId] = useState('');
  const [purchaseOrderId, setPurchaseOrderId] = useState<string | undefined>(undefined);
  const [receiptDate, setReceiptDate] = useState(new Date().toISOString().split('T')[0]);
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('');
  const [supplierInvoiceDate, setSupplierInvoiceDate] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<GRNLineItem[]>([]);

  const masterLoaded = useRef(false);
  const pendingPoId = useRef<string | null>(null);

  const fetchGRNs = async () => {
    try { setLoading(true); const res = await purchaseApi.listGRNs(statusFilter || undefined); setGRNs(res.data.items || []); } catch { setError('Failed to load GRNs'); } finally { setLoading(false); }
  };

  const fetchMaster = useCallback(async () => {
    try {
      const s = await apiClient.get('/api/v1/suppliers', { params: { page_size: 100 } });
      setSuppliers(Array.isArray(s.data?.items) ? s.data.items : []);
    } catch (err) {
      console.error('Failed to fetch suppliers:', err);
      setSuppliers([]);
    }
    try {
      const p = await apiClient.get('/api/v1/products', { params: { page_size: 100 } });
      setProducts(Array.isArray(p.data?.items) ? p.data.items : []);
    } catch (err) {
      console.error('Failed to fetch products:', err);
      setProducts([]);
    }
    masterLoaded.current = true;
    if (pendingPoId.current) {
      const poId = pendingPoId.current;
      pendingPoId.current = null;
      loadPOData(poId);
    }
  }, []);

  const fetchPOs = async () => {
    try {
      const [sentRes, partialRes] = await Promise.all([
        purchaseApi.listPOs('sent', 1, 100),
        purchaseApi.listPOs('partial', 1, 100),
      ]);
      const all = [...(sentRes.data.items || []), ...(partialRes.data.items || [])];
      const unique = Array.from(new Map(all.map((po) => [po.id, po])).values());
      setPurchaseOrders(unique);
    } catch {
      setPurchaseOrders([]);
    }
  };

  useEffect(() => {
    const poId = searchParams.get('po_id');
    if (poId) {
      if (masterLoaded.current) { loadPOData(poId); }
      else { pendingPoId.current = poId; }
    }
  }, [searchParams]);

  useEffect(() => { fetchGRNs(); }, [statusFilter]);
  useEffect(() => { fetchMaster(); fetchPOs(); }, []);

  const loadPOData = async (poId: string) => {
    try {
      const poRes = await purchaseApi.getPO(poId);
      const po = poRes.data.purchase_order;
      const poItems = poRes.data.items || [];

      if (!['sent', 'partial'].includes(po.status)) {
        toast.error('GRN can be created only from sent or partial PO');
        return;
      }

      const prefilledItems: GRNLineItem[] = poItems
        .map((item) => {
          const orderedQty = Number(item.quantity) || 0;
          const receivedQty = Number(item.received_quantity || 0);
          const pendingQty = Number((orderedQty - receivedQty).toFixed(4));
          return {
            product_id: item.product_id,
            purchase_order_item_id: item.id,
            quantity: pendingQty > 0 ? pendingQty : 0,
            unit_price: Number(item.unit_price) || 0,  // Already in paise from backend
            discount_percent: Number(item.discount_percent || 0),
            gst_rate: Number(item.gst_rate) || 0,
            po_ordered_qty: orderedQty,
            po_received_qty: receivedQty,
          };
        })
        .filter((item) => item.quantity > 0);

      setSelectedPO(po);
      setPurchaseOrderId(poId);
      setSupplierId(po.supplier_id);
      setItems(prefilledItems);
      setShowForm(true);
      toast.success('PO loaded. Verify received quantities and supplier invoice details.');
    } catch {
      toast.error('Failed to load PO data');
    }
  };

  const resetForm = () => {
    setSupplierId(''); setPurchaseOrderId(undefined); setSelectedPO(null);
    setReceiptDate(new Date().toISOString().split('T')[0]);
    setSupplierInvoiceNumber(''); setSupplierInvoiceDate('');
    setNotes(''); setItems([]); setError('');
  };

  const addItem = () => {
    setItems([...items, { product_id: '', quantity: 1, unit_price: 0, discount_percent: 0, gst_rate: 18 }]);
  };

  const updateItem = (idx: number, field: keyof GRNLineItem, value: string | number) => {
    const updated = [...items];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    // Auto-fill price and GST when product is selected (for standalone GRN)
    if (field === 'product_id') {
      const p = products.find(x => x.id === value);
      if (p) {
        updated[idx].unit_price = p.purchase_price; // Already in paise
        updated[idx].gst_rate = p.gst_rate;
      }
    }
    setItems(updated);
  };

  const removeItem = (idx: number) => setItems(items.filter((_, i) => i !== idx));

  // All calculations in PAISE — unit_price is always in paise
  const calcTotal = (i: GRNLineItem) => {
    const gross = i.unit_price * i.quantity;
    const disc = gross * (i.discount_percent || 0) / 100;
    const taxable = gross - disc;
    return taxable + taxable * i.gst_rate / 100;
  };

  const formatPaise = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  // Convert paise to rupees for display in input fields
  const paiseToRupees = (paise: number) => (paise / 100).toFixed(2);
  // Convert rupees input to paise
  const rupeesToPaise = (rupees: string) => Math.round((parseFloat(rupees) || 0) * 100);

  const handleSubmit = async () => {
    if (!supplierId) { setError('Please select a supplier'); return; }
    if (items.length === 0) { setError('Please add at least one item'); return; }
    if (!receiptDate) { setError('Please select a receipt date'); return; }
    const invalidItems = items.filter(i => !i.product_id);
    if (invalidItems.length > 0) { setError('Please select a product for all line items'); return; }
    const zeroQtyItems = items.filter(i => !i.quantity || i.quantity <= 0);
    if (zeroQtyItems.length > 0) { setError('All items must have a quantity greater than 0'); return; }

    setSubmitting(true); setError('');
    try {
      const payload: CreateGRNPayload = {
        supplier_id: supplierId,
        purchase_order_id: purchaseOrderId || undefined,
        receipt_date: receiptDate,
        supplier_invoice_number: supplierInvoiceNumber || undefined,
        supplier_invoice_date: supplierInvoiceDate || undefined,
        notes: notes || undefined,
        items: items.map(i => ({
          product_id: i.product_id,
          purchase_order_item_id: i.purchase_order_item_id || undefined,
          quantity: Number(i.quantity),
          unit_price: Number(i.unit_price),  // Already in paise
          discount_percent: Number(i.discount_percent || 0),
          gst_rate: Number(i.gst_rate),
        })),
      };
      await purchaseApi.createGRN(payload);
      toast.success('GRN created successfully');
      setShowForm(false); resetForm(); fetchGRNs(); fetchPOs();
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string | Array<{ msg: string; loc?: string[] }> } } };
      const detail = axErr?.response?.data?.detail;
      if (typeof detail === 'string') { setError(detail); }
      else if (Array.isArray(detail)) { setError(detail.map(d => d.msg).join(', ')); }
      else { setError('Failed to create GRN. Please check all fields and try again.'); }
    } finally { setSubmitting(false); }
  };

  const handleOpenDetail = async (grn: GoodsReceiptNote) => {
    setDetailGRN(grn);
    setDetailItems([]);
    setLoadingDetail(true);
    try {
      const res = await purchaseApi.getGRN(grn.id);
      setDetailGRN(res.data.grn);
      setDetailItems(res.data.items || []);
    } catch {
      setDetailItems([]);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleConfirm = async (id: string) => {
    if (!confirm('Confirm this GRN? Stock will be added to inventory.')) return;
    try {
      await purchaseApi.confirmGRN(id);
      toast.success('GRN confirmed — stock updated');
      fetchGRNs();
      fetchPOs(); // Refresh POs since status may have changed
      if (detailGRN?.id === id) {
        const res = await purchaseApi.getGRN(id);
        setDetailGRN(res.data.grn);
      }
    } catch (err: unknown) {
      const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof m === 'string' ? m : 'Failed to confirm GRN');
    }
  };

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this GRN?')) return;
    try {
      await purchaseApi.cancelGRN(id);
      toast.success('GRN cancelled');
      fetchGRNs();
      if (detailGRN?.id === id) {
        const res = await purchaseApi.getGRN(id);
        setDetailGRN(res.data.grn);
      }
    } catch { toast.error('Failed to cancel GRN'); }
  };

  const sc: Record<string, string> = { draft: 'bg-gray-100 text-gray-700', confirmed: 'bg-green-100 text-green-700', cancelled: 'bg-red-100 text-red-700' };

  // Products available for selection — filtered to PO products when linked
  const availableProducts = selectedPO
    ? products.filter(p => items.some(i => i.product_id === p.id))
    : products;

  return (
    <AppLayout title="Goods Receipt Notes (GRN)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All</option><option value="draft">Draft</option><option value="confirmed">Confirmed</option><option value="cancelled">Cancelled</option>
          </select>
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New GRN</button>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">GRN #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">PO #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Receipt Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier Inv #</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={8} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : grns.length === 0 ? <tr><td colSpan={8} className="px-4 py-8 text-center text-neutral-500">No GRNs found</td></tr>
                : grns.map(g => (
                  <tr key={g.id} className="border-b border-neutral-100 hover:bg-neutral-50 cursor-pointer" onClick={() => handleOpenDetail(g)}>
                    <td className="px-4 py-3 font-medium">{g.grn_number}</td>
                    <td className="px-4 py-3">{suppliers.find(s => s.id === g.supplier_id)?.company_name || '-'}</td>
                    <td className="px-4 py-3 text-xs">{g.purchase_order_id ? '✔ Linked' : '—'}</td>
                    <td className="px-4 py-3">{g.receipt_date}</td>
                    <td className="px-4 py-3">{g.supplier_invoice_number || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatPaise(g.total_amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[g.status] || 'bg-gray-100'}`}>{g.status}</span></td>
                    <td className="px-4 py-3 text-center">
                      {g.status === 'draft' && (
                        <div className="flex items-center justify-center gap-1">
                          <button onClick={(e) => { e.stopPropagation(); handleConfirm(g.id); }} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Confirm</button>
                          <button onClick={(e) => { e.stopPropagation(); handleCancel(g.id); }} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Cancel</button>
                        </div>
                      )}
                      <button onClick={(e) => { e.stopPropagation(); handleOpenDetail(g); }} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">View</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Total: {grns.length}</p>}
        </div>

        {/* ══════════════════ GRN Detail Modal ══════════════════ */}
        {detailGRN && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setDetailGRN(null)}>
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">GRN: {detailGRN.grn_number}</h2>
                  <p className="text-sm text-neutral-600 mt-1">Supplier: {suppliers.find(s => s.id === detailGRN.supplier_id)?.company_name || '-'}</p>
                </div>
                <button onClick={() => setDetailGRN(null)} className="text-neutral-400 hover:text-neutral-600 text-2xl">&times;</button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-neutral-50 p-4 rounded-lg">
                <div><p className="text-xs text-neutral-600">Receipt Date</p><p className="font-medium">{detailGRN.receipt_date}</p></div>
                <div><p className="text-xs text-neutral-600">Status</p><span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${sc[detailGRN.status] || 'bg-gray-100'}`}>{detailGRN.status}</span></div>
                <div><p className="text-xs text-neutral-600">Total Amount</p><p className="font-medium">{formatPaise(detailGRN.total_amount)}</p></div>
                <div><p className="text-xs text-neutral-600">Supplier Invoice</p><p className="font-medium">{detailGRN.supplier_invoice_number || '—'}</p></div>
              </div>

              {/* Tax Breakdown */}
              <div className="grid grid-cols-3 gap-4 bg-neutral-50 p-4 rounded-lg">
                <div><p className="text-xs text-neutral-600">Taxable</p><p className="font-medium">{formatPaise(detailGRN.total_taxable_amount)}</p></div>
                <div><p className="text-xs text-neutral-600">GST</p><p className="font-medium">{formatPaise(detailGRN.total_gst)}</p></div>
                <div>
                  <p className="text-xs text-neutral-600">Breakdown</p>
                  <p className="font-medium text-xs">
                    {detailGRN.total_igst > 0 ? `IGST: ${formatPaise(detailGRN.total_igst)}` : `CGST: ${formatPaise(detailGRN.total_cgst)} / SGST: ${formatPaise(detailGRN.total_sgst)}`}
                  </p>
                </div>
              </div>

              {/* Items */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Line Items</h3>
                {loadingDetail ? (
                  <p className="text-sm text-neutral-500 py-4 text-center">Loading items...</p>
                ) : detailItems.length === 0 ? (
                  <p className="text-sm text-neutral-400 py-4 text-center">No items found</p>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-neutral-200">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-neutral-50 border-b border-neutral-200">
                        <th className="px-3 py-2 text-left text-xs font-semibold">Product</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Qty</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Unit Price</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Disc %</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">GST %</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Total</th>
                      </tr></thead>
                      <tbody>
                        {detailItems.map((item, idx) => {
                          const product = products.find((p) => p.id === item.product_id);
                          return (
                            <tr key={idx} className="border-t border-neutral-100">
                              <td className="px-3 py-2 font-medium">{product?.name || 'Unknown'}</td>
                              <td className="px-3 py-2 text-right">{item.quantity}</td>
                              <td className="px-3 py-2 text-right">{formatPaise(item.unit_price)}</td>
                              <td className="px-3 py-2 text-right">{item.discount_percent || 0}%</td>
                              <td className="px-3 py-2 text-right">{item.gst_rate}%</td>
                              <td className="px-3 py-2 text-right font-medium">{formatPaise(item.total_amount)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                {detailGRN.status === 'draft' && (
                  <>
                    <button onClick={() => handleConfirm(detailGRN.id)} className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-green-700">✓ Confirm & Add Stock</button>
                    <button onClick={() => handleCancel(detailGRN.id)} className="bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-red-100">Cancel GRN</button>
                  </>
                )}
                {detailGRN.status === 'confirmed' && (
                  <span className="inline-flex items-center gap-1 text-sm text-green-600 font-medium">
                    <span className="material-icons text-sm">check_circle</span> Stock has been added to inventory
                  </span>
                )}
                <div className="flex-1" />
                <button onClick={() => setDetailGRN(null)} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-neutral-50">Close</button>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════ Create GRN Form Modal ══════════════════ */}
        {showForm && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">New GRN (Goods Receipt)</h2>
                  {selectedPO && (
                    <p className="text-sm text-primary mt-1">
                      Creating from PO: <span className="font-semibold">{selectedPO.po_number}</span>
                    </p>
                  )}
                </div>
                <button onClick={() => { setShowForm(false); resetForm(); }} className="text-neutral-400 hover:text-neutral-600 text-2xl">&times;</button>
              </div>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              {suppliers.length === 0 && !error && (
                <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">
                  No suppliers available. Create a supplier first in <Link to="/masters/suppliers" className="font-semibold underline">Masters → Suppliers</Link>.
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier *</label>
                  <select
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                    value={supplierId}
                    onChange={e => setSupplierId(e.target.value)}
                    disabled={!!selectedPO || suppliers.length === 0}
                  >
                    <option value="">Select</option>
                    {suppliers.map(s => (
                      <option key={s.id} value={s.id}>{s.company_name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Linked PO</label>
                  <select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={purchaseOrderId || ''}
                    onChange={e => {
                      const nextPoId = e.target.value;
                      if (nextPoId) { loadPOData(nextPoId); }
                      else { setPurchaseOrderId(undefined); setSelectedPO(null); setItems([]); setSupplierId(''); }
                    }}
                    disabled={!!selectedPO}
                  >
                    <option value="">Standalone GRN</option>
                    {purchaseOrders.filter(po => !supplierId || po.supplier_id === supplierId).map(po => 
                      <option key={po.id} value={po.id}>{po.po_number} ({po.status})</option>
                    )}
                  </select>
                </div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Receipt Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={receiptDate} onChange={e => setReceiptDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceNumber} onChange={e => setSupplierInvoiceNumber(e.target.value)} placeholder="e.g., SI-12345" /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice Date</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceDate} onChange={e => setSupplierInvoiceDate(e.target.value)} /></div>
              </div>

              {/* Line Items */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Items</h3>
                  {!selectedPO && (
                    <button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">+ Add Item</button>
                  )}
                </div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200">
                  <table className="w-full text-sm">
                    <thead><tr className="bg-neutral-50">
                      <th className="px-3 py-2 text-left">Product</th>
                      {selectedPO && <th className="px-3 py-2 text-right w-20">Ordered</th>}
                      {selectedPO && <th className="px-3 py-2 text-right w-20">Received</th>}
                      <th className="px-3 py-2 text-right w-20">Qty *</th>
                      <th className="px-3 py-2 text-right w-28">Price (₹)</th>
                      <th className="px-3 py-2 text-right w-20">Disc %</th>
                      <th className="px-3 py-2 text-right w-20">GST</th>
                      <th className="px-3 py-2 text-right w-28">Total</th>
                      {!selectedPO && <th className="w-10"></th>}
                    </tr></thead>
                    <tbody>
                      {items.map((item, idx) => (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            {selectedPO ? (
                              <span className="text-sm font-medium">{products.find(p => p.id === item.product_id)?.name || 'Unknown'}</span>
                            ) : (
                              <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                                <option value="">Select</option>
                                {availableProducts.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                              </select>
                            )}
                          </td>
                          {selectedPO && <td className="px-3 py-2 text-right text-neutral-500">{item.po_ordered_qty ?? '-'}</td>}
                          {selectedPO && <td className="px-3 py-2 text-right text-neutral-500">{item.po_received_qty ?? 0}</td>}
                          <td className="px-3 py-2">
                            <input type="number" min="0.01" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.quantity}
                              onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm"
                              value={paiseToRupees(item.unit_price)}
                              onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.discount_percent || 0}
                              onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                              <option value={0}>0%</option><option value={5}>5%</option><option value={12}>12%</option><option value={18}>18%</option><option value={28}>28%</option>
                            </select>
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatPaise(calcTotal(item))}</td>
                          {!selectedPO && (
                            <td className="px-3 py-2"><button onClick={() => removeItem(idx)} className="text-red-500">✕</button></td>
                          )}
                        </tr>
                      ))}
                      {items.length === 0 && <tr><td colSpan={selectedPO ? 8 : 8} className="px-3 py-4 text-center text-neutral-400">No items — {selectedPO ? 'link a PO to prefill items' : 'click "+ Add Item" to add items'}</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot><tr className="border-t-2 bg-neutral-50">
                        <td colSpan={selectedPO ? 7 : 5} className="px-3 py-2 text-right font-semibold">Total:</td>
                        <td className="px-3 py-2 text-right font-bold text-primary">{formatPaise(items.reduce((s, i) => s + calcTotal(i), 0))}</td>
                        {!selectedPO && <td></td>}
                      </tr></tfoot>
                    )}
                  </table>
                </div>
              </div>

              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting || suppliers.length === 0} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : 'Create GRN'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default GRNPage;
