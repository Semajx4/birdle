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

    // Show the splash/how-to page first, unless there's already a game in
    // progress for today - then go straight back to it.
    let started = $state(loadProgress() !== null);

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

    // The round is only created once the player presses Play, so page views
    // that never get past the splash don't show up as started rounds.
    const play = async () => {
        started = true;
        await startGame();
    };

    onMount(async () => {
        if (started) await startGame();
        await getBirds();
    });
</script>

<main class="container">
    {#if !started}
        <div class="splash">
            <div class="splash-card">
                <div class="title-area">
                    <img class="splash-logo" src="/bird.svg" alt="" />
                    <h1 class="title" aria-label="birdle2.nz">BIRDLE<sup>2</sup>.NZ</h1>
                    <p class="subtitle">
                        Listen to the bird song and guess the bird
                    </p>
                </div>

                <section class="how-to" aria-labelledby="how-to-heading">
                    <h2 id="how-to-heading">How to play</h2>
                    <ul>
                        <li>Listen to a mystery New Zealand bird</li>
                        <li>Guess it in {MAX_GUESSES} tries</li>
                        <li><span class="hit">Green</span> hints mean you're getting close</li>
                    </ul>

                    <div class="example" aria-label="Example guess">
                        <p class="example-caption">
                            Answer <b>Tui</b>, you guess <b>Bellbird</b>:
                        </p>
                        <div class="example-row">
                            <span class="hit">Passeriformes</span>
                            <span class="hit">Meliphagidae</span>
                            <span class="miss">Anthornis</span>
                        </div>
                        <p class="example-caption">Same order and family. Close!</p>
                    </div>

                    <p class="rules">New bird every day.</p>
                </section>

                <button class="start-button" onclick={play}>Play</button>

                <p class="hint">Best played with sound on 🔊</p>
            </div>
        </div>
    {:else}
        <div id="game">
            <div class="card">
                <AudioSnippet roundID={round} />
            </div>

            <div class="card">
                <GuessForm roundID={round} {allBirds} {audioPath} {initialProgress} />
            </div>
        </div>
    {/if}
</main>

<style>
</style>
