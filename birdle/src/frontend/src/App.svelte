<script lang="ts">
    import { onMount, tick } from "svelte";
    import { getAllBirds, getRoundStatus, start } from "./api";
    import type { Bird } from "./types";
    import AudioSnippet from "./lib/AudioSnippet.svelte";
    import GuessForm from "./lib/GuessForm.svelte";
    import { MAX_GUESSES } from "./lib/constants";
    import {
        clearProgress,
        loadProgress,
        saveProgress,
        todayKey,
        type Progress,
    } from "./lib/progress";

    let round = $state("");
    let audioPath = $state("");
    let imagePath = $state("");
    let initialProgress = $state<Progress | null>(null);

    let allBirds = $state<Array<Bird>>([]);

    const startGame = async () => {
        const saved = loadProgress();

        if (saved) {
            // Only resume if the server still remembers this round - it
            // won't after a restart/redeploy, since round state lives in memory.
            const status = await getRoundStatus(saved.roundId);
            if (status) {
                round = saved.roundId;
                initialProgress = saved;
                return;
            }
            clearProgress();
        }

        const game = await start();
        round = game.round_id;

        saveProgress({
            date: todayKey(),
            roundId: round,
            guessRows: Array(MAX_GUESSES).fill(null),
            guessCounter: 0,
            correct: false,
            answer: null,
        });
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
            <GuessForm roundID={round} {allBirds} {audioPath} {initialProgress} />
        </div>
    </div>
</main>

<style>
</style>
