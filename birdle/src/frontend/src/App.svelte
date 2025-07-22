<script lang="ts">
  import { onMount, tick } from "svelte";
  import type { Bird } from "./types";
  import AudioSnippet from "./lib/AudioSnippet.svelte";
  import GuessForm from "./lib/GuessForm.svelte";

  let audioPath = $state("");

  let birdOfTheDay = $state(null);
  let allBirds = $state<Bird[] | null>(null);
  let reset = $state(false);

  async function getRandomBird() {
    const res = await fetch("http://localhost:3000/api/bird/random");
    if (!res.ok) throw new Error("Failed to fetch bird data");
    return await res.json();
  }

  async function getAllBirds() {
    const res = await fetch("http://localhost:3000/api/bird/all");
    if (!res.ok) throw new Error("Failed to fetch bird data");
    const data = await res.json();
    return data as Bird[];
  }

  const updateAllBirds = async () => {
    allBirds = await getAllBirds();
  };

  const updateBirdOfTheDay = async () => {
    const bird = await getRandomBird();
    birdOfTheDay = bird;
    console.log(birdOfTheDay);
    audioPath = bird.audio_path;

    reset = true;
    await tick();
    reset = false;
  };

  onMount(async () => {
    await updateBirdOfTheDay();
    await updateAllBirds();
  });
</script>

<main class="container">
  <div class="title-bar">
    <h1>Birdle 2.0</h1>
    <button class="refresh-btn" onclick={updateBirdOfTheDay}>🔁</button>
  </div>

  <div class="card">
    <AudioSnippet audioSource={audioPath} />
  </div>

  <div class="card">
    <GuessForm {reset} bird={birdOfTheDay} {allBirds} />
  </div>
</main>

<style>
</style>
