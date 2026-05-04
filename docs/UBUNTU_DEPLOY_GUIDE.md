# Ubuntu Server Deployment Guide

This checklist applies the latest changes on an Ubuntu server running the inventory management system.

## 1) Pre-flight

- Confirm you have SSH access and sudo privileges.
- Confirm you know the repo path on the server (example: /srv/apps/inventory-management-system-full-project).
- Confirm active service names (example: ims-backend, ims-frontend, nginx).

## 2) Backups (recommended)

- Backup the database.
- Backup the current frontend build directory (if static files are served).

## 3) Update the code

```bash
cd /srv/apps/inventory-management-system-full-project
sudo git fetch --all
sudo git pull
```

## 4) Backend update

```bash
cd /srv/apps/inventory-management-system-full-project/backend
source .venv/bin/activate
pip install -r requirements.txt
```

Notes:
- No new DB migration files were added for this update. Skip DB migrations unless you have custom steps.

Restart the backend service (use your actual service name):

```bash
sudo systemctl restart ims-backend
sudo systemctl status ims-backend --no-pager
```

## 5) Frontend update

```bash
cd /srv/apps/inventory-management-system-full-project/frontend
npm ci
npm run build
```

If the frontend is served by Nginx or another web server, copy or sync the build output (example path):

```bash
sudo rsync -av --delete ./dist/ /var/www/ims-frontend/
```

Restart the frontend web service if needed (use your actual service name):

```bash
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager
```

## 6) Verification

- Open the app and verify:
  - Receivables/Payables show readable notes and allocation labels.
  - View modals work for both Customer and Supplier payments.
  - Admin-only actions still enforce permissions.

## 7) Troubleshooting

- Backend logs (example):
  ```bash
  sudo journalctl -u ims-backend -n 200 --no-pager
  ```
- Nginx logs (example):
  ```bash
  sudo journalctl -u nginx -n 200 --no-pager
  ```

Adjust service names and paths to match your server setup.
