<script lang="ts">
	import { fade } from 'svelte/transition';

	let xVisible = $state(false);
	let tickVisible = $state(false);


    let answer = "kea"
    let inputField

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
        if (guess === answer) {
            xVisible=false
            tickVisible = true;
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

<div>
    <input bind:value={
        () => guess,
        (v) => guess = v.toLowerCase()}
        bind:this={inputField}
        class="guessInput"
        on:keydown={handleInput}
    />
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
<br>
<br>
<!-- svelte-ignore event_directive_deprecated -->
<button on:click={submitGuess}> Guess </button>
<h1>Guesses: {guessCounter}/6</h1>
