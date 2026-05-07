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
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { purchaseApi, type GoodsReceiptNote, type CreateGRNPayload, type PurchaseOrder, type GRNItemResponse } from '../api/purchase';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { confirmWithToast } from '../utils/toastHelper';
import { addDaysToDateInputValue, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';
import { usePermissions } from '../hooks/usePermissions';

interface ProductOption { id: string; name: string; product_code: string; purchase_price: number; gst_rate: number; }
interface SupplierOption { id: string; company_name: string; supplier_code: string; payment_terms_days: number; }

interface LinkedPOItemOption {
  purchase_order_item_id: string;
  product_id: string;
  product_name: string;
  product_code: string;
  sku?: string;
  ordered_qty: number;
  received_qty: number;
  pending_qty: number;
  unit_price: number;
  discount_percent: number;
  gst_rate: number;
}

/** Internal line item — unit_price always in PAISE */
interface GRNLineItem {
  product_id: string;
  purchase_order_item_id?: string;
  batch_no?: string;
  manufacture_date?: string;
  expiry_date?: string;
  quantity: number;
  free_quantity?: number;
  unit_price: number;      // paise
  discount_percent: number;
  gst_rate: number;
  // Display-only context from PO
  po_ordered_qty?: number;
  po_received_qty?: number;
}

interface TolerancePopupData {
  title: 'Under delivery exceeded allowed tolerance' | 'Over delivery exceeded allowed tolerance';
  itemLabel: string;
  rowNumber: number;
  receivedQty: number;
  minAllowed: number;
  maxAllowed: number;
}

const GRNPage = () => {
  const [searchParams] = useSearchParams();
  const { isAdmin } = usePermissions();
  const [grns, setGRNs] = useState<GoodsReceiptNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [archiveView, setArchiveView] = useState<'active' | 'archived'>('active');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
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
  const [paymentTermsDays, setPaymentTermsDays] = useState(30);
  const [paymentDueDate, setPaymentDueDate] = useState('');
  const [underDeliveryTolerance, setUnderDeliveryTolerance] = useState(0);
  const [overDeliveryTolerance, setOverDeliveryTolerance] = useState(0);
  const [purchaseOrderId, setPurchaseOrderId] = useState<string | undefined>(undefined);
  const [receiptDate, setReceiptDate] = useState(todayLocalDateInputValue());
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('');
  const [supplierInvoiceDate, setSupplierInvoiceDate] = useState('');
  const [notes, setNotes] = useState('');
  const [itemSearchQuery, setItemSearchQuery] = useState('');
  const [items, setItems] = useState<GRNLineItem[]>([]);
  const [linkedPOItemOptions, setLinkedPOItemOptions] = useState<LinkedPOItemOption[]>([]);
  const [searchMatchedRowIndex, setSearchMatchedRowIndex] = useState<number | null>(null);
  const [tolerancePopup, setTolerancePopup] = useState<TolerancePopupData | null>(null);
  const [toleranceErrorItemIndex, setToleranceErrorItemIndex] = useState<number | null>(null);

  const masterLoaded = useRef(false);
  const pendingPoId = useRef<string | null>(null);
  const itemRowRefs = useRef<Array<HTMLTableRowElement | null>>([]);

  // Calculate payment due date from receipt date + payment terms
  const calculateDueDate = useCallback((receipt: string, terms: number) => {
    if (!receipt) return '';
    return addDaysToDateInputValue(receipt, terms);
  }, []);

  const fetchGRNs = async () => {
    try {
      setLoading(true);
      const res = await purchaseApi.listGRNs(statusFilter || undefined, 1, 20, { archived_only: archiveView === 'archived' });
      setGRNs(res.data.items || []);
    } catch {
      setError('Failed to load GRNs');
    } finally {
      setLoading(false);
    }
  };

  /* eslint-disable react-hooks/exhaustive-deps -- loadPOData is intentionally referenced after master data load to resolve pending PO deep-link */
  const fetchMaster = useCallback(async () => {
    try {
      const s = await apiClient.get('/api/v2/suppliers', { params: { page_size: 100 } });
      setSuppliers(Array.isArray(s.data?.items) ? s.data.items : []);
    } catch (err) {
      console.error('Failed to fetch suppliers:', err);
      setSuppliers([]);
    }
    try {
      const p = await apiClient.get('/api/v2/products', { params: { page_size: 100 } });
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
  /* eslint-enable react-hooks/exhaustive-deps */

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

  /* eslint-disable react-hooks/exhaustive-deps -- loadPOData intentionally excluded to avoid reloading PO data on unrelated state changes */
  useEffect(() => {
    const poId = searchParams.get('po_id');
    if (poId) {
      if (masterLoaded.current) { loadPOData(poId); }
      else { pendingPoId.current = poId; }
    }
  }, [searchParams]);
  /* eslint-enable react-hooks/exhaustive-deps */

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchGRNs is stable for this dependency set and should only run when filters change
  useEffect(() => { fetchGRNs(); }, [statusFilter, archiveView]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- one-time bootstrap for master + PO lists on mount
  useEffect(() => { fetchMaster(); fetchPOs(); }, []);
  
  // Recalculate due date when receipt date or payment terms change
  useEffect(() => {
    if (receiptDate && paymentTermsDays > 0) {
      setPaymentDueDate(calculateDueDate(receiptDate, paymentTermsDays));
    } else {
      setPaymentDueDate('');
    }
  }, [receiptDate, paymentTermsDays, calculateDueDate]);

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
            batch_no: '',
            manufacture_date: '',
            expiry_date: '',
            quantity: pendingQty > 0 ? pendingQty : 0,
            unit_price: Number(item.unit_price) || 0,  // Already in paise from backend
            discount_percent: Number(item.discount_percent || 0),
            gst_rate: Number(item.gst_rate) || 0,
            po_ordered_qty: orderedQty,
            po_received_qty: receivedQty,
          };
        })
        .filter((item) => item.quantity > 0);

      const poLinkedOptions: LinkedPOItemOption[] = poItems
        .map((item) => {
          const product = products.find((p) => p.id === item.product_id);
          const orderedQty = Number(item.quantity) || 0;
          const receivedQty = Number(item.received_quantity || 0);
          const pendingQty = Number((orderedQty - receivedQty).toFixed(4));
          return {
            purchase_order_item_id: item.id || '',
            product_id: item.product_id,
            product_name: product?.name || 'Unknown Product',
            product_code: product?.product_code || '-',
            sku: (product as ProductOption & { sku?: string })?.sku,
            ordered_qty: orderedQty,
            received_qty: receivedQty,
            pending_qty: pendingQty > 0 ? pendingQty : 0,
            unit_price: Number(item.unit_price || 0),
            discount_percent: Number(item.discount_percent || 0),
            gst_rate: Number(item.gst_rate || 0),
          };
        })
        .filter((row) => row.pending_qty > 0);

      setSelectedPO(po);
      setPurchaseOrderId(poId);
      setSupplierId(po.supplier_id);
      setUnderDeliveryTolerance(Number(po.under_delivery_tolerance || 0));
      setOverDeliveryTolerance(Number(po.over_delivery_tolerance || 0));
      
      // Auto-fill payment terms from supplier
      const supplier = suppliers.find(s => s.id === po.supplier_id);
      if (supplier) {
        setPaymentTermsDays(supplier.payment_terms_days ?? 30);
      }
      
      setLinkedPOItemOptions(poLinkedOptions);
      setItems(prefilledItems);
      setItemSearchQuery('');
      setTolerancePopup(null);
      setToleranceErrorItemIndex(null);
      setShowForm(true);
      toast.success('PO loaded. Verify received quantities and supplier invoice details.');
    } catch {
      toast.error('Failed to load PO data');
    }
  };

  const resetForm = () => {
    setSupplierId(''); setPaymentTermsDays(30); setPaymentDueDate(''); setUnderDeliveryTolerance(0); setOverDeliveryTolerance(0); setPurchaseOrderId(undefined); setSelectedPO(null);
    setReceiptDate(todayLocalDateInputValue());
    setSupplierInvoiceNumber(''); setSupplierInvoiceDate('');
    setNotes(''); setItemSearchQuery(''); setLinkedPOItemOptions([]); setItems([]); setError(''); setTolerancePopup(null); setToleranceErrorItemIndex(null); setSearchMatchedRowIndex(null);
  };

  const addItem = () => {
    setTolerancePopup(null);
    setToleranceErrorItemIndex(null);
    setSearchMatchedRowIndex(null);
    setItems([...items, { product_id: '', batch_no: '', manufacture_date: '', expiry_date: '', quantity: 0, unit_price: 0, discount_percent: 0, gst_rate: 18 }]);
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
    if (field === 'quantity' && toleranceErrorItemIndex === idx) {
      setTolerancePopup(null);
      setToleranceErrorItemIndex(null);
      setError('');
    }
    setItems(updated);
  };

  const updateItemFromPOOption = (idx: number, purchaseOrderItemId: string) => {
    const option = linkedPOItemOptions.find((row) => row.purchase_order_item_id === purchaseOrderItemId);
    if (!option) return;

    const updated = [...items];
    updated[idx] = {
      ...updated[idx],
      product_id: option.product_id,
      purchase_order_item_id: option.purchase_order_item_id,
      quantity: option.pending_qty > 0 ? option.pending_qty : 0,
      unit_price: option.unit_price,
      discount_percent: option.discount_percent,
      gst_rate: option.gst_rate,
      po_ordered_qty: option.ordered_qty,
      po_received_qty: option.received_qty,
    };

    if (toleranceErrorItemIndex === idx) {
      setTolerancePopup(null);
      setToleranceErrorItemIndex(null);
      setError('');
    }

    setItems(updated);
  };

  const removeItem = (idx: number) => {
    setTolerancePopup(null);
    setToleranceErrorItemIndex(null);
    setSearchMatchedRowIndex(null);
    setItems(items.filter((_, i) => i !== idx));
  };

  // All calculations in PAISE — unit_price is always in paise
  const calcTotal = (i: GRNLineItem) => {
    const gross = i.unit_price * i.quantity;
    const disc = gross * (i.discount_percent || 0) / 100;
    const taxable = gross - disc;
    return taxable + taxable * i.gst_rate / 100;
  };

  const formatPaise = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const formatQty = (qty: number) => Number(qty || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const openTolerancePopup = (payload: TolerancePopupData) => {
    setToleranceErrorItemIndex(payload.rowNumber - 1);
    setTolerancePopup(payload);
  };

  // Convert paise to rupees for display in input fields
  const paiseToRupees = (paise: number) => (paise / 100).toFixed(2);
  // Convert rupees input to paise
  const rupeesToPaise = (rupees: string) => Math.round((parseFloat(rupees) || 0) * 100);

  const handleSubmit = async () => {
    setTolerancePopup(null);
    setToleranceErrorItemIndex(null);
    if (!supplierId) { setError('Please select a supplier'); return; }
    if (items.length === 0) { setError('Please add at least one item'); return; }
    if (!receiptDate) { setError('Please select a receipt date'); return; }
    if (underDeliveryTolerance > overDeliveryTolerance) {
      setError('Under Delivery Tolerance must be less than or equal to Over Delivery Tolerance');
      return;
    }
    
    // Validate receipt date is not in the future
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const selectedDate = new Date(receiptDate);
    selectedDate.setHours(0, 0, 0, 0);
    if (selectedDate > today) {
      setError('Receipt date cannot be a future date. Please select today or a past date.');
      return;
    }
    
    const invalidItems = items.filter(i => !i.product_id);
    if (invalidItems.length > 0) { setError('Please select a product for all line items'); return; }
    const zeroQtyItems = items.filter(i => !i.quantity || i.quantity <= 0);
    if (zeroQtyItems.length > 0) { setError('All items must have a quantity greater than 0'); return; }

    if (selectedPO) {
      const qtyOutOfRangeIndex = items.findIndex((i) => {
        const orderedQty = Number(i.po_ordered_qty || 0);
        const minimumAllowed = Math.max(0, orderedQty - Number(underDeliveryTolerance || 0));
        const maximumAllowed = orderedQty + Number(overDeliveryTolerance || 0);
        const previouslyReceivedQty = Number(i.po_received_qty || 0);
        const currentReceivedQty = Number(i.quantity || 0);
        const cumulativeReceivedQty = previouslyReceivedQty + currentReceivedQty;
        return cumulativeReceivedQty < minimumAllowed || cumulativeReceivedQty > maximumAllowed;
      });

      if (qtyOutOfRangeIndex >= 0) {
        const qtyOutOfRange = items[qtyOutOfRangeIndex];
        const orderedQty = Number(qtyOutOfRange.po_ordered_qty || 0);
        const minimumAllowed = Math.max(0, orderedQty - Number(underDeliveryTolerance || 0));
        const maximumAllowed = orderedQty + Number(overDeliveryTolerance || 0);
        const previouslyReceivedQty = Number(qtyOutOfRange.po_received_qty || 0);
        const currentReceivedQty = Number(qtyOutOfRange.quantity || 0);
        const cumulativeReceivedQty = previouslyReceivedQty + currentReceivedQty;
        const isUnderDelivery = cumulativeReceivedQty < minimumAllowed;
        const productName = products.find((p) => p.id === qtyOutOfRange.product_id)?.name || `Line item ${qtyOutOfRangeIndex + 1}`;

        openTolerancePopup({
          title: isUnderDelivery ? 'Under delivery exceeded allowed tolerance' : 'Over delivery exceeded allowed tolerance',
          itemLabel: productName,
          rowNumber: qtyOutOfRangeIndex + 1,
          receivedQty: cumulativeReceivedQty,
          minAllowed: minimumAllowed,
          maxAllowed: maximumAllowed,
        });
        return;
      }
    }

    const invalidDateItemIndex = items.findIndex(
      (i) => i.manufacture_date && i.expiry_date && i.expiry_date < i.manufacture_date,
    );
    if (invalidDateItemIndex >= 0) {
      setError(`Line item ${invalidDateItemIndex + 1}: expiry date cannot be earlier than manufacture date`);
      return;
    }

    // GRN-007: Validate manufacture date is a past date only
    const todayIso = todayLocalDateInputValue();
    const invalidMfgDateIndex = items.findIndex(
      (i) => i.manufacture_date && i.manufacture_date >= todayIso,
    );
    if (invalidMfgDateIndex >= 0) {
      setError('MFG Date must be a past date');
      return;
    }

    // GRN-008: Validate expiry date is a future date only
    const invalidExpDateIndex = items.findIndex(
      (i) => i.expiry_date && i.expiry_date <= todayIso,
    );
    if (invalidExpDateIndex >= 0) {
      setError(`Line item ${invalidExpDateIndex + 1}: expiry date must be a future date`);
      return;
    }

    setSubmitting(true); setError('');
    try {
      const payload: CreateGRNPayload = {
        supplier_id: supplierId,
        purchase_order_id: purchaseOrderId || undefined,
        receipt_date: receiptDate,
        supplier_invoice_number: supplierInvoiceNumber || undefined,
        supplier_invoice_date: supplierInvoiceDate || undefined,
        under_delivery_tolerance: underDeliveryTolerance,
        over_delivery_tolerance: overDeliveryTolerance,
        notes: notes || undefined,
        items: items.map(i => ({
          product_id: i.product_id,
          purchase_order_item_id: i.purchase_order_item_id || undefined,
          batch_no: i.batch_no || undefined,
          manufacture_date: i.manufacture_date || undefined,
          expiry_date: i.expiry_date || undefined,
          quantity: Number(i.quantity),
          free_quantity: Number(i.free_quantity ?? 0),
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
    const confirmed = await confirmWithToast('Confirm this GRN? Stock will be added to inventory.', {
      type: 'warning',
    });
    if (!confirmed) return;
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
    const confirmed = await confirmWithToast('Cancel this GRN?', {
      type: 'danger',
    });
    if (!confirmed) return;
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

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await purchaseApi.restoreGRN(id);
      } else {
        await purchaseApi.archiveGRN(id);
      }
      toast.success(archived ? 'GRN restored' : 'GRN archived');
      fetchGRNs();
      if (detailGRN?.id === id) {
        setDetailGRN(null);
      }
    } catch {
      toast.error(archived ? 'Failed to restore GRN' : 'Failed to archive GRN');
    }
  };

  const statusChipClass = (grn: GoodsReceiptNote) => {
    const status = (grn.status || '').toLowerCase();
    if (status === 'cancelled') return 'bg-red-100 text-red-700';
    if (grn.is_partial_qty && status === 'confirmed') return 'bg-amber-100 text-amber-800';
    if (grn.is_partial_qty && status === 'draft') return 'bg-orange-100 text-orange-800';
    if (status === 'confirmed') return 'bg-green-100 text-green-700';
    if (status === 'draft') return 'bg-gray-100 text-gray-700';
    return 'bg-gray-100 text-gray-700';
  };

  const statusDisplayText = (grn: GoodsReceiptNote) => {
    if (grn.status_display && grn.status_display.trim()) return grn.status_display;
    const status = (grn.status || '').toLowerCase();
    if (status === 'draft') return grn.is_partial_qty ? 'Partial Receipt (Draft)' : 'Draft';
    if (status === 'confirmed') return grn.is_partial_qty ? 'Partial Receipt (Confirmed)' : 'Confirmed';
    if (status === 'cancelled') return 'Cancelled';
    return grn.status;
  };

  const compactStatusText = (grn: GoodsReceiptNote) => {
    const full = statusDisplayText(grn);
    if (full === 'Partial Receipt (Draft)') return 'Partial (Draft)';
    if (full === 'Partial Receipt (Confirmed)') return 'Partial (Confirmed)';
    return full;
  };

  const statusChipTextClass = 'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold leading-4 whitespace-nowrap';

  const supplierNameById = (id: string) => suppliers.find((s) => s.id === id)?.company_name || '-';

  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    if (dateTo && value && value > dateTo) {
      setDateTo(value);
    }
  };

  const handleDateToChange = (value: string) => {
    setDateTo(value);
    if (dateFrom && value && value < dateFrom) {
      setDateFrom(value);
    }
  };

  const handleLinkedPOChange = async (nextPoId: string) => {
    const currentPoId = purchaseOrderId || '';
    if (nextPoId === currentPoId) return;

    const hasUnsavedData =
      items.length > 0 ||
      Boolean(supplierInvoiceNumber.trim()) ||
      Boolean(supplierInvoiceDate) ||
      Boolean(notes.trim());

    if (hasUnsavedData) {
      const confirmed = await confirmWithToast('Changing the PO will reset current items. Do you want to continue?', {
        type: 'warning',
      });
      if (!confirmed) {
        return;
      }
    }

    setTolerancePopup(null);
    setToleranceErrorItemIndex(null);
    setSearchMatchedRowIndex(null);
    setError('');
    setItemSearchQuery('');
    setItems([]);
    setLinkedPOItemOptions([]);
    setSupplierInvoiceNumber('');
    setSupplierInvoiceDate('');
    setNotes('');

    if (nextPoId) {
      await loadPOData(nextPoId);
      return;
    }

    setPurchaseOrderId(undefined);
    setSelectedPO(null);
    setSupplierId('');
    setUnderDeliveryTolerance(0);
    setOverDeliveryTolerance(0);
  };

  const filteredGRNs = grns.filter((g) => {
    const q = searchQuery.trim().toLowerCase();
    const supplierName = supplierNameById(g.supplier_id);
    const poLabel = g.purchase_order_id ? 'linked' : 'unlinked';
    const matchesSearch =
      !q ||
      g.grn_number.toLowerCase().includes(q) ||
      supplierName.toLowerCase().includes(q) ||
      (g.supplier_invoice_number || '').toLowerCase().includes(q) ||
      g.receipt_date.toLowerCase().includes(q) ||
      g.status.toLowerCase().includes(q) ||
      poLabel.includes(q);

    const matchesFrom = !dateFrom || g.receipt_date >= dateFrom;
    const matchesTo = !dateTo || g.receipt_date <= dateTo;

    return matchesSearch && matchesFrom && matchesTo;
  });

  // Products available for selection — filtered to PO products when linked
  const availableProducts = selectedPO
    ? products.filter(p => items.some(i => i.product_id === p.id))
    : products;
  const todayDateInputMax = todayLocalDateInputValue();
  const mfgDateInputMax = addDaysToDateInputValue(todayDateInputMax, -1);
  const expiryDateInputMin = addDaysToDateInputValue(todayDateInputMax, 1);

  useEffect(() => {
    const query = itemSearchQuery.trim().toLowerCase();
    if (!query) {
      setSearchMatchedRowIndex(null);
      return;
    }

    const matchedIndex = items.findIndex((item) => {
      const linked = item.purchase_order_item_id
        ? linkedPOItemOptions.find((row) => row.purchase_order_item_id === item.purchase_order_item_id)
        : undefined;
      const product = products.find((p) => p.id === item.product_id);
      const name = product?.name || linked?.product_name || '';
      const code = product?.product_code || linked?.product_code || '';
      const haystack = `${name} ${code}`.toLowerCase();
      return haystack.includes(query);
    });

    if (matchedIndex < 0) {
      setSearchMatchedRowIndex(null);
      return;
    }

    setSearchMatchedRowIndex(matchedIndex);
    const rowEl = itemRowRefs.current[matchedIndex];
    if (rowEl) {
      rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [itemSearchQuery, items, products, linkedPOItemOptions]);

  return (
    <AppLayout title="Goods Receipt Notes (GRN)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option><option value="draft">Draft</option><option value="confirmed">Confirmed</option><option value="cancelled">Cancelled</option>
            </select>
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={archiveView} onChange={e => setArchiveView(e.target.value as 'active' | 'archived')}>
              <option value="active">Active Only</option>
              <option value="archived">Archived Only</option>
            </select>
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search GRN #, supplier, invoice #, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(e) => handleDateFromChange(e.target.value)}
                title="Receipt date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => handleDateToChange(e.target.value)}
                title="Receipt date to"
              />
            </div>
          </div>
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
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Due Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier Inv #</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : filteredGRNs.length === 0 ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No GRNs found</td></tr>
                : filteredGRNs.map(g => (
                  <tr key={g.id} className="border-b border-neutral-100 hover:bg-neutral-50 cursor-pointer" onClick={() => handleOpenDetail(g)}>
                    <td className="px-4 py-3 font-medium">{g.grn_number}</td>
                    <td className="px-4 py-3">{supplierNameById(g.supplier_id)}</td>
                    <td className="px-4 py-3 text-xs">
                      {g.purchase_order_id ? (
                        <span className="inline-flex items-center gap-1 text-green-700 font-medium">
                          <span className="material-icons text-sm" aria-hidden="true">check_circle</span>
                          {g.po_number || 'Linked'}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3">{g.receipt_date}</td>
                    <td className="px-4 py-3 font-medium text-neutral-700">{g.payment_due_date || '-'}</td>
                    <td className="px-4 py-3">{g.supplier_invoice_number || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatPaise(g.total_amount)}</td>
                    <td className="px-4 py-3 text-center"><span title={statusDisplayText(g)} className={`${statusChipTextClass} ${statusChipClass(g)}`}>{compactStatusText(g)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {archiveView === 'active' && g.status === 'draft' && (
                          <>
                            {isAdmin && (
                              <button onClick={(e) => { e.stopPropagation(); handleConfirm(g.id); }} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Confirm</button>
                            )}
                            <button onClick={(e) => { e.stopPropagation(); handleCancel(g.id); }} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Cancel</button>
                          </>
                        )}
                        <button onClick={(e) => { e.stopPropagation(); handleOpenDetail(g); }} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">View</button>
                        <button onClick={(e) => { e.stopPropagation(); void handleArchiveToggle(g.id, archiveView === 'archived'); }} className={`rounded px-2 py-1 text-xs font-medium ${archiveView === 'archived' ? 'text-emerald-700 hover:bg-emerald-50' : 'text-red-600 hover:bg-red-50'}`}>{archiveView === 'archived' ? 'Restore' : 'Archive'}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredGRNs.length} of {grns.length}</p>}
        </div>

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• GRN Detail Modal â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {detailGRN && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setDetailGRN(null)}>
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">GRN: {detailGRN.grn_number}</h2>
                  <p className="text-sm text-neutral-600 mt-1">Supplier: {suppliers.find(s => s.id === detailGRN.supplier_id)?.company_name || '-'}</p>
                </div>
                <button onClick={() => setDetailGRN(null)} className="text-neutral-400 hover:text-neutral-600 text-2xl">&times;</button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-7 gap-4 bg-neutral-50 p-4 rounded-lg">
                <div><p className="text-xs text-neutral-600">Receipt Date</p><p className="font-medium">{detailGRN.receipt_date}</p></div>
                <div><p className="text-xs text-neutral-600">Payment Due Date</p><p className="font-medium">{detailGRN.payment_due_date || '-'}</p></div>
                <div><p className="text-xs text-neutral-600">Status</p><span title={statusDisplayText(detailGRN)} className={`${statusChipTextClass} ${statusChipClass(detailGRN)}`}>{compactStatusText(detailGRN)}</span></div>
                <div><p className="text-xs text-neutral-600">Total Amount</p><p className="font-medium">{formatPaise(detailGRN.total_amount)}</p></div>
                <div><p className="text-xs text-neutral-600">Supplier Invoice</p><p className="font-medium">{detailGRN.supplier_invoice_number || '—'}</p></div>
                <div><p className="text-xs text-neutral-600">Under Delivery Tol. (Qty)</p><p className="font-medium">{Number(detailGRN.under_delivery_tolerance || 0).toFixed(2)}</p></div>
                <div><p className="text-xs text-neutral-600">Over Delivery Tol. (Qty)</p><p className="font-medium">{Number(detailGRN.over_delivery_tolerance || 0).toFixed(2)}</p></div>
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
                        <th className="px-3 py-2 text-left text-xs font-semibold">Product Code</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold">Product</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Received Qty</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold">Free</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold">Batch No</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold">MFG Date</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold">EXP Date</th>
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
                              <td className="px-3 py-2">
                                <span className="text-xs font-semibold text-neutral-700">{product?.product_code || '-'}</span>
                              </td>
                              <td className="px-3 py-2 font-medium">{product?.name || 'Unknown'}</td>
                              <td className="px-3 py-2 text-right font-medium">{item.quantity}</td>
                              <td className="px-3 py-2 text-right font-medium">{item.free_quantity || 0}</td>
                              <td className="px-3 py-2">{item.batch_no || '-'}</td>
                              <td className="px-3 py-2">{item.manufacture_date || '-'}</td>
                              <td className="px-3 py-2">{item.expiry_date || '-'}</td>
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
                    {isAdmin && (
                      <button onClick={() => handleConfirm(detailGRN.id)} className="inline-flex items-center gap-1 bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-green-700"><span className="material-icons text-sm" aria-hidden="true">task_alt</span>Confirm & Add Stock</button>
                    )}
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
          </div>,
          document.body
        )}

        {/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• Create GRN Form Modal â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */}
        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1600px)] max-w-none space-y-6 p-4 sm:p-6">
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
                  No suppliers available. Create a supplier first in <Link to="/masters/suppliers" className="font-semibold underline">Masters â†’ Suppliers</Link>.
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier *</label>
                  <select
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                    value={supplierId}
                    onChange={e => {
                      setSupplierId(e.target.value);
                      const selectedSupplier = suppliers.find(s => s.id === e.target.value);
                      if (selectedSupplier) {
                        setPaymentTermsDays(selectedSupplier.payment_terms_days ?? 30);
                      } else {
                        setPaymentTermsDays(30);
                      }
                    }}
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
                      void handleLinkedPOChange(e.target.value);
                    }}
                  >
                    <option value="">Standalone GRN</option>
                    {purchaseOrders.filter(po => !supplierId || po.supplier_id === supplierId).map(po =>
                      <option key={po.id} value={po.id}>{po.po_number} ({po.status})</option>
                    )}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Payment Terms (Days)</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm"
                    value={`${paymentTermsDays} days`}
                    readOnly
                    title="Auto-filled from supplier master"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Payment Due Date</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm"
                    value={paymentDueDate || '-'}
                    readOnly
                    title="Auto-calculated: Receipt Date + Payment Terms"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Under Delivery Tolerance (Qty)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={`w-full rounded-lg border px-3 py-2 text-sm ${selectedPO ? 'border-neutral-200 bg-neutral-50' : 'border-neutral-200'}`}
                    value={selectedPO ? underDeliveryTolerance : emptyWhenZero(underDeliveryTolerance)}
                    onChange={e => setUnderDeliveryTolerance(e.target.value === '' ? 0 : (parseFloat(e.target.value) || 0))}
                    placeholder="Enter tolerance"
                    readOnly={!!selectedPO}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Over Delivery Tolerance (Qty)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={`w-full rounded-lg border px-3 py-2 text-sm ${selectedPO ? 'border-neutral-200 bg-neutral-50' : 'border-neutral-200'}`}
                    value={selectedPO ? overDeliveryTolerance : emptyWhenZero(overDeliveryTolerance)}
                    onChange={e => setOverDeliveryTolerance(e.target.value === '' ? 0 : (parseFloat(e.target.value) || 0))}
                    placeholder="Enter tolerance"
                    readOnly={!!selectedPO}
                  />
                </div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Receipt Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={receiptDate} onChange={e => setReceiptDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceNumber} onChange={e => setSupplierInvoiceNumber(e.target.value)} placeholder="e.g., SI-12345" /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice Date</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceDate} onChange={e => setSupplierInvoiceDate(e.target.value)} /></div>
              </div>

              {/* Line Items */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Items</h3>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      className="w-72 rounded border border-neutral-200 px-2.5 py-1.5 text-xs"
                      placeholder={selectedPO ? 'Search PO items by name/code' : 'Search item by product or code'}
                      value={itemSearchQuery}
                      onChange={(e) => setItemSearchQuery(e.target.value)}
                    />
                    {!selectedPO && (
                      <button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">+ Add Item</button>
                    )}
                  </div>
                </div>
                <div className="max-h-[52vh] overflow-auto rounded-lg border border-neutral-200">
                  <table className="w-full min-w-[1700px] table-fixed text-sm">
                    <thead><tr className="bg-neutral-50">
                      <th className="px-3 py-2 text-right w-14">S.No</th>
                      <th className="px-3 py-2 text-left w-[12%] min-w-[120px]">Product Code</th>
                      <th className="px-3 py-2 text-left w-[32%] min-w-[320px]">Product</th>
                      <th className="px-3 py-2 text-right w-40">Received Qty</th>
                      <th className="px-3 py-2 text-right w-24">Free</th>
                      <th className="px-3 py-2 text-left w-32">Batch No</th>
                      <th className="px-3 py-2 text-left w-36">MFG Date</th>
                      <th className="px-3 py-2 text-left w-36">EXP Date</th>
                      <th className="px-3 py-2 text-right w-28">Price (₹)</th>
                      <th className="px-3 py-2 text-right w-20">Disc %</th>
                      <th className="px-3 py-2 text-right w-20">GST</th>
                      <th className="px-3 py-2 text-right w-28">Total</th>
                      {!selectedPO && <th className="w-10"></th>}
                    </tr></thead>
                    <tbody>
                      {items.map((item, idx) => (
                        <tr
                          key={idx}
                          ref={(el) => {
                            itemRowRefs.current[idx] = el;
                          }}
                          className={`border-t border-neutral-100 ${searchMatchedRowIndex === idx ? 'bg-amber-50' : ''}`}
                        >
                          <td className="px-3 py-2 text-right text-xs font-semibold text-neutral-600">{idx + 1}</td>
                          <td className="px-3 py-2">
                            <span className="text-xs font-semibold text-neutral-700">{products.find(p => p.id === item.product_id)?.product_code || linkedPOItemOptions.find((row) => row.purchase_order_item_id === item.purchase_order_item_id)?.product_code || '-'}</span>
                          </td>
                          <td className="px-3 py-2">
                            {selectedPO ? (
                              <select
                                className="h-9 w-full rounded border px-2 py-1.5 text-sm"
                                value={item.purchase_order_item_id || ''}
                                onChange={e => updateItemFromPOOption(idx, e.target.value)}
                              >
                                <option value="">Select PO Item</option>
                                {linkedPOItemOptions.map((row) => (
                                  <option key={row.purchase_order_item_id} value={row.purchase_order_item_id}>
                                    {row.product_name} ({row.product_code})
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <select className="h-9 w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                                <option value="">Select</option>
                                {availableProducts.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                              </select>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {selectedPO ? (
                              <div className="flex flex-col items-end gap-1">
                                <div className="text-[10px] text-neutral-500 whitespace-nowrap shrink-0">
                                  (Ord: {formatQty(item.po_ordered_qty ?? 0)} | Prev: {formatQty(item.po_received_qty ?? 0)})
                                </div>
                                <input
                                  type="number"
                                  min="0.01"
                                  step="0.01"
                                  className={`h-9 w-full rounded border px-2 py-1.5 text-right text-sm ${toleranceErrorItemIndex === idx ? 'border-red-400 bg-red-50 ring-1 ring-red-200' : ''}`}
                                  value={item.quantity}
                                  onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)}
                                  title={`Ordered: ${item.po_ordered_qty ?? 0}, Previously received: ${item.po_received_qty ?? 0}`}
                                />
                                <div className="text-[10px] text-neutral-500 whitespace-nowrap shrink-0">
                                  Allowed: {formatQty(Math.max(0, Number(item.po_ordered_qty || 0) - Number(underDeliveryTolerance || 0)))} - {formatQty(Number(item.po_ordered_qty || 0) + Number(overDeliveryTolerance || 0))}
                                </div>
                              </div>
                            ) : (
                              <input type="number" min="0.01" step="0.01" className="h-9 w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.quantity)}
                                onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} placeholder="Qty" />
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              className="h-9 w-full rounded border px-2 py-1.5 text-right text-sm"
                              value={emptyWhenZero(item.free_quantity)}
                              onChange={e => {
                                const val = e.target.value;
                                updateItem(idx, 'free_quantity', val === '' ? 0 : (parseFloat(val) || 0));
                              }}
                              placeholder="0"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input
                              type="text"
                              className="h-9 w-full rounded border px-2 py-1.5 text-sm"
                              value={item.batch_no || ''}
                              onChange={e => updateItem(idx, 'batch_no', e.target.value)}
                              placeholder="e.g. BATCH-001"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input
                              type="date"
                              className="h-9 w-full rounded border px-2 py-1.5 text-sm"
                              value={item.manufacture_date || ''}
                              max={mfgDateInputMax}
                              onChange={e => updateItem(idx, 'manufacture_date', e.target.value)}
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input
                              type="date"
                              className="h-9 w-full rounded border px-2 py-1.5 text-sm"
                              value={item.expiry_date || ''}
                              min={expiryDateInputMin}
                              onChange={e => updateItem(idx, 'expiry_date', e.target.value)}
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="h-9 w-full rounded border px-2 py-1.5 text-right text-sm"
                              value={item.unit_price ? paiseToRupees(item.unit_price) : ''}
                              onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className="h-9 w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.discount_percent)}
                              onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <select className="h-9 w-full rounded border px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                              <option value={0}>0%</option><option value={5}>5%</option><option value={12}>12%</option><option value={18}>18%</option><option value={28}>28%</option>
                            </select>
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatPaise(calcTotal(item))}</td>
                          {!selectedPO && (
                            <td className="px-3 py-2"><button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 text-red-500"><span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove</button></td>
                          )}
                        </tr>
                      ))}
                      {items.length === 0 && <tr><td colSpan={selectedPO ? 12 : 13} className="px-3 py-4 text-center text-neutral-400">No items — {selectedPO ? 'link a PO to prefill items' : 'click "+ Add Item" to add items'}</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot><tr className="border-t-2 bg-neutral-50">
                        <td colSpan={11} className="px-3 py-2 text-right font-semibold">Total:</td>
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
          </div>,
          document.body
        )}

        {tolerancePopup && createPortal(
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm" onClick={() => setTolerancePopup(null)}>
            <div className="hms-card w-full max-w-lg space-y-4 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-bold text-red-700">Error: {tolerancePopup.title}</h3>
                <button
                  onClick={() => setTolerancePopup(null)}
                  className="text-xl leading-none text-neutral-400 hover:text-neutral-700"
                  aria-label="Close tolerance error"
                >
                  &times;
                </button>
              </div>

              <div className="space-y-2 rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-900">
                <p><span className="font-semibold">Item:</span> {tolerancePopup.itemLabel} (Row {tolerancePopup.rowNumber})</p>
                <p><span className="font-semibold">Cumulative Received:</span> {formatQty(tolerancePopup.receivedQty)}</p>
                <p><span className="font-semibold">Allowed:</span> {formatQty(tolerancePopup.minAllowed)} - {formatQty(tolerancePopup.maxAllowed)}</p>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => setTolerancePopup(null)}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90"
                >
                  OK
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default GRNPage;


