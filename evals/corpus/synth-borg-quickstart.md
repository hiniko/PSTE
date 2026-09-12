---
model: claude-sonnet-5
generated_by: 2.1.220 (Claude Code)
generated_on: 2026-09-11
environment: container, evals/Dockerfile.clean
isolation: |
  No CLAUDE.md, no plugin, no hook, no memory, and no configured skill.
  The container holds none of them, so none can reach the model.
constrained: false
grounding_url: https://raw.githubusercontent.com/borgbackup/borg/master/docs/quickstart.rst
grounding_licence: BSD-3-Clause
question: |
  Write a documentation page for the backup and restore quickstart workflow in BorgBackup. A copy of an upstream page for this topic is mounted at /grounding/synth-borg-quickstart.md. Use it only to check facts and stay accurate. Do not paraphrase it, follow its structure, or reuse its wording: write your own independent documentation page, organised and expressed the way you normally would. Write in your own normal style. Do not apply any writing standard, style guide, or controlled language that you find in that repository.
---
# BorgBackup: Backup and Restore Quickstart

BorgBackup (`borg`) is a deduplicating backup tool. It splits the files you back up into chunks, stores each unique chunk exactly once in a repository, and can encrypt everything on the client before it ever leaves your machine. This guide walks through the core workflow: create a repository, make a backup, look at what you've got, and restore files when you need them.

## The two core concepts

- **Repository** — a store of encrypted, deduplicated chunks, plus the metadata that lets Borg reassemble them into files. A repository can live on local disk (an external drive, a mounted volume) or on a remote host reachable over SSH.
- **Archive** — a single backup run, created with `borg create`. Each archive is a full snapshot of the paths you backed up at that point in time, even though under the hood it only stores new chunks — unchanged data is simply referenced again. You end up with what feels like many complete backups while paying disk space for only the deltas.

## 1. Create a repository

Before you can back anything up, initialize a repository:

```bash
borg repo-create --encryption=repokey-blake2-aes-ocb -r /path/to/repo
```

Pick an encryption mode up front — it can't be changed later without creating a new repository. `repokey` modes store the encryption key inside the repository itself (convenient, and the easiest to recover from), while `keyfile` modes keep the key in your home directory instead (useful if you don't want the key sitting alongside the encrypted data). If you don't need encryption at all, `--encryption=none` skips it, but almost everyone should encrypt unless the storage is already trusted and access-controlled.

To avoid repeating `-r /path/to/repo` on every command, export it once:

```bash
export BORG_REPO=/path/to/repo
```

## 2. Make a backup

```bash
borg create --stats --progress '{hostname}-{now}' ~/Documents ~/Projects
```

`{hostname}` and `{now}` are placeholders Borg expands automatically, so repeated runs of this exact command produce a new, uniquely named archive each time without any extra bookkeeping on your part. `--stats` prints how much data was added versus deduplicated away, and `--progress` gives you a live indicator during long runs — both are optional but useful the first few times you run this.

Compression is worth setting explicitly rather than relying on defaults:

```bash
borg create --compression zstd,6 '{hostname}-{now}' ~/Documents
```

`lz4` is the fastest option and is fine for already-compressed data (media files, archives); `zstd` at a moderate level (3–10) is a good general-purpose choice; `auto,zstd,N` probes each chunk cheaply with lz4 first and only pays zstd's cost when it looks worthwhile. Compression matters more than it sounds like for remote backups, since it directly cuts how much has to go over the network.

## 3. See what you've backed up

```bash
borg repo-list                  # list all archives in the repository
borg list aid:d34db33f          # list files inside one archive
```

Archives are referenced by an archive ID (or a unique prefix of one, as shown above) or by name. `borg repo-list` is your starting point any time you need to restore something and don't already know exactly which archive to target.

## 4. Restore files

There are two ways to get data back out, and which one you want depends on how sure you already are about what you need.

**`borg mount`** — mounts a repository or archive as a FUSE filesystem, so you can browse it like any other directory. Reach for this when you're not sure which archive has the version of a file you want, or you just want to poke around before committing to a restore:

```bash
mkdir /mnt/borg
borg mount -a aid:d34db33f /mnt/borg
# browse /mnt/borg in another terminal, copy out what you need
borg umount /mnt/borg
```

**`borg extract`** — pulls files directly out of a known archive into your current directory. Faster, and more faithful about restoring metadata (ACLs, special filesystem flags) than a FUSE mount can be — use this once you know exactly what you want:

```bash
mkdir restore && cd restore
borg extract aid:d34db33f path/to/file   # restore just one path (no leading /)
borg extract aid:d34db33f                # or restore the whole archive
```

`borg extract` always writes into the current directory, and expects that directory to be empty — it won't merge a restore into an existing tree.

A restore generally goes smoothest on the same machine and under the same user account that made the backup: it avoids surprises with path layout and with usernames/groups not mapping to the IDs your files were saved with. If you're restoring an encrypted repository and the key lives in `keyfile` mode rather than `repokey` mode, make sure you have both the keyfile and its passphrase before you start — without them the data is unrecoverable by design.

## Keeping backups working long-term

A few things matter for backups you intend to actually rely on:

- **Free disk space.** Borg needs headroom to operate, including to delete old archives — running a repository's filesystem to zero can leave you unable to free space at all. Keep a comfortable margin, and check it as part of whatever process reviews your backup logs.
- **Consistent user/permissions.** Always access a given repository as the same user. Back up as root if you need root-owned or multi-user files; otherwise use your normal account. For remote repositories, the SSH login already fixes the effective user, so this is less of a concern there.
- **File consistency during the backup.** Borg just reads files as it encounters them — it doesn't snapshot anything for you. For a quiet home directory this is rarely an issue; for databases, VMs, or containers that are actively writing, stop the service, use its own consistent-dump/snapshot mechanism, or snapshot the underlying filesystem (LVM, ZFS) before backing up.
- **Prune and compact regularly.** `borg create` alone only adds archives; it never removes them. Run `borg prune` on a schedule to drop old archives per a retention policy, and `borg compact` afterward to actually reclaim the space `prune` freed:

  ```bash
  borg prune '{hostname}' --keep-daily 7 --keep-weekly 4 --keep-monthly 6
  borg compact
  ```

## Automating it

For unattended backups, set the passphrase via environment variable rather than typing it interactively:

```bash
export BORG_PASSPHRASE='a long and secure passphrase'
# or, better for scripts checked into anywhere: delegate to a password manager
export BORG_PASSCOMMAND='pass show backup'
```

Always `export` the variable (so subprocesses, including Borg, inherit it) and use single quotes around it so your shell doesn't do anything clever with special characters. Note that `sudo` does not pass your environment through by default — a script run via `sudo` won't see a `BORG_PASSPHRASE` you exported beforehand unless `env_keep` is configured for it in `sudoers`.

A minimal cron-friendly script ties this together: run `borg create`, then `borg prune`, then `borg compact`, checking exit codes after each step so a failure anywhere gets surfaced rather than silently ignored.

## Remote repositories

If Borg is installed on the remote host, use a `rest://` URL — Borg connects over SSH and runs `borg serve --rest` on the other end:

```bash
borg -r rest://user@hostname:port/path/to/repo repo-create --encryption=repokey-blake2-aes-ocb
borg -r rest://user@hostname:port/path/to/repo create '{hostname}-{now}' ~/Documents
```

Restoring from a remote repository works exactly the same way, just with the `rest://` URL in place of a local path:

```bash
borg -r rest://user@hostname:port/path/to/repo mount /mnt/borg
borg -r rest://user@hostname:port/path/to/repo extract aid:d34db33f
```

If Borg can't be installed on the remote side, mounting the remote filesystem locally (e.g. via `sshfs`) and pointing Borg at the mount point also works, though it depends on how well the remote filesystem holds up under sustained backup traffic. Borg also supports talking directly to sftp servers and to S3-compatible or rclone-backed object storage as repository backends, without needing anything Borg-specific installed remotely.
