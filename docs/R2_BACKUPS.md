# Second off-server backup copy in Cloudflare R2

`r2put.py` (11 Nov 2026) sends the newest two nightly backups (records only: no secrets, no videos; see `backup.py`) to a Cloudflare R2 bucket. It is a second copy next to `deploy/backup_push.sh` (private GitHub repo). It is not scheduled until the first real run works.

## Owner steps (about five minutes, in the Cloudflare dashboard; no value is ever pasted into a chat)
1. Cloudflare dashboard > **R2 Object Storage** > switch R2 on (Cloudflare may ask for a payment card; the free tier is far above the size of these archives, but check the current R2 price page).
2. **Create bucket**: name `studio-backups`, leave it private.
3. R2 > **Manage API tokens** > **Create API token**: permission **Object Read & Write**, limited to the bucket `studio-backups` only. Copy the Access Key ID and Secret Access Key shown once.
4. On the server, add four lines to `~/studio/.env` yourself (the account id is on the R2 overview page):
   `R2_ACCOUNT_ID=...`  `R2_BUCKET=studio-backups`  `R2_ACCESS_KEY_ID=...`  `R2_SECRET_ACCESS_KEY=...`

## Check, then first upload (an assistant can do these once step 4 is done)
- `python r2put.py --dry` lists the files it would send and sends nothing.
- `python r2put.py` sends them and writes `backups/last_r2.txt`.
- Refusals are by design: a backup older than 30 hours, a file that is not valid gzip, a link inside `backups/`, or any file not named `backup-YYYYMMDD.tar.gz`. A refused upload shows only the HTTP status, never a key.

## Limits
- Live signing against R2 has not been run yet (the unit tests check the signing key against AWS's published example, not the service).
- Keys stay in `.env` (never committed). Rotate the R2 token in the dashboard if it is ever exposed.
