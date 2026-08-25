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

// The backend picks the daily bird off datetime.utcnow().date(), so the
// resume check has to use the same UTC day boundary.
export function todayKey(): string {
    return new Date().toISOString().slice(0, 10);
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
