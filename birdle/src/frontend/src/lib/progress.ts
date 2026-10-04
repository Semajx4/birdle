import type { Bird } from "../types";

export type GuessRowState = Bird & {
    hints: { order: boolean; family: boolean; genus: boolean };
    correct: boolean;
};

export type Progress = {
    date: string;
    roundId: string;
    guessRows: (GuessRowState | null)[];
    guessCounter: number;
    correct: boolean;
    answer: Bird | null;
};

const STORAGE_KEY = "birdle:progress";

// The backend rolls the daily bird over at midnight New Zealand time
// (GAME_TZ in services/game.py), so the resume check and share text have to
// use the same day boundary, whatever the player's own time zone.
const GAME_TZ = "Pacific/Auckland";

export function todayKey(): string {
    const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: GAME_TZ,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).formatToParts(new Date());
    const get = (type: string) => parts.find((p) => p.type === type)?.value;
    return `${get("year")}-${get("month")}-${get("day")}`;
}

// Milliseconds until the next bird (midnight New Zealand time). Worked out
// from the NZ wall clock, so it can be an hour out in the few hours after
// midnight on the two daylight-saving changeover days - fine for a countdown.
export function msUntilNextBird(now: Date = new Date()): number {
    const parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: GAME_TZ,
        hourCycle: "h23",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    }).formatToParts(now);
    const get = (type: string) =>
        Number(parts.find((p) => p.type === type)?.value ?? 0);
    const elapsed =
        (get("hour") * 3600 + get("minute") * 60 + get("second")) * 1000 +
        now.getMilliseconds();
    return 24 * 3600 * 1000 - elapsed;
}

export function loadProgress(): Progress | null {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;

        const parsed = JSON.parse(raw) as Progress;
        return parsed.date === todayKey() ? parsed : null;
    } catch {
        return null;
    }
}

export function saveProgress(progress: Progress) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    } catch {
        // localStorage unavailable (private browsing, quota, etc) - just skip persistence
    }
}

export function clearProgress() {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {
        // ignore
    }
}
