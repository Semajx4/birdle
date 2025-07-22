<script lang="ts">
    let props = $props()
    let progress = $state(0);
    let startOffset = 2
  let duration = 30; // play only 3 seconds
  let audio: HTMLAudioElement;
  let animationFrame: number;

  function play() {
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      cancelAnimationFrame(animationFrame);
    }

    audio = new Audio(`${props.audioSource}`);
    audio.addEventListener('loadedmetadata', () => {
      audio.currentTime = startOffset; // Start from 2s
      audio.play();

      const startTime = performance.now();

      // Stop after `duration` seconds
      setTimeout(() => {
        audio.pause();
        audio.currentTime = 0;
        progress = 0;
        cancelAnimationFrame(animationFrame);
      }, duration * 1000);

      // Progress update
      function updateProgress(timestamp: number) {
        const elapsed = (timestamp - startTime) / 1000;
        progress = +Math.min((elapsed / duration) * 100, 100).toFixed(2);
        if (elapsed < duration) {
          animationFrame = requestAnimationFrame(updateProgress);
        }
      }

      animationFrame = requestAnimationFrame(updateProgress);
  });
  }
</script>

<style>
 
</style>

<div class="audioDiv">
  <div class="playButtonDiv">
    <button onclick={play} class="playButton">▶</button>
  </div>
  <div class="progBarDiv">
  <div class="progress-bar">
    <div class="progress" style="width: {progress}%"></div>
  </div>

  </div>
</div>