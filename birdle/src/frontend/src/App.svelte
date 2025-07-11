<script>
    import { onMount, tick } from 'svelte';
  import AudioSnippet from './lib/AudioSnippet.svelte';
  import GuessForm from './lib/GuessForm.svelte';

  let audioPath = $state("")

  let birdOfTheDay = $state(null);

  let reset = $state(false);


  async function getRandomBird() {
    const res = await fetch("http://localhost:3000/api/bird/random");
    if (!res.ok) throw new Error("Failed to fetch bird data");
    return await res.json();
  }

const updateBirdOfTheDay = async () => {
  const bird = await getRandomBird();
  birdOfTheDay = bird;
  audioPath = bird.audio_path

  reset = true;
  await tick();     
  reset = false;    
}

onMount(async() => {
 await updateBirdOfTheDay()
})


</script>


<main class="container">
  <div class="title-bar">
    <h1>Birdle 2.0</h1>
    <button class="refresh-btn" on:click={updateBirdOfTheDay}>🔁</button>
  </div>

  <div class="card">
    <AudioSnippet audioSource={audioPath} />
  </div>

  <div class="card">
    <GuessForm reset={reset} bird={birdOfTheDay}/>
  </div>
</main>

<style>


</style>