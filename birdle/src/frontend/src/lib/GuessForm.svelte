<script lang="ts">
    import AnswerText from "./AnswerText.svelte";
    import { fade } from "svelte/transition";
    import type { Bird } from "../types";
    import AutoCompleteRow from "./AutoCompleteRow.svelte";

    let prop = $props();

    let xVisible = $state(false);
    let tickVisible = $state(false);

    let correct = $state(false);

    let birdOfTheDay = $state<Bird | null>(null);

    let allBirds = $state<Bird[] | null>(null);

    let possibleOptions = $state<Bird[] | null>(null);

    let guessArray = new Array<String>();

    $effect(() => {
        if (prop.bird) {
            birdOfTheDay = prop.bird;
        }
        if (prop.allBirds) {
            allBirds = prop.allBirds;
        }
    });

    $effect(() => {
        if (prop.reset === true) {
            correct = false;
            xVisible = false;
            tickVisible = false;
            guessCounter = 0;
        }
    });

    let inputField = $state();

    let guessCounter = $state(0);

    let guess = $state<Bird>({
        id: '',
        common_name: '',
        scientific_name: '',
        audio_path: '',
        order: '',
        family: '',
        genus: '',
        image_path: ''
    });
    let input = $state("")

    const MAXGUESSES = 6


    const submitGuess = () => {
        checkGuess(guess);
    };
    const handleInput = (event) => {
        if (event.key !== "Enter") {
            autoCompleteClicked = false;
            possibleOptions = new Array<Bird>();
            if (allBirds) {
                let currentGuess = input;
                for (const elem of allBirds) {
                    if (
                        currentGuess &&
                        currentGuess !== "" &&
                        (guessMatchesBirdName(currentGuess, elem))
                        
                    ) {
                        possibleOptions.push(elem);
                    } 
                }
            }

            return;
        }
    };

    const guessMatchesBirdName = (guess, bird) => {


        return bird.common_name.toLowerCase().includes(guess.toLowerCase()) ||
        bird.scientific_name.toLowerCase().includes(guess.toLowerCase());
    };

    const checkGuess = (guess) => {
        guessArray = [...guessArray, guess];

        if (guess === birdOfTheDay) {
            inputField.value = "";
            xVisible = false;
            tickVisible = true;
            correct = true;
        } else {
            tickVisible = false;
            xVisible = true;
        }
        guessCounter += 1;
        inputField.value = "";
    };

    $effect(() => {
        if (guessCounter >= MAXGUESSES) {
            guessCounter = 0;
        }
    });

    let autoCompleteClicked = $state(false);

    const autoCompleteGuess = (bird) => {
        guess = bird;
        input = bird.common_name
        autoCompleteClicked = true;

    };

    let guessRows = $state(Array(MAXGUESSES))
    $effect(()=> {
        if(guessCounter >  0){
            guessRows = Array(MAXGUESSES).fill(null).map((_, i) => guessArray[i] || null);
        }
    })

</script>


{#each guessRows as guess, i}
  {#if guess}
    <div class="guessRowFilled">
      <AnswerText guess={guess} answer={birdOfTheDay} />
    </div>
  {:else}
    <div class="guessRowEmpty">
    </div>
  {/if}
{/each}
<div class="guessDiv">
    <div class="autoCompleteContainer">
        {#if !correct}
            <input
                bind:value={input}
                bind:this={inputField}
                class="guessInput"
                oninput={handleInput}
                placeholder="Name that bird..."
                hidden={correct}
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
        {:else}
            <div>Well Done !!!</div>
        {/if}
    </div>
</div>
<br />

<div class="spacing">
    <button class="guessButton" hidden={correct} onclick={() => submitGuess()}
        >Submit Guess</button
    >
</div>
