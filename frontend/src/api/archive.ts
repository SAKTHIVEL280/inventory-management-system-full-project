import { apiClient } from './client';

export interface ArchiveModuleAlert {
  key: string;
  label: string;
  retention_days: number;
  purge_allowed: boolean;
  total_archived: number;
  due_soon: number;
  overdue: number;
}

export interface ArchiveLoginAlertsResponse {
  requires_attention: boolean;
  modules: ArchiveModuleAlert[];
  actionable_modules: ArchiveModuleAlert[];
  protected_modules: ArchiveModuleAlert[];
  message: string;
  default_action: string;
  policy: {
    no_auto_hard_delete_for: string[];
    review_window_days: number;
  };
}

export interface ArchivePurgePreviewResponse {
  modules: ArchiveModuleAlert[];
  purge_candidates: number;
  expected_confirmation_text: string;
  warning: string;
}

export interface ArchivePurgeConfirmResponse {
  deleted: number;
  skipped: number;
  protected_modules_kept_archived: string[];
  message: string;
}

class ArchiveApiClient {
  async getLoginAlerts() {
    return apiClient.get<ArchiveLoginAlertsResponse>('/api/v2/archive/login-alerts');
  }

  async getPurgePreview() {
    return apiClient.get<ArchivePurgePreviewResponse>('/api/v2/archive/purge-preview');
  }

  async confirmPurge(confirmation_text: string) {
    return apiClient.post<ArchivePurgeConfirmResponse>('/api/v2/archive/purge-confirm', { confirmation_text });
  }
}

export const archiveApi = new ArchiveApiClient();

