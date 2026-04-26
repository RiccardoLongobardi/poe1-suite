/**
 * Welcome-flag persistence.
 *
 * The animated welcome screen is shown only on the user's first visit.
 * After "Inizia" we set a localStorage flag so subsequent loads skip
 * straight to the home dashboard — repeated cinematic intros get old
 * fast, even good ones.
 *
 * The flag is intentionally one-way: there's no built-in "reset"
 * action because the user can clear browser storage if they want to
 * see the intro again.
 */

const KEY = "fob_seen_welcome";

export function hasSeenWelcome(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    // Private mode / disabled storage — show the welcome.
    return false;
  }
}

export function markWelcomeSeen(): void {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    /* nothing useful we can do here */
  }
}
