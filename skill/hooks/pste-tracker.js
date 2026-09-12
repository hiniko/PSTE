#!/usr/bin/env node
/**
 * UserPromptSubmit hook. Layers 2 and 3 of the anti-drift design.
 *
 * Three jobs, on every user turn:
 *   1. Parse /pste commands and natural-language activation, and write on/off.
 *   2. Turn PSTE on automatically when the user asks for an artifact type
 *      AUTO_ON_ARTIFACTS names, unless the repository turns that off.
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

/** The per-turn anchor. Always carries the scope boundary. */
function reminder(autoOn) {
  return (
    "PSTE ACTIVE. Result first. Active voice, named actor. " +
    "One word one meaning, from the approved word list. Simple tenses only. " +
    "No contractions, semicolons, Latin abbreviations, marketing adjectives, or " +
    "filler. State uncertainty once. One instruction per sentence. A vertical " +
    "list for three or more steps. A note holds no instruction. Lead a warning " +
    "with the command or the condition. " +
    "Instruction under 20 words, description under 25. " +
    "Code, quotes, identifiers, commit messages: verbatim or repository style. " +
    "Accuracy defeats every rule: never drop a fact to meet a word limit." +
    (autoOn ? " PSTE turned on automatically for this artifact type." : "")
  );
}

function main() {
  const payload = parsePayload(readStdin());
  const prompt = payload.prompt || payload.user_prompt || "";
  const cwd = payload.cwd || process.cwd();

  let level = cfg.readLevel();

  // 1. Explicit command wins over everything. "/pste" and "/pste on" both mean
  //    the same thing as the default: turn PSTE on.
  const cmd = prompt.match(COMMAND_RE);
  if (cmd) {
    const raw = (cmd[1] || "on").toLowerCase();
    const arg = raw === "on" ? cfg.DEFAULT_LEVEL : raw;
    if (cfg.VALID_LEVELS.includes(arg)) {
      cfg.writeLevel(arg);
      if (arg === "off") {
        emit("PSTE is off. Write normal prose.");
        return;
      }
      emit("PSTE turned on. " + reminder(false));
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
    // 3. Turn PSTE on for this one turn when the prompt asks for an artifact
    //    type AUTO_ON_ARTIFACTS names. This does not overwrite the stored
    //    on/off state, the same way the command above does.
    if (cfg.wantsOn(prompt, cwd)) {
      emit(reminder(true));
    }
    process.exit(0);
  }

  emit(reminder(false));
}

try {
  main();
} catch {
  // A hook must never block a user turn.
  process.exit(0);
}
