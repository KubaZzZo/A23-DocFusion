# DocFusion VPS deployment notes

These files are examples for a demo VPS. Keep existing unrelated containers, such as `new-api`, untouched.

## Users and directories

```bash
useradd --system --home /opt/docfusion --shell /usr/sbin/nologin docfusion
install -d -o docfusion -g docfusion -m 750 /opt/docfusion /data/docfusion/tasks /var/log/docfusion
install -d -m 750 /etc/docfusion
```

## Secrets

Put server-side model credentials in environment files, not in desktop `settings.json`.

```bash
install -m 600 /dev/null /etc/docfusion/docfusion-api.env
printf 'OPENAI_API_KEY=%s\nOPENAI_BASE_URL=https://maolaoapi.com/v1\nLLM_PROVIDER=openai\n' 'replace-me' > /etc/docfusion/docfusion-api.env

install -m 600 /dev/null /etc/docfusion/docfusion-toolkit.env
printf 'DOCFUSION_EXECUTION_BACKEND=local\n' > /etc/docfusion/docfusion-toolkit.env
printf '%s\n' 'replace-token' > /etc/docfusion/toolkit-token.txt
chmod 600 /etc/docfusion/toolkit-token.txt
chmod 600 /root/.codex/maolao.env
```

## Reverse proxy

Install `nginx-docfusion.conf` under `/etc/nginx/sites-available/`, symlink it into `sites-enabled`, then point the desktop client at the public domain:

- Main API: `https://docx.zhuoruan.xyz/api`
- Toolkit API: `https://docx.zhuoruan.xyz/toolkit`

Issue the certificate after DNS points `docx.zhuoruan.xyz` to the VPS:

```bash
certbot --nginx -d docx.zhuoruan.xyz
```
