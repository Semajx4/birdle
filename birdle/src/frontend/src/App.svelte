<script lang="ts">
    import { onMount, tick } from "svelte";
    import { getAllBirds, start } from "./api";
    import type { Bird } from "./types";
    import AudioSnippet from "./lib/AudioSnippet.svelte";
    import GuessForm from "./lib/GuessForm.svelte";

    let round = $state("");
    let audioPath = $state("");
    let imagePath = $state("");

    let allBirds = $state<Array<Bird>>([]);

    const startGame = async () => {
        const game = await start();
        round = game.round_id;
    };

    const getBirds = async () => {
        allBirds = await getAllBirds();
    };

    onMount(async () => {
        await startGame();
        await getBirds();
    });
</script>

<main class="container">
    <div id="splash" class="splash" style="display: {'none'}">
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

            <!-- <button onclick={() => (started = true)}>Play</button> -->

            <p class="hint">Best played with sound on 🔊</p>
        </div>
    </div>

    <div id="game" hidden={!true}>
        <div class="card">
            <AudioSnippet roundID={round} />
        </div>

        <div class="card">
            <GuessForm roundID={round} {allBirds} {audioPath} />
        </div>
    </div>
</main>

<style>
</style>
