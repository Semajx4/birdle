<script lang="ts">
    import AnswerText from "./AnswerText.svelte";
    import type { Bird } from "../types";
    import ImageHint from "./ImageHint.svelte";

    let prop = $props();

    const MAXGUESSES = 5;
    let correct = $state(false);
    let guessStatus = $state<boolean[]>([
        false,
        false,
        false,
        false,
        false,
        false,
    ]);
    let birdOfTheDay = $state<Bird | null>(null);
    let allBirds = $state<Bird[] | null>(null);
    let possibleOptions = $state<Bird[] | null>(null);
    let guessArray = $state(new Array<Bird>());
    let inputField = $state<HTMLInputElement>();
    let guessCounter = $state(0);
    let input = $state("");
    let autoCompleteClicked = $state(false);
    let guessRows = $state(Array(MAXGUESSES).fill(null));

    let currentGuess = $state<Bird>({
        id: "",
        common_name: "",
        scientific_name: "",
        audio_path: "",
        genus: "",
        order: "",
        family: "",
        image_path: "",
    });

    $effect(() => {
        if (prop.bird) birdOfTheDay = prop.bird;
        if (prop.allBirds) allBirds = prop.allBirds;
    });

    $effect(() => {
        if (prop.reset === true) {
            correct = false;
            guessCounter = 0;
            guessArray = [];
            guessRows = Array(MAXGUESSES).fill(null);
            guessStatus = [false, false, false, false, false, false];
            input = "";
            currentGuess = emptyBird();
            possibleOptions = null;
            autoCompleteClicked = false;
        }
    });

    $effect(() => {
        if (guessCounter > 0) {
            guessRows = Array(MAXGUESSES)
                .fill(null)
                .map((_, i) => guessArray[i] || null);
        }
    });

    function emptyBird(): Bird {
        return {
            id: "",
            common_name: "",
            scientific_name: "",
            audio_path: "",
            genus: "",
            order: "",
            family: "",
            image_path: "",
        };
    }

    const guessMatchesBirdName = (guess: string, bird: Bird) => {
        if (guessArray.some((g) => g.id === bird.id)) return;
        return (
            bird.common_name.toLowerCase().includes(guess.toLowerCase()) ||
            bird.scientific_name.toLowerCase().includes(guess.toLowerCase())
        );
    };

    const handleInput = (event: KeyboardEvent) => {
        if (event.key === "Enter") return;
        autoCompleteClicked = false;
        possibleOptions = [];
        if (allBirds && input && input !== "") {
            for (const elem of allBirds) {
                if (guessMatchesBirdName(input, elem)) {
                    possibleOptions.push(elem);
                }
            }
        }
    };

    const autoCompleteGuess = (bird: Bird) => {
        currentGuess = bird;
        input = bird.common_name;
        autoCompleteClicked = true;
        possibleOptions = null;
    };

    const checkGuess = (guess: Bird) => {
        if (guessCounter >= MAXGUESSES || correct) return;

        guessArray = [...guessArray, guess];
        guessStatus[guessCounter] = guess.id === birdOfTheDay?.id;

        if (guess.id === birdOfTheDay?.id) {
            correct = true;
        }

        guessCounter += 1;
        input = "";
        currentGuess = emptyBird();
        possibleOptions = null;
        autoCompleteClicked = false;

        if (inputField) {
            inputField.value = "";
        }
    };

    const submitGuess = () => {
        if (currentGuess.id !== "") {
            checkGuess(currentGuess);
        }
    };
</script>

{#if birdOfTheDay !== null}
    <div class="image-hint">
        <ImageHint
            bird={birdOfTheDay}
            guessNumber={guessCounter}
            correct={guessStatus}
        />
    </div>
{/if}

{#each guessRows as guessRow, i}
    {#if guessRow}
        <div class="guessRowFilled {guessStatus[i] ? 'correct' : 'wrong'}">
            <AnswerText guess={guessRow} answer={birdOfTheDay} />
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
            {#if possibleOptions !== null && possibleOptions.length > 0 && !autoCompleteClicked}
                <div class="autoCompleteDropdown">
                    {#each possibleOptions as possibleBird}
                        <div
                            class="autoCompleteRow"
                            onclick={() => autoCompleteGuess(possibleBird)}
                        >
                            {possibleBird.common_name} - {possibleBird.scientific_name.toLowerCase()}
                        </div>
                    {/each}
                </div>
            {/if}
        {:else if correct}
            <div>Well Done!!!</div>
        {:else}
            <div>
                No more guesses! The bird was {birdOfTheDay?.common_name}.
            </div>
        {/if}
    </div>
</div>

<div>
    <button
        class="guessButton"
        hidden={correct || guessCounter >= MAXGUESSES}
        onclick={submitGuess}
        disabled={currentGuess.id === ""}
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
