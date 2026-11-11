# Amy WordPress plugin auto-deploy (Hostinger)

When `main` changes under `app/public/wp-content/plugins/amy-agent/`, GitHub Actions rsyncs **only that folder** to the live WordPress plugin path on Hostinger (`ogcnewfinity.com`).

This is separate from **Dokploy** auto-deploy of `amy-agent-service/`. Do not change the Dokploy build path or wire Dokploy to sync the WP plugin — Hostinger is the WP host; Dokploy stays the Python service host.

## What gets deployed

| Source (repo) | Destination (server) |
| --- | --- |
| `app/public/wp-content/plugins/amy-agent/` | `$HOSTINGER_PLUGIN_PATH` (must end with `/amy-agent`) |

Triggers:

- `push` to `main` that touches the plugin path (or this workflow file)
- Manual **Actions → Deploy Amy Plugin → Run workflow** (`workflow_dispatch`)

`--delete` is used so removed plugin files disappear on the server. The remote path **must** be the `amy-agent` plugin directory only.

## One-time setup (Abdulla)

### 1. Enable SSH on Hostinger

1. Open **hPanel** for `ogcnewfinity.com`.
2. **Advanced → SSH Access** — enable SSH if needed; note **host**, **port**, and **username**.
3. Typical remote plugin path (confirm in File Manager):

   ```text
   /home/<USER>/domains/ogcnewfinity.com/public_html/wp-content/plugins/amy-agent
   ```

   If the site document root is not `public_html`, adjust accordingly — the path must still end with `/amy-agent`.

### 2. Create a deploy key (do not commit it)

On a secure machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-amy-plugin-deploy" -f ./amy-plugin-deploy -N ""
```

- Add **`amy-plugin-deploy.pub`** to Hostinger SSH keys (hPanel SSH Access / authorized keys).
- Keep **`amy-plugin-deploy`** (private) only for the GitHub secret below; delete the local copy after adding the secret.

Restrict the key to this use if Hostinger/your process allows (deploy-only account or forced command is ideal; shared hosting often only supports a normal SSH user).

### 3. Add GitHub repository secrets

Repo: [WaelOGC/plugin-amy-agent](https://github.com/WaelOGC/plugin-amy-agent) → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret name | Example / notes |
| --- | --- |
| `HOSTINGER_SSH_HOST` | SSH hostname from hPanel (often `ssh.hostinger.com` or a server hostname) |
| `HOSTINGER_SSH_USER` | SSH username from hPanel |
| `HOSTINGER_SSH_PRIVATE_KEY` | Full private key PEM (`-----BEGIN … PRIVATE KEY-----` …), including newlines |
| `HOSTINGER_PLUGIN_PATH` | Absolute path ending in `/amy-agent` (see above) |
| `HOSTINGER_SSH_PORT` | **Optional.** Default `22` if unset. Set if hPanel shows another port |

Do **not** put these values in the repo, `.env`, or PR descriptions.

### 4. Smoke-test

1. GitHub → **Actions → Deploy Amy Plugin → Run workflow** (branch `main`).
2. Confirm the job is green.
3. In wp-admin → **Plugins**, confirm **Amy Agent** version/files match `main`.
4. Optional: touch a harmless file under the plugin on `main` and confirm a push-triggered run.

If the job fails with “Missing GitHub secret”, complete step 3. If `Permission denied (publickey)`, the private key secret and Hostinger authorized key do not match.

Do **not** pass `-o IdentitiesOnly=yes` in the rsync SSH options when using `webfactory/ssh-agent` (key only in the agent, no `IdentityFile`): on current OpenSSH that blocks agent-only keys and causes `Permission denied (publickey)` even when the correct key is loaded.

## Monorepo layout (why not Dokploy alone)

```text
plugin-amy-agent/
├── amy-agent-service/          → Dokploy GitHub autodeploy (unchanged)
└── app/public/wp-content/plugins/amy-agent/  → this workflow → Hostinger WP
```

Dokploy builds the Python service from `/amy-agent-service`. It does not reliably sync arbitrary Hostinger `wp-content` paths. GitHub Actions + SSH/rsync is the reliable path for the plugin folder.

## Ops notes

- Plugin-only path filters avoid running this job when only `amy-agent-service/` changes.
- Concurrency group `deploy-amy-plugin-hostinger` prevents overlapping rsyncs from stomping each other (`cancel-in-progress: false`).
- After deploy, clear LiteSpeed/Hostinger caches if the admin UI looks stale.
- WordPress options and DB are **not** overwritten by rsync — only plugin files.
