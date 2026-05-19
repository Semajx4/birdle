<script lang="ts">
    import { onMount, tick } from "svelte";
    import { getAllBirds, getRandomBird } from "./api";
    import type { Bird } from "./types";
    import AudioSnippet from "./lib/AudioSnippet.svelte";
    import GuessForm from "./lib/GuessForm.svelte";

    let audioPath = $state("");

    let birdOfTheDay = $state(null);
    let allBirds = $state<Bird[] | null>(null);
    let reset = $state(false);
    let started = $state(false);

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
    export { getAudio };
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
