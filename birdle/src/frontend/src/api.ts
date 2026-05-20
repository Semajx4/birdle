
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

    return await res.json();
}

export function getAudioUrl(round_id: string): string {
    return `/api/bird/audio/${round_id}`;
}


export function getImageUrl(round_id: string): string {
    return `/api/bird/image/${round_id}`;
}
