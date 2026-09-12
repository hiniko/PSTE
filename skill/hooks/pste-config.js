/**
 * Shared state for the PSTE hooks.
 *
 * The active level lives in a file rather than in the conversation, so that it
 * survives context compaction and new sessions. Every filesystem operation here
 * fails silently: a hook must never block session start (PSTE plan section 9).
 */

const fs = require("fs");
const os = require("os");
const path = require("path");

const VALID_LEVELS = ["off", "lite", "pste", "strict"];
const DEFAULT_LEVEL = "pste";
const FLAG_NAME = ".pste-active";
const MAX_FLAG_BYTES = 64;

/** Artifact types that select level 3 automatically (PSTE-C3). */
const STRICT_ARTIFACTS = [
  "release note",
  "release notes",
  "changelog",
  "runbook",
  "playbook",
  "incident report",
  "postmortem",
  "post-mortem",
  "error message",
  "error text",
  "user-facing message",
  "documentation",
  "docs page",
  "readme",
  "api docs",
  "man page",
  "help text",
  "onboarding guide",
  "migration guide",
];

function configDir() {
  return (
    process.env.CLAUDE_CONFIG_DIR ||
    path.join(os.homedir(), ".claude")
  );
}

function flagPath() {
  return path.join(configDir(), FLAG_NAME);
}

/**
 * Refuse to follow a symlink when reading or writing the flag. A symlinked flag
 * file would let anything that can write to the config directory redirect a hook
 * write to an arbitrary path.
 */
function refusesSymlink(target) {
  try {
    const st = fs.lstatSync(target);
    return st.isSymbolicLink();
  } catch {
    return false; // absent is fine; it gets created
  }
}

function readLevel() {
  try {
    const p = flagPath();
    if (refusesSymlink(p)) return DEFAULT_LEVEL;
    const raw = fs.readFileSync(p, { encoding: "utf8", flag: "r" });
    if (raw.length > MAX_FLAG_BYTES) return DEFAULT_LEVEL;
    const value = raw.trim();
    return VALID_LEVELS.includes(value) ? value : DEFAULT_LEVEL;
  } catch {
    return DEFAULT_LEVEL;
  }
}

function writeLevel(level) {
  if (!VALID_LEVELS.includes(level)) return false;
  try {
    const dir = configDir();
    fs.mkdirSync(dir, { recursive: true });
    const target = flagPath();
    if (refusesSymlink(target)) return false;
    // Write to a temporary file and rename, so a reader never sees a partial value.
    const tmp = path.join(dir, `${FLAG_NAME}.${process.pid}.tmp`);
    fs.writeFileSync(tmp, level, { mode: 0o600 });
    fs.renameSync(tmp, target);
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the level that a new session starts at.
 * Order: env var, then repository config, then user config, then the default.
 */
function defaultLevel(cwd) {
  const fromEnv = process.env.PSTE_LEVEL;
  if (fromEnv && VALID_LEVELS.includes(fromEnv)) return fromEnv;

  const fromRepo = readRepoConfig(cwd || process.cwd());
  if (fromRepo && VALID_LEVELS.includes(fromRepo.level)) return fromRepo.level;

  return DEFAULT_LEVEL;
}

/** Walk up from cwd looking for .pste.json. Bounded, so a deep tree cannot hang. */
function readRepoConfig(startDir) {
  let dir = startDir;
  for (let i = 0; i < 32; i += 1) {
    try {
      const candidate = path.join(dir, ".pste.json");
      if (fs.existsSync(candidate)) {
        const raw = fs.readFileSync(candidate, "utf8");
        if (raw.length < 8192) return JSON.parse(raw);
      }
    } catch {
      // Unreadable or malformed config is not fatal; keep walking.
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/**
 * Decide whether a prompt asks for an artifact that PSTE-C3 says to write at
 * level 3. A repository can turn this off, or add its own triggers, through
 * .pste.json: {"autoStrict": false} or {"strictArtifacts": ["design doc"]}.
 */
function wantsStrict(promptText, cwd) {
  if (!promptText) return false;
  const cfg = readRepoConfig(cwd || process.cwd()) || {};
  if (cfg.autoStrict === false) return false;

  const triggers = Array.isArray(cfg.strictArtifacts)
    ? STRICT_ARTIFACTS.concat(cfg.strictArtifacts)
    : STRICT_ARTIFACTS;

  const text = promptText.toLowerCase();
  return triggers.some((t) => text.includes(t.toLowerCase()));
}

module.exports = {
  VALID_LEVELS,
  DEFAULT_LEVEL,
  STRICT_ARTIFACTS,
  configDir,
  flagPath,
  readLevel,
  writeLevel,
  defaultLevel,
  readRepoConfig,
  wantsStrict,
};
