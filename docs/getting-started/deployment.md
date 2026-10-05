---
id: deployment
title: Deployment
sidebar_position: 4
description: Running the backend on one Ubuntu 22.04 VPS at api.musnid.online with Docker Compose, nginx and Let's Encrypt.
---

# Deployment

The production backend runs on a single VPS at `https://api.musnid.online`. The frontend
is hosted separately on Vercel. The design is recorded in
[ADR 0018](../architecture/decisions/0018-single-vps-deployment.md).

```
client ──HTTPS──▶ nginx (host, :443, Let's Encrypt)
                    └─HTTP──▶ 127.0.0.1:8011 ─▶ web container (gunicorn + WhiteNoise)
                                                   └─▶ db container (PostgreSQL + pgvector)
```

| Item | Value |
| --- | --- |
| Server | Ubuntu 22.04 LTS, 4 cores, 6 GB RAM, 120 GB SSD |
| Hostname | `api.musnid.online` (DNS `A` record to the VPS address) |
| Services | `docker-compose.yml`, the same file as local development, with the `web` profile |
| Proxy and TLS | nginx and certbot from Ubuntu's packages, on the host |
| Static files | WhiteNoise inside gunicorn; nginx proxies everything |
| Open ports | 22, 80, 443. PostgreSQL (5435) and gunicorn (8011) listen on 127.0.0.1 only |

Local development is unaffected: every production setting is off unless its variable is
set (`DJANGO_HTTPS`, `DJANGO_HSTS_SECONDS`, `DJANGO_NUM_PROXIES`).

## 1. DNS

At the domain registrar, create an `A` record `api` → the VPS IPv4 address. Wait until
`dig +short api.musnid.online` returns that address; certbot fails before then.

## 2. Server access

As `root` on the fresh server, create a deploy user that uses an SSH key:

```bash
adduser musnid
usermod -aG sudo musnid
mkdir -p /home/musnid/.ssh
cp ~/.ssh/authorized_keys /home/musnid/.ssh/   # requires the key to be on root already
chown -R musnid:musnid /home/musnid/.ssh && chmod 700 /home/musnid/.ssh
```

Log in as `musnid` with the key in a second terminal before going on. Then, in
`/etc/ssh/sshd_config`, set `PermitRootLogin no` and `PasswordAuthentication no`, and run
`sudo systemctl restart ssh`.

## 3. Base system

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ufw nginx certbot python3-certbot-nginx git
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Ubuntu 22.04 installs `unattended-upgrades` by default, which applies security updates.

A 2 GB swap file guards against the out-of-memory killer during image builds and
migrations:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. Docker

Install Docker Engine and the Compose plugin from Docker's repository, following
[Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/), then let
the deploy user run it:

```bash
sudo usermod -aG docker musnid   # log out and in again
docker compose version
```

Docker publishes ports by writing its own iptables rules, which ufw does not filter.
That is safe here only because `docker-compose.yml` binds every port to `127.0.0.1`;
keep it that way.

## 5. Code and `.env`

If the repository is private, add a read-only deploy key: run
`ssh-keygen -t ed25519 -C musnid-vps`, add `~/.ssh/id_ed25519.pub` under the repository's
*Settings → Deploy keys*, then clone:

```bash
git clone git@github.com:<owner>/musnid-backend.git ~/musnid-backend
cd ~/musnid-backend
cp .env.example .env && chmod 600 .env
```

Generate new secrets on the server; never copy the development ones. Each command prints
one value (all URL-safe, as Compose requires):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"            # DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"            # POSTGRES_PASSWORD
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"  # FIELD_ENCRYPTION_KEYS
```

Production values in `.env` (full reference: [Configuration](configuration.md)):

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | generated |
| `DJANGO_DEBUG` | empty (off) |
| `DJANGO_ALLOWED_HOSTS` | `api.musnid.online` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | the Vercel origin(s), for example `https://musnid.online` |
| `DJANGO_HTTPS` | `True` |
| `DJANGO_HSTS_SECONDS` | `0` at first, see [step 8](#8-hsts) |
| `DJANGO_NUM_PROXIES` | `1` (nginx) |
| `FIELD_ENCRYPTION_KEYS` | generated |
| `OPENAI_API_KEY` | the key, or empty and added later in the admin |
| `POSTGRES_DB`, `POSTGRES_USER` | any names |
| `POSTGRES_PASSWORD` | generated |

## 6. Database and application

Start PostgreSQL alone, then the application. The `web` command runs `migrate` and
`createcachetable` before gunicorn starts:

```bash
docker compose up -d db
docker compose --profile web up -d --build
docker compose logs --tail 20 web
docker compose exec web python manage.py createsuperuser
curl -sI -H 'Host: api.musnid.online' http://127.0.0.1:8011/admin/login/ | head -1   # 301: DJANGO_HTTPS works
```

### Knowledge base

`data/raw/` and `data/processed/` are not in git, so the new database has no sources and
every question is answered as not covered. Copy only the two knowledge tables from the
development database; production keeps its own users, keys and questions.

On the development machine:

```bash
docker exec musnid_backend_postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --data-only \
     -t knowledge_sourcedocument -t knowledge_sourcechunk' > knowledge.dump
scp knowledge.dump musnid@api.musnid.online:~/
```

On the server, after `migrate` has created the tables (both code versions must be the
same commit):

```bash
docker exec -i musnid_backend_postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --no-owner' < ~/knowledge.dump
docker compose exec web python manage.py search_test "<a question>"
rm ~/knowledge.dump
```

## 7. nginx and HTTPS

```bash
sudo cp deploy/nginx/api.musnid.online.conf /etc/nginx/sites-available/api.musnid.online
sudo ln -s /etc/nginx/sites-available/api.musnid.online /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.musnid.online --redirect
```

certbot adds the 443 server with the certificate, turns port 80 into a redirect and
installs a systemd timer that renews the certificate; `sudo certbot renew --dry-run`
checks it. Then open `https://api.musnid.online/admin/` and log in.

`docker compose exec web python manage.py check --deploy` lists the remaining hardening
warnings. With HSTS at `0` it reports `security.W004` until step 8. After step 8 only
`security.W005` and `security.W021` remain (measured with these settings on 2026-10-05);
they are expected, since `includeSubDomains` and `preload` are deliberately off.

## 8. HSTS

HSTS tells browsers to refuse plain HTTP to the host for `DJANGO_HSTS_SECONDS`, and a
browser keeps that promise even if HTTPS later breaks. Raise it in steps once HTTPS has
worked for a while: `300`, then `86400`, then `31536000` (one year). After each change:

```bash
docker compose --profile web up -d
```

`includeSubDomains` and `preload` are not set: other `musnid.online` hosts are not under
this server's control.

## 9. Backups

A daily compressed dump, keeping 14 days. Run `crontab -e` as `musnid` and add:

```cron
30 3 * * * mkdir -p ~/backups && docker exec musnid_backend_postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > ~/backups/musnid-$(date +\%F).dump && find ~/backups -name 'musnid-*.dump' -mtime +14 -delete
```

The dumps stay on the same disk; copy them off the server regularly, since a lost VPS
loses them too. Restore with `pg_restore --clean --no-owner` into the `db` container.

## Updating

```bash
cd ~/musnid-backend
git pull
docker compose --profile web up -d --build
docker compose logs --tail 20 web
```

The image is rebuilt (including `collectstatic`) and the container restarts with
`migrate`. Requests in flight during the restart fail; there is no zero-downtime
rollout.

## Known limitations

- One server: no failover. A VPS outage stops the service until it is restored.
- Backups live on the VPS until copied elsewhere.
- Restarting `web` interrupts questions being answered (each takes 20 to 45 s,
  [ADR 0017](../architecture/decisions/0017-anonymous-ask-api.md)).
- Memory per gunicorn worker has not been measured on the VPS yet; check it with
  `docker stats` after the first questions and adjust `--workers` if needed.
