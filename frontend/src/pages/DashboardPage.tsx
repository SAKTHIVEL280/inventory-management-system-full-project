/**
 * Dashboard Page
 *
 * Main page after login - shows user info and provides navigation.
 */

import { useAuthStore } from '../store/auth';
import { usePermissions } from '../hooks/usePermissions';
import { Link } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import {
  Building2,
  Users,
  Warehouse,
  ShoppingCart,
  BarChart3,
  ChevronRight,
  Settings,
  Users as UsersIcon,
  User,
  Truck,
  Package,
  Download,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { getDashboardStats, type DashboardStats as APIDashboardStats } from '../api/reports';

interface ModuleSection {
  title: string;
  description: string;
  icon: React.ReactNode;
  items: { label: string; to: string; permission?: string; icon: React.ReactNode }[];
}

interface DashboardStats {
  totalProducts: number;
  totalCustomers: number;
  totalSuppliers: number;
  lowStockProducts: number;
  pendingPurchaseOrders: number;
  pendingSalesOrders: number;
}

const DashboardPage = () => {
  const user = useAuthStore((state) => state.user);
  const { can } = usePermissions();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data: APIDashboardStats = await getDashboardStats();
        setStats({
          totalProducts: data.total_products,
          totalCustomers: data.total_customers,
          totalSuppliers: data.total_suppliers,
          lowStockProducts: data.low_stock_count,
          pendingPurchaseOrders: data.pending_purchase_orders,
          pendingSalesOrders: data.pending_sales_orders,
        });
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
        setStats({
          totalProducts: 0,
          totalCustomers: 0,
          totalSuppliers: 0,
          lowStockProducts: 0,
          pendingPurchaseOrders: 0,
          pendingSalesOrders: 0,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  const quickLinkClassName =
    'group flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm font-semibold text-neutral-700 transition hover:border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';

  const sections: ModuleSection[] = [
    {
      title: 'Administration',
      description: 'System and user management',
      icon: <Building2 size={20} aria-hidden="true" />,
      items: [
        { label: 'Company Settings', to: '/company', permission: 'company_read', icon: <Settings size={18} /> },
        { label: 'User Management', to: '/users', permission: 'users_read', icon: <UsersIcon size={18} /> },
      ],
    },
    {
      title: 'Operations',
      description: 'Partners and inventory',
      icon: <Warehouse size={20} aria-hidden="true" />,
      items: [
        { label: 'Customers', to: '/customers', permission: 'customers_read', icon: <User size={18} /> },
        { label: 'Suppliers', to: '/suppliers', permission: 'suppliers_read', icon: <Truck size={18} /> },
        { label: 'Products & Stock', to: '/products', permission: 'products_read', icon: <Package size={18} /> },
      ],
    },
    {
      title: 'Sales & Procurement',
      description: 'Orders and transactions',
      icon: <ShoppingCart size={20} aria-hidden="true" />,
      items: [
        { label: 'Purchase Orders', to: '/purchase-orders', permission: 'purchase_orders_read', icon: <Download size={18} /> },
      ],
    },
    {
      title: 'Reporting',
      description: 'Analytics and insights',
      icon: <BarChart3 size={20} aria-hidden="true" />,
      items: [
        { label: 'Reports', to: '/reports', permission: 'reports_read', icon: <BarChart3 size={18} /> },
      ],
    },
  ];

  const filteredSections = sections.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || can(item.permission)),
  })).filter((section) => section.items.length > 0);

  return (
    <AppLayout title="Dashboard">
      <div className="space-y-6">
        {/* Business Stats Cards */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Products</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{loading ? '-' : stats?.totalProducts ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Products in catalog</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Package size={20} className="text-primary" aria-hidden="true" />
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Customers</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{loading ? '-' : stats?.totalCustomers ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Active customers</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Users size={20} className="text-success" aria-hidden="true" />
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Suppliers</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{loading ? '-' : stats?.totalSuppliers ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Active suppliers</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Truck size={20} className="text-primary" aria-hidden="true" />
              </div>
            </div>
          </article>
        </section>

        {/* Secondary Stats Row */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Low Stock Items</p>
                <p className="mt-3 text-2xl font-bold text-warning">{loading ? '-' : stats?.lowStockProducts ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Need restocking</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-warning/10">
                <AlertTriangle size={20} className="text-warning" aria-hidden="true" />
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Pending Purchase Orders</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{loading ? '-' : stats?.pendingPurchaseOrders ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Awaiting delivery</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Download size={20} className="text-primary" aria-hidden="true" />
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Pending Sales Orders</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{loading ? '-' : stats?.pendingSalesOrders ?? 0}</p>
                <p className="mt-1 text-xs text-neutral-500">Awaiting fulfillment</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <CheckCircle2 size={20} className="text-success" aria-hidden="true" />
              </div>
            </div>
          </article>
        </section>

        {/* Module Sections by Permission */}
        {filteredSections.map((section, idx) => (
          <section key={idx} className="hms-card overflow-hidden">
            <div className="border-b border-neutral-200 bg-gradient-to-r from-neutral-50 to-white px-6 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  {section.icon}
                </div>
                <div>
                  <h2 className="font-display text-lg font-bold text-neutral-900">{section.title}</h2>
                  <p className="text-xs text-neutral-500">{section.description}</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 p-6 md:grid-cols-2 lg:grid-cols-3">
              {section.items.map((item) => (
                <Link
                  key={item.label}
                  to={item.to}
                  className={quickLinkClassName}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-neutral-500" aria-hidden="true">
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                  </span>
                  <ChevronRight size={16} className="text-neutral-400 transition group-hover:translate-x-1 group-hover:text-primary" />
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </AppLayout>
  );
};

export default DashboardPage;
