<script lang="ts">
	import { fade } from 'svelte/transition';

    let prop = $props();

	let xVisible = $state(false);
	let tickVisible = $state(false);

    let correct = $state(false);

    let birdOfTheDay = $state(null);

   $effect(() => {
    if (prop.bird) {
        birdOfTheDay = prop.bird;
    }
    });


    $effect(() => {
        if (prop.reset === true) {
            correct = false;
            xVisible = false;
            tickVisible = false;
            guessCounter = 0;
            guess = ""
        }
    });




    let inputField = $state()

    let guessCounter = $state(0)

    let guess
    const submitGuess = () => {
        checkGuess(guess.toLowerCase())
    }
    const handleInput = (event) => {
        if(event.key !== 'Enter') return;
        submitGuess()
    }

    const checkGuess = (guess) => {
        if (guess === birdOfTheDay.common_name.toLowerCase() || guess === birdOfTheDay.scientific_name.toLowerCase) {
            inputField.value = ""
            xVisible=false
            tickVisible = true;
            correct = true
        } else {
            tickVisible=false
            xVisible=true
        }
        guessCounter+=1;
        inputField.value = ""
    }
    

    $effect(() => {
        if(guessCounter >= 6) {
            alert ("you lose")
            guessCounter = 0
        }
    })
</script>

<div class="guessDiv">
    <div class="guessInputDiv">
        {#if !correct}
        <input bind:value={
            () => guess,
            (v) => guess = v.toLowerCase()}
            bind:this={inputField}
            class="guessInput"
            on:keydown={handleInput}
            placeholder="Name that bird..."
            hidden={correct}
        />
        {:else}
        <div>
            Well Done !!!
        </div>
        {/if}
    </div>
    <div class="guessIndicatorDiv">

    {#if xVisible}
    <h1 in:fade 
    class="guessIndicator" 
    >❌</h1>
    {/if}

    {#if tickVisible}
    <h1 in:fade
    class="guessIndicator" 
    >✅</h1>
    {/if}

    </div>
</div>

<div class="spacing">
    <h1>Guesses: {guessCounter}/6</h1>
    <button class="guessButton" hidden={correct} on:click={submitGuess}>Submit Guess</button>
</div>
