---
id: deployment
title: Deployment
sidebar_position: 4
description: Step-by-step deployment of the backend on one Ubuntu 22.04 VPS at api.musnid.online, as performed on 2026-10-05.
---

# Deployment

The production backend runs on one VPS at `https://api.musnid.online`; the frontend is
hosted separately on Vercel. The design is recorded in
[ADR 0018](../architecture/decisions/0018-single-vps-deployment.md). This page is the
procedure as it was performed on 2026-10-05, including the problems met on the way.

```
client ──HTTPS──▶ nginx (host, :443, Let's Encrypt)
                    └─HTTP──▶ 127.0.0.1:8011 ─▶ web container (gunicorn + WhiteNoise)
                                                   └─▶ db container (PostgreSQL + pgvector)
```

| Item | Value |
| --- | --- |
| Server | Ubuntu 22.04.5 LTS, 4 cores, 5.8 GiB RAM reported, 118 GB disk, address `104.207.88.52` |
| Hostname | `api.musnid.online`, DNS `A` record at Namecheap |
| Login | `root` with an SSH key only; password login is off |
| Code | `/root/musnid-backend`, cloned with a read-only GitHub deploy key |
| Services | `docker-compose.yml` with the `web` profile, the same file as in development |
| Proxy and TLS | nginx 1.18.0 and certbot from Ubuntu's packages, on the host |
| Static files | WhiteNoise inside gunicorn; nginx proxies everything |
| Open ports | 22, 80, 443. PostgreSQL (5435) and gunicorn (8011) listen on `127.0.0.1` only |

Local development is unaffected: every production setting is off unless its variable is
set (`DJANGO_HTTPS`, `DJANGO_HSTS_SECONDS`, `DJANGO_NUM_PROXIES`).

## How to run the commands

- Commands marked **Mac** run in a terminal on the development machine; all others run in
  an SSH session on the server as `root`.
- Paste **one command at a time** and check its output before the next. Long lines
  pasted into the terminal were wrapped and broke twice (an unclosed quote left the shell
  at a `>` prompt; `Ctrl+C` recovers). Long commands below use short variables for that
  reason.
- Never put the server password in the project's `.env`: Compose loads that file into
  both containers.

## 1. DNS

At the registrar, add a record: type `A`, host `api`, value `104.207.88.52`, TTL
automatic. Leave the `@` and `www` records for the frontend. Check from the Mac:

```bash
dig +short api.musnid.online
```

Expected: `104.207.88.52`. It resolved within minutes.

## 2. SSH key (Mac)

Create a dedicated key without a passphrase, then install it with the root password
(asked once):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/musnid_vps -N "" -C musnid-vps
```

```bash
ssh-copy-id -i ~/.ssh/musnid_vps.pub root@104.207.88.52
```

Expected: `Number of key(s) added: 1`. From now on log in with
`ssh -i ~/.ssh/musnid_vps root@104.207.88.52`. Anyone holding that file can log in;
keep it on the Mac only.

## 3. Let the provider's first-boot upgrade finish

The provider's image runs `/usr/local/bin/debian-based-post-install.sh` at first boot. It
runs `apt upgrade -y` up to three times, two minutes apart, then adds a weekly `fstrim`
cron job and deletes itself. The upgrade stopped on a debconf question about
`/etc/ssh/sshd_config` that nobody could answer, holding the dpkg lock with about 70
packages unpacked but not configured, the new kernel among them. **Do not reboot and do
not run `apt` while this is the case.**

Check whether it is stuck:

```bash
ps -eo pid,etime,args | grep -E "[u]cf|[p]ostinst|[d]ebconf/frontend|[a]pt upgrade"
```

If a `ucf … /etc/ssh/sshd_config` process is listed, tell ucf to keep the current
configuration files without asking:

```bash
echo 'conf_force_conffold=YES' >> /etc/ucf.conf
```

Then stop the frozen question: the `ucf`, `openssh-server.postinst` and
`debconf/frontend` processes, by PID from the listing above. dpkg carries on with the
remaining packages, and the script's next attempt configures `openssh-server`.

```bash
kill <ucf-pid> <postinst-pid> <frontend-pid>
```

The script is finished when this prints nothing:

```bash
ps -eo args | grep "[d]ebian-based-post-install"
```

Then check that no package is left half-configured. `dpkg --audit` exits with success
even when it lists packages, so read its output: it must be empty.

```bash
dpkg --audit
```

Reboot to load the new kernel, then check it after about a minute:

```bash
reboot
```

```bash
uname -r && systemctl is-system-running
```

Expected on 2026-10-05: `5.15.0-198-generic` and `running`.

## 4. Packages, firewall and swap

```bash
apt-get update -q && apt-get install -y -q ufw nginx certbot python3-certbot-nginx git
```

```bash
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw --force enable
```

A 2 GB swap file guards against the out-of-memory killer during image builds:

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
```

```bash
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Ubuntu 22.04 applies security updates with `unattended-upgrades`; automatic reboot is
off, so the server never restarts on its own.

## 5. Docker

From Docker's repository ([Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/)):

```bash
install -m 0755 -d /etc/apt/keyrings
```

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
```

```bash
chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
ARCH=$(dpkg --print-architecture)
```

```bash
URL=https://download.docker.com/linux/ubuntu
```

```bash
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] $URL jammy stable" > /etc/apt/sources.list.d/docker.list
```

```bash
apt-get update -q
```

```bash
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

```bash
docker --version && docker compose version
```

Installed on 2026-10-05: Docker 29.8.2 and Docker Compose v5.6.0. Docker publishes
ports with its own iptables rules, which ufw does not filter; this is safe only because
`docker-compose.yml` binds every port to `127.0.0.1`. Keep it that way.

## 6. SSH: key only

```bash
printf 'PermitRootLogin prohibit-password\nPasswordAuthentication no\n' > /etc/ssh/sshd_config.d/00-musnid.conf
```

The provider's cloud-init file turns password login back on; comment it out:

```bash
sed -i 's/^PasswordAuthentication yes/#&/' /etc/ssh/sshd_config.d/50-cloud-init.conf
```

```bash
sshd -t && systemctl reload ssh && echo SSH-OK
```

Keep the current session open and check from the Mac that a password is refused
(`Permission denied (publickey)`) while the key still works:

```bash
ssh -o PubkeyAuthentication=no root@104.207.88.52
```

The server is used only for the competition, so it runs as `root` with a key; no
separate deploy user was created.

## 7. Code

The repository is private, so the server gets a read-only deploy key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C musnid-vps -q
```

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n' >> ~/.ssh/config
```

```bash
cat ~/.ssh/github_deploy.pub
```

Add that line on GitHub under the repository's *Settings → Deploy keys*, title
`musnid-vps`, with **Allow write access unchecked**. Then:

```bash
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
```

```bash
git clone git@github.com:Sohaib-radi/musnid-backend.git ~/musnid-backend
```

```bash
cd ~/musnid-backend && git log --oneline -1
```

## 8. Production `.env`

Secrets are generated on the server straight into the file, never shown on screen and
never copied from development. Run these one by one in `~/musnid-backend`:

```bash
cp .env.example .env && chmod 600 .env
```

```bash
set_env() { sed -i "s|^$1=.*|$1=$2|" .env; }
```

```bash
set_env DJANGO_SECRET_KEY "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
```

```bash
set_env POSTGRES_PASSWORD "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

```bash
set_env FIELD_ENCRYPTION_KEYS "$(python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
```

Then the plain values, one per command: `set_env POSTGRES_DB musnid`,
`set_env POSTGRES_USER musnid`, `set_env DJANGO_DEBUG ""`,
`set_env DJANGO_ALLOWED_HOSTS api.musnid.online`, `set_env DJANGO_HTTPS True`,
`set_env DJANGO_HSTS_SECONDS 0`, `set_env DJANGO_NUM_PROXIES 1`. Review the result with
the secrets masked:

```bash
grep -E '^[A-Z_]+=' .env | sed -E 's/(SECRET_KEY|PASSWORD|KEYS|API_KEY)=.+/\1=<set>/'
```

| Variable | Production value |
| --- | --- |
| `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `FIELD_ENCRYPTION_KEYS` | generated above |
| `DJANGO_DEBUG` | empty (off) |
| `DJANGO_ALLOWED_HOSTS` | `api.musnid.online` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | empty until the Vercel frontend exists (see [To do](#to-do)) |
| `DJANGO_HTTPS` | `True` |
| `DJANGO_HSTS_SECONDS` | `0` (see [To do](#to-do)) |
| `DJANGO_NUM_PROXIES` | `1` (nginx) |
| `OPENAI_API_KEY` | empty: the key is added encrypted in the admin (step 13) |
| `ASK_DAILY_LIMIT` | `150` (default) |
| `POSTGRES_HOST`, `POSTGRES_PORT` | template values; the `web` container overrides them to `db:5432` |

Full reference: [Configuration](configuration.md).

## 9. Database and application

```bash
docker compose up -d db
```

```bash
docker inspect -f '{{.State.Health.Status}}' musnid_backend_postgres
```

Wait for `healthy`, then build and start the app. Output is hidden until the build ends;
let it run (installing the Python packages is the long part):

```bash
docker compose --profile web up -d --build 2>&1 | tail -5
```

```bash
docker compose logs --tail 15 web
```

Expected: the migrations, then `Listening at: http://0.0.0.0:8000` and three
`Booting worker` lines. Check that Django answers and redirects to HTTPS:

```bash
curl -sI -H 'Host: api.musnid.online' http://127.0.0.1:8011/admin/login/ | head -1
```

Expected: `HTTP/1.1 301 Moved Permanently`. Create the admin account:

```bash
docker compose exec web python manage.py createsuperuser
```

## 10. nginx

```bash
cp deploy/nginx/api.musnid.online.conf /etc/nginx/sites-available/api.musnid.online
```

```bash
ln -s /etc/nginx/sites-available/api.musnid.online /etc/nginx/sites-enabled/ && rm /etc/nginx/sites-enabled/default
```

```bash
nginx -t && systemctl reload nginx && echo NGINX-OK
```

## 11. HTTPS

certbot asks for an email address for expiry notices, and whether to share it with the
EFF (either answer works):

```bash
certbot --nginx -d api.musnid.online --redirect --agree-tos
```

Expected: `Successfully deployed certificate`. certbot adds the 443 server to the nginx
site, turns port 80 into a redirect and installs `certbot.timer`, which renews the
certificate. The first certificate expires on 2027-01-03.

Measured from outside on 2026-10-05: `https://api.musnid.online/admin/login/` answers
200 with `Secure` cookies, `http://` answers 301 to `https://`, the admin CSS and
`/api/docs/` answer 200. `manage.py check --deploy` reports only `security.W004`
(HSTS off).

## 12. Knowledge base

`data/raw/` and `data/processed/` are not in git and PyMuPDF stays off the server, so the
two knowledge tables are copied from the development database. Users, keys and
questions are not copied. **Mac**:

```bash
docker exec musnid_backend_postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --data-only -t knowledge_sourcedocument -t knowledge_sourcechunk' > ~/knowledge.dump
```

```bash
scp -i ~/.ssh/musnid_vps ~/knowledge.dump root@104.207.88.52:~/
```

Both databases must be at the same knowledge migration (`0002_source_document_pdf_url`
on 2026-10-05). On the server, after step 9 created the tables:

```bash
cd ~/musnid-backend && cp ~/knowledge.dump /tmp/k.dump
```

```bash
docker compose exec -T db pg_restore -U musnid -d musnid --data-only < /tmp/k.dump
```

Restored on 2026-10-05: 1 document and 1,432 chunks, all with embeddings, identical to
development (dump of 11,525,760 bytes, same SHA-256 on both machines). Delete the dump
files afterwards.

## 13. Admin setup

In `https://api.musnid.online/admin/`:

1. **Provider API keys**: add the OpenAI key (provider OpenAI, any name, for example
   `production key`). It is stored encrypted; only its last four characters are shown.
2. **Centers**: add a center, approve it with the **Approve** action, then select it and
   run **Make default**.

The default center is required. Without it the flow runs, and is paid for, but the
answer cannot be saved and `POST /api/v1/questions/` returns 503 `unavailable`. That
happened on the first test question.

## 14. Check

**Mac**:

```bash
curl -s -X POST https://api.musnid.online/api/v1/questions/ -H 'Content-Type: application/json' -d '{"text":"ما هو الدليل على وجود الله؟","session_id":"deploy-check"}'
```

Measured on 2026-10-05: 201 in 26.8 s, decision `answer`, 2 sentences kept and 4 removed
by the verifier. Afterwards the `web` container used 389 MiB and `db` 71 MiB, with
4.8 GiB of memory available.

## Updating

```bash
cd ~/musnid-backend && git pull
```

```bash
docker compose --profile web up -d --build 2>&1 | tail -5
```

```bash
docker compose logs --tail 15 web
```

The image is rebuilt (including `collectstatic`) and the container restarts with
`migrate`. Answers in progress during the restart fail; avoid updates while judges are
testing.

## To do

Recommended for the competition, not done yet:

| Item | Why | How |
| --- | --- | --- |
| CORS for the frontend | Browsers block the Vercel frontend until its origin is listed | Set `DJANGO_CORS_ALLOWED_ORIGINS` to the Vercel origin(s) in `.env`, then `docker compose --profile web up -d` |
| OpenAI spending limit | The ask API is public and each answer costs tokens | A monthly limit in the OpenAI account (Billing → Limits) |
| Daily limit | 150 questions per day may be too few or too many during judging | Set `ASK_DAILY_LIMIT` to match the OpenAI limit |
| Daily backups | The database exists only on this server | A cron job: `pg_dump -Fc` from the `db` container to `~/backups`, keeping 14 days; copy the dumps off the server |
| Uptime alert | Know when the site is down while judges test | An external HTTPS check on `/api/docs/`, for example UptimeRobot |
| HSTS | Browsers would then refuse plain HTTP to the host | Raise `DJANGO_HSTS_SECONDS` in steps (`300`, `86400`, `31536000`) once HTTPS has been stable; no `includeSubDomains`, no `preload` |
| Delete the knowledge dumps | No longer needed | `~/knowledge.dump` on the Mac and the server, `/tmp/k.dump` on the server |

## Known limitations

- One server: no failover. A VPS outage stops the service until it is restored.
- No backups yet (see [To do](#to-do)).
- Restarting `web` interrupts questions being answered (19.8 to 45.6 s each,
  [ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)).
- `conf_force_conffold=YES` in `/etc/ucf.conf` keeps the local configuration file on every
  future package upgrade without asking; new upstream defaults are not merged.
