import { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';
import { useAuthStore } from '../store/auth';
import { superAdminApi, PlatformCompany } from '../api/superAdmin';

const FIELD_GROUPS: { title: string; fields: { key: keyof PlatformCompany; label: string }[] }[] = [
  {
    title: 'Company',
    fields: [
      { key: 'name', label: 'Company Name' },
      { key: 'legal_name', label: 'Legal Name' },
      { key: 'company_director_name', label: 'Director Name' },
      { key: 'company_director_contact', label: 'Director Contact' },
      { key: 'website', label: 'Website' },
      { key: 'phone', label: 'Phone' },
      { key: 'email', label: 'Email' },
    ],
  },
  {
    title: 'Tax / Registration',
    fields: [
      { key: 'gstin_status', label: 'GST Registration Status' },
      { key: 'gstin', label: 'GSTIN' },
      { key: 'pan', label: 'PAN' },
      { key: 'import_export_number', label: 'Import & Export Number' },
      { key: 'state_code', label: 'State Code' },
    ],
  },
  {
    title: 'Address',
    fields: [
      { key: 'address_line1', label: 'Address Line 1' },
      { key: 'address_line2', label: 'Address Line 2' },
      { key: 'city', label: 'City' },
      { key: 'state', label: 'State' },
      { key: 'pincode', label: 'Pincode' },
      { key: 'country', label: 'Country' },
    ],
  },
  {
    title: 'Bank Details',
    fields: [
      { key: 'bank_name', label: 'Bank Name' },
      { key: 'account_holder_name', label: 'Account Holder' },
      { key: 'bank_branch', label: 'Branch' },
      { key: 'bank_account_no', label: 'Account Number' },
      { key: 'bank_ifsc', label: 'IFSC' },
    ],
  },
];

const GSTIN_STATUS_OPTIONS = [
  { value: 'registered', label: 'Registered' },
  { value: 'non-registered', label: 'Non-Registered' },
  { value: 'composition', label: 'Composition Scheme' },
];

const CompanyProfilePage = () => {
  const user = useAuthStore((s) => s.user);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { register, handleSubmit, reset } = useForm<PlatformCompany>();
  const logoInput = useRef<HTMLInputElement>(null);
  const ambInput = useRef<HTMLInputElement>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [ambPreview, setAmbPreview] = useState<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ['admin', 'company-profile'],
    queryFn: superAdminApi.getCompanyProfile,
    enabled: !!user?.is_super_admin,
  });

  useEffect(() => {
    if (profileQuery.data) {
      reset(profileQuery.data);
      setLogoPreview(profileQuery.data.logo_data_url ?? null);
      setAmbPreview(profileQuery.data.ambassador_logo_data_url ?? null);
    }
  }, [profileQuery.data, reset]);

  const saveMutation = useMutation({
    mutationFn: (payload: PlatformCompany) => superAdminApi.updateCompanyProfile(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'company-profile'] });
      toast.success('Company profile saved.');
      navigate('/admin/tenants'); // back to ERP Customers after a successful save
    },
  });

  const logoMutation = useMutation({
    mutationFn: (file: File) => superAdminApi.uploadCompanyLogo(file),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin', 'company-profile'] }); toast.success('Logo updated.'); },
  });
  const ambMutation = useMutation({
    mutationFn: (file: File) => superAdminApi.uploadCompanyAmbassadorLogo(file),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin', 'company-profile'] }); toast.success('Ambassador logo updated.'); },
  });

  if (!user?.is_super_admin) {
    return <AppLayout title="Company Profile"><PageError message="Super Admin privileges are required." /></AppLayout>;
  }
  if (profileQuery.isLoading) {
    return <AppLayout title="Company Profile"><PageLoading message="Loading profile..." /></AppLayout>;
  }
  if (profileQuery.isError) {
    return <AppLayout title="Company Profile"><PageError message="Failed to load company profile." /></AppLayout>;
  }

  const onLogo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) { setLogoPreview(URL.createObjectURL(f)); logoMutation.mutate(f); }
  };
  const onAmb = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) { setAmbPreview(URL.createObjectURL(f)); ambMutation.mutate(f); }
  };

  return (
    <AppLayout title="Super Admin — Company Profile">
      <form onSubmit={handleSubmit((v) => saveMutation.mutate(v))} className="space-y-6">
        {/* Logos */}
        <div className="hms-card p-5">
          <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">Logos</h2>
          <div className="flex flex-wrap gap-8">
            <div className="space-y-2">
              <p className="hms-label">Company Logo</p>
              <div className="flex h-24 w-24 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50 overflow-hidden">
                {logoPreview ? <img src={logoPreview} alt="logo" className="h-full w-full object-contain" /> : <span className="material-icons text-neutral-300">image</span>}
              </div>
              <input ref={logoInput} type="file" accept="image/png,image/jpeg" className="hidden" onChange={onLogo} />
              <button type="button" onClick={() => logoInput.current?.click()} className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-50">Upload Logo</button>
            </div>
            <div className="space-y-2">
              <p className="hms-label">Ambassador Logo</p>
              <div className="flex h-24 w-24 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50 overflow-hidden">
                {ambPreview ? <img src={ambPreview} alt="ambassador" className="h-full w-full object-contain" /> : <span className="material-icons text-neutral-300">image</span>}
              </div>
              <input ref={ambInput} type="file" accept="image/png,image/jpeg" className="hidden" onChange={onAmb} />
              <button type="button" onClick={() => ambInput.current?.click()} className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-50">Upload Ambassador Logo</button>
            </div>
          </div>
        </div>

        {/* Field groups */}
        {FIELD_GROUPS.map((group) => (
          <div key={group.title} className="hms-card p-5">
            <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">{group.title}</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {group.fields.map((f) => (
                <div key={f.key}>
                  <label className="hms-label">{f.label}</label>
                  {f.key === 'gstin_status' ? (
                    <select className="hms-input" {...register(f.key)}>
                      {GSTIN_STATUS_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  ) : (
                    <input className="hms-input" {...register(f.key)} />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="flex justify-end">
          <button type="submit" disabled={saveMutation.isPending} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-bold text-white hover:bg-primary/90 disabled:opacity-60">
            {saveMutation.isPending ? 'Saving…' : 'Save Profile'}
          </button>
        </div>
      </form>
    </AppLayout>
  );
};

export default CompanyProfilePage;
