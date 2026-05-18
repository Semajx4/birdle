<script lang="ts">
    import { onMount, tick } from "svelte";
    import type { Bird } from "./types";
    import AudioSnippet from "./lib/AudioSnippet.svelte";
    import GuessForm from "./lib/GuessForm.svelte";

    let audioPath = $state("");

    let birdOfTheDay = $state(null);
    let allBirds = $state<Bird[] | null>(null);
    let reset = $state(false);
    let started = $state(false);

    async function getRandomBird() {
        const res = await fetch("http://localhost:8000/api/bird/random");
        if (!res.ok) throw new Error("Failed to fetch bird data");
        return await res.json();
    }

    async function getAllBirds() {
        const res = await fetch("http://localhost:8000/api/bird/all");
        if (!res.ok) throw new Error("Failed to fetch bird data");
        const data = await res.json();
        return data as Bird[];
    }

    const updateAllBirds = async () => {
        allBirds = await getAllBirds();
    };

    const updateBirdOfTheDay = async () => {
        const bird = await getRandomBird();
        birdOfTheDay = bird;
        audioPath = bird.audio_path;

        reset = true;
        await tick();
        reset = false;
    };

    onMount(async () => {
        await updateBirdOfTheDay();
        await updateAllBirds();
    });
</script>

<main class="container">
    <div
        id="splash"
        class="splash"
        style="display: {started ? 'none' : 'flex'}"
    >
        <div class="splash-card">
            <div class="title-area">
                <h1 class="title">BIRDLE</h1>
                <p class="subtitle">
                    Listen to the bird song and guess the bird
                </p>
            </div>

            <div class="illustration">
                <!-- optional: background image or decorative birds -->
            </div>

            <button onclick={() => (started = true)}>Play</button>

            <p class="hint">Best played with sound on 🔊</p>
        </div>
    </div>

    <div id="game" hidden={!started}>
        <div class="card">
            <AudioSnippet audioSource={audioPath} />
        </div>

        <div class="card">
            <GuessForm {reset} bird={birdOfTheDay} {allBirds} />
        </div>
    </div>
</main>

<style>
</style>
