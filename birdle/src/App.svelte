<script>
  import svelteLogo from './assets/svelte.svg'
  import duckImg from './assets/duck.jpg'
  import viteLogo from '/vite.svg'
  import Counter from './lib/Counter.svelte'
    import AudioSnippet from './lib/AudioSnippet.svelte';
    import GuessForm from './lib/GuessForm.svelte';
</script>

<main>
  <div>
      <img src={duckImg} class="logo" alt="Svelte Logo" />
  </div>
  <h1>Birdle 2.0</h1>

<div class="card">
    <AudioSnippet />
  </div>

  <div class="card">
    <GuessForm />
  </div>

</main>

<style>
  .logo {
    height: 10em;
    padding: 1.5em;
    will-change: filter;
    transition: filter 300ms;
  }
  .logo:hover {
    filter: drop-shadow(0 0 2em #646cffaa);
  }

</style>
