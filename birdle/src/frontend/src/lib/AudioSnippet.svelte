<script lang="ts">
let props = $props()
    let progress = $state(0);
    let isPlaying = $state(false);
    let startOffset = 2;
    let duration = 30;
    let audio: HTMLAudioElement;
    let animationFrame: number;
    let playbackTimeout: ReturnType<typeof setTimeout>;
    let elapsedAtPause = 0;

    function play() {
        if (!audio) {
            audio = new Audio(`${props.audioSource}`);
            audio.addEventListener('loadedmetadata', () => {
                    startPlayback();
                    });
        } else {
            startPlayback();
        }
    }

function startPlayback() {
    audio.currentTime = startOffset + elapsedAtPause;
    audio.play();
    isPlaying = true;
    const startTime = performance.now();

    playbackTimeout = setTimeout(() => {
            audio.pause();
            audio.currentTime = 0;
            progress = 0;
            elapsedAtPause = 0;
            isPlaying = false;
            cancelAnimationFrame(animationFrame);
            }, (duration - elapsedAtPause) * 1000);

    function updateProgress(timestamp: number) {
        const elapsed = elapsedAtPause + (timestamp - startTime) / 1000;
        progress = +Math.min((elapsed / duration) * 100, 100).toFixed(2);
        if (elapsed < duration) {
            animationFrame = requestAnimationFrame(updateProgress);
        }
    }
    animationFrame = requestAnimationFrame(updateProgress);
}

function pause() {
    if (audio) {
        elapsedAtPause = audio.currentTime - startOffset;
        audio.pause();
        isPlaying = false;
        cancelAnimationFrame(animationFrame);
        clearTimeout(playbackTimeout);
    }
}
</script>

<div class="audioDiv">
<div class="playButtonDiv">
{#if isPlaying}
<button onclick={pause} class="playButton">⏸</button>
{:else}
<button onclick={play} class="playButton">▶</button>
{/if}
</div>
<div class="progBarDiv">
<div class="progress-bar">
<div class="progress" style="width: {progress}%"></div>
</div>
</div>
</div>
