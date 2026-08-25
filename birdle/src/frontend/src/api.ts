
import type { Bird , Guess} from "./types";

export async function start() {
    const res = await fetch("/api/bird/start");
        if (!res.ok) throw new Error("Failed to fetch round data");
    return await res.json();
}

export async function getAllBirds() {
    const res = await fetch("/api/bird/all");
        if (!res.ok) throw new Error("Failed to fetch bird data");
    const data = await res.json();
    return data as Bird[];
}

export async function postGuess(guess: Guess) {
    const res = await fetch("/api/bird/guess", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(guess),
    });

    if (!res.ok) {
        throw new Error(`Guess request failed: ${res.status}`);
    }

    const data = await res.json();
    if (data.error) {
        throw new Error(data.error);
    }

    return data;
}

export async function getRoundStatus(
    round_id: string,
): Promise<{ guesses: number; finished: boolean; won: boolean } | null> {
    const res = await fetch(`/api/bird/status/${round_id}`);
    if (!res.ok) return null;

    const data = await res.json();
    if (data.error) return null;

    return data;
}

export function getAudioUrl(round_id: string): string {
    return `/api/bird/audio/${round_id}`;
}


export function getImageUrl(round_id: string): string {
    return `/api/bird/image/${round_id}`;
}

export async function getAnswer(round_id: string): Promise<Bird | null> {
    const res = await fetch(`/api/bird/reveal/${round_id}`);

    if (!res.ok) return null;

    const data: Bird = await res.json();
    return data;
}
