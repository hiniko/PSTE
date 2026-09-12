#!/usr/bin/env node
/**
 * SessionStart hook. Layer 1 of the anti-drift design.
 *
 * Reads SKILL.md off disk at runtime and writes it to stdout, which Claude Code
 * injects as system context. Reading the file live means this hook can never drift
 * out of sync with the documented rules.
 *
 * A short summary is not enough. A model that receives two sentences of style
 * instruction returns to its usual prose after a few turns, and context compaction
 * removes the instruction entirely. The full rule set with examples holds.
 */

const fs = require("fs");
const path = require("path");
const cfg = require("./pste-config.js");

/** SKILL.md may sit in several places, depending on how the user installed this. */
function findSkillFile() {
  const candidates = [
    process.env.PSTE_SKILL_PATH,
    process.env.CLAUDE_PLUGIN_ROOT &&
      path.join(process.env.CLAUDE_PLUGIN_ROOT, "skill", "SKILL.md"),
    process.env.CLAUDE_PLUGIN_ROOT &&
      path.join(process.env.CLAUDE_PLUGIN_ROOT, "SKILL.md"),
    path.join(__dirname, "..", "SKILL.md"),
    path.join(__dirname, "..", "..", "skill", "SKILL.md"),
  ].filter(Boolean);

  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch {
      // Keep looking.
    }
  }
  return null;
}

function stripFrontmatter(text) {
  if (!text.startsWith("---")) return text;
  const end = text.indexOf("\n---", 3);
  if (end === -1) return text;
  return text.slice(end + 4).replace(/^\s*\n/, "");
}

/** Used when SKILL.md cannot be found, so a hook-only install still works. */
function fallbackRules() {
  return [
    "PSTE MODE ACTIVE.",
    "",
    "Write your own prose in Programming Simplified Technical English.",
    "",
    "Say the result first. Name the actor and use the active voice. Use one word for",
    "one meaning, from the approved word list. Keep an instruction under 20 words and",
    "a description under 25. Use simple tenses only, with no perfect tenses and no",
    "stacked auxiliaries. Do not use contractions, semicolons, Latin abbreviations,",
    "marketing adjectives, or filler. State uncertainty once and never stack hedges.",
    "Use a vertical list for three or more steps. Keep an instruction to one per",
    "sentence. A note holds no instruction. Lead a warning with the command or the",
    "condition. Warn before an operation that destroys something, state the scope",
    "before the command, and say what the reader loses.",
    "",
    "Accuracy defeats every rule above. Never drop a fact, a condition, or a number to",
    "satisfy a word limit. Split the sentence instead.",
    "",
    "Scope: these rules govern the prose you write. Reproduce code, commands, paths,",
    "identifiers, error strings, and quoted text verbatim. Match the repository style",
    "in code comments and commit messages. Never inflect an identifier.",
    "",
    'Never announce the mode. Off only on "stop pste" or "normal mode".',
  ].join("\n");
}

function main() {
  const level = cfg.defaultLevel(process.cwd());
  cfg.writeLevel(level);

  if (level === "off") {
    process.exit(0);
  }

  const skillPath = findSkillFile();
  if (!skillPath) {
    process.stdout.write(fallbackRules());
    process.exit(0);
  }

  let body;
  try {
    body = fs.readFileSync(skillPath, "utf8");
  } catch {
    process.stdout.write(fallbackRules());
    process.exit(0);
  }

  const rules = stripFrontmatter(body);
  process.stdout.write(
    `PSTE MODE ACTIVE. Follow these rules for prose you write.\n\n${rules}`
  );
}

try {
  main();
} catch {
  // A hook must never block session start.
  process.exit(0);
}
