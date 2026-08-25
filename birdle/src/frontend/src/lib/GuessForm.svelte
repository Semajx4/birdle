<script lang="ts">
    import AnswerText from "./AnswerText.svelte";
    import type { Bird, FullGuess } from "../types";
    import ImageHint from "./ImageHint.svelte";
    import { postGuess, getAnswer, start } from "../api";
    import { MAX_GUESSES } from "../lib/constants";
    import {
        clearProgress,
        saveProgress,
        todayKey,
        type GuessRowState,
    } from "../lib/progress";

    let prop = $props();

    const MAXGUESSES = MAX_GUESSES;
    let hydrated = $state(false);

    let roundID = $state<string | null>(null);
    let audioPath = $state<string | null>("");
    let imageVersion = $state(0);
    let allBirds = $state<Array<Bird> | null>(null);
    let correct = $state<boolean>(false);
    let possibleOptions = $state<Bird[] | null>(null);
    let answer = $state<Bird | null>(null);

    let guessArray = $state(new Array<Bird>());

    let guessStatus = $state<boolean[]>([
        false,
        false,
        false,
        false,
        false,
        false,
    ]);

    let inputField = $state<HTMLInputElement>();
    let guessCounter = $state(0);
    let input = $state("");
    let autoCompleteClicked = $state(false);
    let highlightedIndex = $state(-1);
    let guessRows = $state(Array(MAXGUESSES).fill(null));

    let shareCopied = $state(false);

    let currentGuess = $state<FullGuess>({
        guess: {
            round_id: "",
            guess_id: "",
        },
        bird: {
            id: "",
            common_name: "",
            scientific_name: "",
            order: "",
            family: "",
            genus: "",
        },
    });

    $effect(() => {
        if (prop.roundID) roundID = prop.roundID;
        if (prop.allBirds) allBirds = prop.allBirds;
        if (prop.audioPath) audioPath = prop.audioPath;

        if (!hydrated && prop.initialProgress) {
            const saved = prop.initialProgress;

            guessRows = saved.guessRows;
            guessCounter = saved.guessCounter;
            correct = saved.correct;
            answer = saved.answer;
            imageVersion = saved.guessCounter;

            guessStatus = guessStatus.map(
                (_, i) => !!saved.guessRows[i]?.correct,
            );

            guessArray = saved.guessRows
                .filter(
                    (row: GuessRowState | null): row is GuessRowState =>
                        row !== null,
                )
                .map((row: GuessRowState) => ({
                    id: row.id,
                    common_name: row.common_name,
                    scientific_name: row.scientific_name,
                    order: row.order,
                    family: row.family,
                    genus: row.genus,
                }));

            hydrated = true;
        }
    });

    const guessMatchesBirdName = (guess: string, bird: Bird) => {
        if (guessArray.some((g) => g.id === bird.id)) return;
        return (
            bird.common_name.toLowerCase().includes(guess.toLowerCase())

        );
    };

    const highlightMatch = (name: string, query: string) => {
        if (!query) return [{ text: name, match: false }];
        const matchStart = name.toLowerCase().indexOf(query.toLowerCase());
        if (matchStart === -1) return [{ text: name, match: false }];
        const matchEnd = matchStart + query.length;
        return [
            { text: name.slice(0, matchStart), match: false },
            { text: name.slice(matchStart, matchEnd), match: true },
            { text: name.slice(matchEnd), match: false },
        ].filter((segment) => segment.text !== "");
    };

    const handleInput = (event: KeyboardEvent) => {
        if (["Enter", "ArrowUp", "ArrowDown", "Escape"].includes(event.key))
            return;
        autoCompleteClicked = false;
        if (allBirds && input && input !== "") {
            possibleOptions = [];
            for (const elem of allBirds) {
                if (guessMatchesBirdName(input, elem)) {
                    possibleOptions.push(elem);
                }
            }
            highlightedIndex = possibleOptions.length > 0 ? 0 : -1;
        }
    };

    const handleKeydown = (event: KeyboardEvent) => {
        if (!possibleOptions || possibleOptions.length === 0 || autoCompleteClicked)
            return;

        if (event.key === "ArrowDown") {
            event.preventDefault();
            highlightedIndex = Math.min(
                highlightedIndex + 1,
                possibleOptions.length - 1,
            );
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            highlightedIndex = Math.max(highlightedIndex - 1, 0);
        } else if (event.key === "Enter") {
            if (highlightedIndex >= 0 && highlightedIndex < possibleOptions.length) {
                event.preventDefault();
                autoCompleteGuess(possibleOptions[highlightedIndex]);
            }
        } else if (event.key === "Escape") {
            autoCompleteClicked = true;
            highlightedIndex = -1;
        }
    };

    const autoCompleteGuess = (bird: Bird) => {
        if (!roundID) return;
        const currentRoundID = roundID;
        currentGuess = {
            guess: {
                round_id: currentRoundID,
                guess_id: bird.id,
            },
            bird: bird,
        };
        input = bird.common_name;
        autoCompleteClicked = true;
        highlightedIndex = -1;
    };

    const restartRound = async () => {
        clearProgress();
        const fresh = await start();
        roundID = fresh.round_id;

        guessRows = Array(MAXGUESSES).fill(null);
        guessCounter = 0;
        correct = false;
        answer = null;
        guessStatus = guessStatus.map(() => false);
        guessArray = [];
        imageVersion = 0;

        saveProgress({
            date: todayKey(),
            roundId: roundID,
            guessRows,
            guessCounter,
            correct,
            answer,
        });
    };

    const checkGuess = async (fullGuess: FullGuess) => {
        if (guessCounter >= MAXGUESSES || correct || !roundID) return;
        const currentRoundID = roundID;

        let res;
        try {
            res = await postGuess(fullGuess.guess);
        } catch (err) {
            // The server no longer knows this round (e.g. it restarted since
            // we resumed it from localStorage) - start a fresh one instead
            // of getting stuck.
            await restartRound();
            return;
        }

        correct = res.correct;
        imageVersion += 1;

        if (res.finished && !answer) {
            answer = await getAnswer(currentRoundID);
        }

        guessCounter += 1;
        input = "";

        guessStatus[guessCounter - 1] = correct;
        guessArray = [...guessArray, fullGuess.bird];

        guessRows = [...guessRows];
        guessRows[guessCounter - 1] = {
            ...fullGuess.bird,
            hints: res.hints,
            correct: res.correct,
        };

        saveProgress({
            date: todayKey(),
            roundId: currentRoundID,
            guessRows,
            guessCounter,
            correct,
            answer,
        });
    };

    const submitGuess = () => {
        if (currentGuess.guess.guess_id !== "") {
            checkGuess(currentGuess);
        }
    };

    const buildShareText = () => {
        const today = new Date().toISOString().slice(0, 10);
        const score = correct ? guessCounter : "X";

        const rows = guessRows
            .filter((row) => row)
            .map((row) => {
                const squares = [
                    row.hints.order,
                    row.hints.family,
                    row.hints.genus,
                    row.correct,
                ].map((hit) => (hit ? "🟩" : "⬛"));
                return squares.join("");
            });

        return [`Birdle ${today} ${score}/${MAXGUESSES}`, "", ...rows].join(
            "\n",
        );
    };

    const shareResults = () => {
        navigator.clipboard.writeText(buildShareText()).then(() => {
            shareCopied = true;
            setTimeout(() => (shareCopied = false), 2000);
        });
    };
</script>

{#if roundID}
    <div class="image-hint">
        <ImageHint {roundID} {imageVersion} />
    </div>
{/if}

{#each guessRows as guessRow, i}
    {#if guessRow}
        <div class="guessRowFilled {guessStatus[i] ? 'correct' : 'wrong'}">
            <AnswerText guess={guessRow} />
        </div>
    {:else}
        <div class="guessRowEmpty"></div>
    {/if}
{/each}

<div class="guessDiv">
    <div class="autoCompleteContainer">
        {#if !correct && guessCounter < MAXGUESSES}
            <input
                bind:value={input}
                bind:this={inputField}
                class="guessInput"
                onkeyup={handleInput}
                onkeydown={handleKeydown}
                placeholder="Name that bird..."
                role="combobox"
                aria-expanded={allBirds !== null &&
                    allBirds.length > 0 &&
                    !autoCompleteClicked}
                aria-controls="autoCompleteListbox"
                aria-activedescendant={highlightedIndex >= 0
                    ? `autoCompleteOption-${highlightedIndex}`
                    : undefined}
            />
            {#if allBirds !== null && allBirds.length > 0 && !autoCompleteClicked}
                <div
                    class="autoCompleteDropdown"
                    id="autoCompleteListbox"
                    role="listbox"
                >
                    {#each possibleOptions as possibleBird, i}
                        <!-- svelte-ignore a11y_click_events_have_key_events -->
                        <div
                            id="autoCompleteOption-{i}"
                            class="autoCompleteRow {i === highlightedIndex
                                ? 'highlighted'
                                : ''}"
                            role="option"
                            tabindex="-1"
                            aria-selected={i === highlightedIndex}
                            onmouseenter={() => (highlightedIndex = i)}
                            onclick={() => autoCompleteGuess(possibleBird)}
                        >
                            {#each highlightMatch(possibleBird.common_name, input) as segment}{#if segment.match}<b>{segment.text}</b>{:else}{segment.text}{/if}{/each} - {possibleBird.scientific_name.toLowerCase()}
                        </div>
                    {/each}
                </div>
            {/if}
        {:else if correct}
            <div>Well Done!!!</div>
            <button class="shareButton" onclick={shareResults}>
                {shareCopied ? "Copied!" : "Share Results"}
            </button>
        {:else}
            <div>
                No more guesses! The bird was {answer?.common_name}.
            </div>
            <button class="shareButton" onclick={shareResults}>
                {shareCopied ? "Copied!" : "Share Results"}
            </button>
        {/if}
    </div>
</div>

<div>
    <button
        class="guessButton"
        hidden={correct || guessCounter >= MAXGUESSES}
        onclick={submitGuess}
    >
        Submit Guess
    </button>
</div>

<style>
    .correct {
        border: 3px solid #538d4e;
    }

    .wrong {
        border: 3px solid red;
    }
</style>
