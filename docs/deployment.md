# Deploy Blog-Gen on one server

This guide runs the built frontend, API, worker and PostgreSQL on one Docker host. Use Linux or WSL2 with Bash, Docker and the Compose v2 plugin (`docker compose`). The host does not need Python or Node. A domain is optional for a local preview and required for the public HTTPS setup below.

The production stack has its own Compose project and named volumes. It does not automatically import an existing development database or uploads. Keep the same project name and deployment env file when updating an installation.

## Start a local preview

From the repository root:

```bash
./deploy.sh init
./deploy.sh up
./deploy.sh create-user you@example.com
```

The initializer creates `.env.production` with independent random database and signing secrets, file permissions `0600`, and registration disabled. It refuses to overwrite an existing file. The account command prompts for a password without putting it in shell history or process arguments.

Open [http://localhost:8080](http://localhost:8080). Draft editing, revisions and account login work before you configure generation providers. The first image build downloads dependencies; later builds reuse unchanged layers. `up` returns an error if migrations or health checks fail.

## Enable generation

Edit `.env.production`:

- Set at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or use `USE_LOCAL_LLM=true` with a reachable Ollama service.
- Add the exact cloud provider/model identifiers and current USD rates to `LLM_PRICING_JSON`. Its format is documented in `backend/.env.example`. Empty or unknown pricing blocks cloud generation. These are generation LLM estimates, with the exclusions described in the README.
- Set `FIRECRAWL_API_KEY` for web research and style URL scraping. Leave it empty when those features are unused.
- Set `PINECONE_API_KEY` for document indexing and retrieval. Embeddings also need OpenAI or an available local embedding model; local embeddings still use Pinecone for vector storage.
- Set `DEFAULT_MONTHLY_LIMIT_USD` for new accounts and `WORKER_CONCURRENCY` for the worker's parallel jobs. Existing account limits do not change when the default changes.

Then run `./deploy.sh up` again. Settings are shared by the API, migration service and worker. They are not baked into the images. Preflight validates format and reports missing capabilities; it does not contact providers or prove that a key, model, embedding dimension or balance is valid.

Inside Docker, `localhost` means the container itself. `host.docker.internal` is configured for reaching host Ollama, which must accept connections from the Docker network. Keep Ollama behind your host firewall. Alternatively point `OLLAMA_BASE_URL` at a private reachable server. Model requirements determine the machine capacity needed for Ollama.

## Publish with your domain

1. Point the domain's DNS A record (and AAAA only if IPv6 is actually configured) at your server. Allow inbound TCP ports 80 and 443.
2. Edit these values in `.env.production`:

   ```dotenv
   SITE_ADDRESS=blog.example.com
   PUBLIC_BIND_ADDRESS=0.0.0.0
   HTTP_PORT=80
   HTTPS_PORT=443
   ```

3. Run `./deploy.sh up` and open your domain using HTTPS. Caddy requests and renews certificates and redirects HTTP to HTTPS when the domain and network prerequisites are satisfied. Its certificate data persists in a named volume. See [Caddy's HTTPS requirements](https://caddyserver.com/docs/automatic-https).

The default preview binds only to loopback and uses HTTP. Do not use that preview configuration as an internet deployment. If another reverse proxy already owns ports 80/443, keep this app bound to loopback, configure your existing proxy to forward the domain to the chosen HTTP port, and manage TLS there. Do not publish the API or database ports separately.

The frontend calls `/api/v1` on the same origin for REST and event streams, so it needs no production API hostname or CORS edits. The proxy forwards event streams immediately. API proxy headers are trusted inside this private Compose network; only the frontend publishes host ports. Direct visits to routes such as `/drafts/ID` return the SPA. Versioned assets are cached; the HTML entry point is revalidated.

## Operate and update

```bash
./deploy.sh status
./deploy.sh logs worker
./deploy.sh check
./deploy.sh backup
# Update the checkout to your reviewed release, preserving .env.production.
./deploy.sh up
```

`check` builds the backend if needed and validates settings without printing secrets. `status` includes API, worker and web container health. `up` builds and validates first, then stops the application writers, re-runs migrations and starts healthy services. Updates have a short maintenance window; this setup does not provide rolling deploys. Run only one deployment/backup/restore operation at a time.

If a build or preflight fails, the old services remain running. If a migration fails, the application stays stopped; inspect logs and correct the migration before restarting. Do not assume that checking out old application code can reverse a schema migration. Restore a tested pre-upgrade backup when the schema is incompatible.

`./deploy.sh down` stops the stack without deleting its named volumes. Do not add `--volumes` or run volume-pruning commands against an installation you need to keep. Changing the database password in the env file does not change the password inside an already initialized PostgreSQL volume; perform an explicit database role password rotation and update the file together. Changing the signing secret invalidates existing sessions.

Production API/worker processes run as a non-root user with a read-only application filesystem. Uploads and detailed LLM logs have named volumes. Container stdout/stderr logs rotate at 3 × 10 MB per container. Detailed LLM logs can contain prompts and article text and currently have no retention policy; keep access restricted and manage their retention separately.

The repository includes GitHub Actions for frontend checks, backend tests against PostgreSQL, and a container startup smoke check. Dependabot proposes dependency updates. These will run after the changes are pushed; they do not deploy to a server or publish images.

## Back up and restore

```bash
./deploy.sh backup
# Optional: supply a new directory, which must not already exist.
./deploy.sh backup backups/before-release
```

Backup briefly stops API and worker writers, saves a PostgreSQL custom-format dump and uploaded originals, validates the dump listing, marks successful backups with `COMPLETE`, and restarts the previously running writers even if backup fails. Treat a directory without `COMPLETE` as incomplete. The command needs a running database and the backend image. Copy completed backups to protected storage on another machine; this command does not schedule or upload them.

Database backups include drafts, revisions, users, usage and workflow checkpoints. Uploads are needed for document download/resync. Save `.env.production` separately through a secure channel. Pinecone vectors are external data and are not included; preserve the external index or resync documents after restoring it. Detailed LLM logs and TLS certificates are not part of these backups.

To restore a trusted backup to an installation **whose current database and uploads may be replaced**, run the following from the repository root. This is a destructive operator procedure, not an automatic rollback:

```bash
# Substitute the directory of a COMPLETE backup and use its matching env/project.
set -e
BACKUP=backups/before-release
DC=(docker compose --env-file .env.production -p blog-gen-production -f compose.production.yml)
test -f "$BACKUP/COMPLETE"
# Validate both files before replacing anything.
"${DC[@]}" exec -T db pg_restore --list < "$BACKUP/database.dump" > /dev/null
"${DC[@]}" run --rm --no-deps -T backend tar -tzf - < "$BACKUP/uploads.tar.gz"
"${DC[@]}" stop frontend worker backend
"${DC[@]}" exec -T db pg_restore -U blog_gen -d blog_gen --single-transaction --clean --if-exists --no-owner --no-privileges < "$BACKUP/database.dump"
"${DC[@]}" run --rm --no-deps -T backend sh -c 'find uploads -mindepth 1 -delete && tar -xzf - -C /app' < "$BACKUP/uploads.tar.gz"
# Use application code compatible with the restored database, then:
./deploy.sh up
```

Run these in a Bash shell with `set -e` so a failed validation or restore prevents later commands. Start the database first if restoring to a fresh host: `${DC[@]} up -d --wait db`; build the backend image before restoring uploads. Leave services stopped if a restore fails. Test restoration on an isolated project periodically; a successful backup command alone does not prove recovery.

## Troubleshoot

| Symptom | Check |
| --- | --- |
| `up` fails before startup | Docker daemon, Compose v2, disk space, then `./deploy.sh check`. Avoid printing resolved Compose config; it contains credentials. |
| API is unhealthy | `./deploy.sh logs backend` and migration logs. `/health/ready` checks workflow initialization and the application database table; `/health/live` only checks the HTTP process. |
| Runs stay queued | Worker container health and `./deploy.sh logs worker`. Workers must use the same database/settings as the API. |
| Worker is unhealthy | Its dispatcher heartbeat is missing or stale. Inspect logs and restart it after correcting the cause. Docker health status alone does not restart a live but unhealthy process. |
| Cloud run is blocked | Exact `provider:model` rate, provider key, remaining monthly and per-run budgets, and any unresolved reservations. |
| HTTPS certificate fails | Domain DNS, IPv4/IPv6 routing, public 80/443 reachability, and frontend logs. |
| Signup is disabled | Use `./deploy.sh create-user EMAIL`. Enable public registration only intentionally; new accounts can consume shared provider keys. |
| Another deployment seems empty | Check that the project name and env file have not changed; named volumes are scoped by project. |

For an isolated rehearsal, set `BLOG_GEN_PROJECT_NAME` to a different name and `BLOG_GEN_ENV_FILE` to a different file for every command, then choose unused HTTP/HTTPS ports. The default production and development databases are separate. Compose waits for database health and successful migrations using its documented [startup dependencies](https://docs.docker.com/compose/how-tos/startup-order/).
