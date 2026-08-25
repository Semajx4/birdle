<script lang="ts">
    import { getAudioUrl } from "../api";
    let props = $props();
    let progress = $state(0);
    let isPlaying = $state(false);
    let dragging = $state(false);
    let startOffset = 2;
    let duration = 30;
    let audio: HTMLAudioElement;
    let animationFrame: number;
    let playbackTimeout: ReturnType<typeof setTimeout>;
    let elapsedAtPause = 0;

    function startTimers() {
        cancelAnimationFrame(animationFrame);
        clearTimeout(playbackTimeout);

        const startTime = performance.now();
        const base = elapsedAtPause;

        playbackTimeout = setTimeout(
            () => {
                audio.pause();
                audio.currentTime = 0;
                progress = 0;
                elapsedAtPause = 0;
                isPlaying = false;
                cancelAnimationFrame(animationFrame);
            },
            Math.max(duration - base, 0) * 1000,
        );

        function updateProgress(timestamp: number) {
            const elapsed = base + (timestamp - startTime) / 1000;
            if (!dragging) {
                progress = +Math.min((elapsed / duration) * 100, 100).toFixed(2);
            }
            if (elapsed < duration) {
                animationFrame = requestAnimationFrame(updateProgress);
            }
        }
        animationFrame = requestAnimationFrame(updateProgress);
    }

    function play() {
        if (!audio) {
            audio = new Audio(getAudioUrl(props.roundID));

            audio.addEventListener("loadedmetadata", () => {
                audio.currentTime = startOffset + elapsedAtPause;
                audio.play();
                isPlaying = true;
                startTimers();
            });
            return;
        }

        audio.currentTime = startOffset + elapsedAtPause;
        audio.play();
        isPlaying = true;
        startTimers();
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

    function seek(fraction: number) {
        const clamped = Math.min(Math.max(fraction, 0), 1);
        elapsedAtPause = clamped * duration;
        progress = +(clamped * 100).toFixed(2);

        if (audio) {
            audio.currentTime = startOffset + elapsedAtPause;
        }

        if (isPlaying) {
            startTimers();
        }
    }

    function handleSeekStart() {
        dragging = true;
    }

    function handleSeekInput(event: Event) {
        progress = Number((event.target as HTMLInputElement).value);
    }

    function handleSeekCommit(event: Event) {
        const value = Number((event.target as HTMLInputElement).value);
        dragging = false;
        seek(value / 100);
    }
</script>

<div class="audioDiv">
    <div class="playButtonDiv">
        {#if isPlaying}
            <button onclick={pause} class="playButton" aria-label="Pause">
                <span class="icon-pause"><span></span><span></span></span>
            </button>
        {:else}
            <button onclick={play} class="playButton" aria-label="Play">
                <span class="icon-play"></span>
            </button>
        {/if}
    </div>
    <div class="progBarDiv">
        <input
            type="range"
            class="progress-slider"
            style="--progress: {progress}%"
            min="0"
            max="100"
            step="0.1"
            value={progress}
            onpointerdown={handleSeekStart}
            oninput={handleSeekInput}
            onchange={handleSeekCommit}
            aria-label="Seek audio"
        />
    </div>
</div>
