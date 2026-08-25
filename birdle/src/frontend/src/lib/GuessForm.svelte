<script lang="ts">
    import AnswerText from "./AnswerText.svelte";
    import type { Bird, FullGuess } from "../types";
    import ImageHint from "./ImageHint.svelte";
    import { postGuess, getAnswer } from "../api";

    let prop = $props();

    const MAXGUESSES = 5;

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
        if (event.key === "Enter") return;
        autoCompleteClicked = false;
        if (allBirds && input && input !== "") {
            possibleOptions = [];
            for (const elem of allBirds) {
                if (guessMatchesBirdName(input, elem)) {
                    possibleOptions.push(elem);
                }
            }
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
    };

    const checkGuess = async (fullGuess: FullGuess) => {
        if (guessCounter >= MAXGUESSES || correct || !roundID) return;
        const currentRoundID = roundID;

        const res = await postGuess(fullGuess.guess);

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
                placeholder="Name that bird..."
            />
            {#if allBirds !== null && allBirds.length > 0 && !autoCompleteClicked}
                <div class="autoCompleteDropdown">
                    {#each possibleOptions as possibleBird}
                        <div
                            class="autoCompleteRow"
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
