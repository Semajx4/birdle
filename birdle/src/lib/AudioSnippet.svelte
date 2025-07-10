<script lang="ts">
function play() {
    const audio = new Audio(`/audio/}`);
    audio.play();
  }
</script>
<div>

<button on:click={play} class="playButton ">🐦🔊 Play</button>
</div>