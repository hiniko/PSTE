#!/usr/bin/env node
/**
 * UserPromptSubmit hook. Layers 2 and 3 of the anti-drift design.
 *
 * Three jobs, on every user turn:
 *   1. Parse /pste commands and natural-language activation, and write the level.
 *   2. Select level 3 automatically when the user asks for an artifact that
 *      PSTE-C3 names, unless the repository turns that off.
 *   3. Inject a short reminder, which survives competing instructions from other
 *      plugins and keeps the rules in the model's attention.
 *
 * The reminder is short on purpose. SessionStart supplies the full rule set once.
 * Repeating all of it every turn would cost more than it returns.
 */

const cfg = require("./pste-config.js");

const COMMAND_RE = /^\s*\/pste(?::pste)?(?:\s+(\S+))?/i;
const DEACTIVATE_RE =
  /\b(?:stop pste|normal mode|disable pste|turn off pste|pste off)\b/i;
const ACTIVATE_RE =
  /\b(?:start pste|use pste|enable pste|pste mode|simplified technical english|controlled english)\b/i;
// A question about the mode is not a command to change it.
const QUESTION_RE = /\b(?:what|which|how|why|when|is|does|can)\b[^?]*\?/i;

function readStdin() {
  try {
    const fs = require("fs");
    return fs.readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

function parsePayload(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function emit(context) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: context,
      },
    })
  );
}

/** The per-turn anchor. Level-specific, and always carries the scope boundary. */
function reminder(level, autoStrict) {
  if (level === "lite") {
    return (
      "PSTE ACTIVE (lite). Cut filler, hedging, and marketing adjectives. " +
      "Active voice, named actor. Result first. " +
      "Code, quotes, and identifiers: verbatim."
    );
  }

  const base =
    `PSTE ACTIVE (${level}). Result first. Active voice, named actor. ` +
    "One word one meaning. Simple tenses only. No contractions, semicolons, " +
    "Latin abbreviations, marketing adjectives, or filler. State uncertainty once. " +
    "Instruction under 20 words, description under 25. " +
    "Code, quotes, identifiers, commit messages: verbatim or repository style. " +
    "Accuracy defeats every rule: never drop a fact to meet a word limit.";

  if (level === "strict") {
    return (
      base +
      " STRICT: use the approved word list, one instruction per sentence, " +
      "vertical lists for three or more steps, and lead a warning with the command " +
      "or the condition." +
      (autoStrict
        ? " Level 3 selected automatically for this artifact type."
        : "")
    );
  }
  return base;
}

function main() {
  const payload = parsePayload(readStdin());
  const prompt = payload.prompt || payload.user_prompt || "";
  const cwd = payload.cwd || process.cwd();

  let level = cfg.readLevel();

  // 1. Explicit command wins over everything.
  const cmd = prompt.match(COMMAND_RE);
  if (cmd) {
    const arg = (cmd[1] || cfg.DEFAULT_LEVEL).toLowerCase();
    if (cfg.VALID_LEVELS.includes(arg)) {
      cfg.writeLevel(arg);
      if (arg === "off") {
        emit("PSTE is off. Write normal prose.");
        return;
      }
      emit(`PSTE level set to ${arg}. ` + reminder(arg, false));
      return;
    }
  }

  // 2. Natural language. Deactivation is checked first so that it cannot be
  //    shadowed, and questions about the mode are ignored.
  const isQuestion = QUESTION_RE.test(prompt);
  if (!isQuestion && DEACTIVATE_RE.test(prompt)) {
    cfg.writeLevel("off");
    emit("PSTE is off. Write normal prose.");
    return;
  }
  if (!isQuestion && level === "off" && ACTIVATE_RE.test(prompt)) {
    level = cfg.DEFAULT_LEVEL;
    cfg.writeLevel(level);
  }

  if (level === "off") {
    process.exit(0);
  }

  // 3. Auto-select level 3 for the artifact types in PSTE-C3. This raises the
  //    level for one turn and does not overwrite the user's chosen level.
  let effective = level;
  let auto = false;
  if (level !== "strict" && cfg.wantsStrict(prompt, cwd)) {
    effective = "strict";
    auto = true;
  }

  emit(reminder(effective, auto));
}

try {
  main();
} catch {
  // A hook must never block a user turn.
  process.exit(0);
}
