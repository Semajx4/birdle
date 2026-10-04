<script lang="ts">
    import { onMount } from "svelte";
    import { msUntilNextBird } from "./progress";

    let untilNextBird = $state(msUntilNextBird());

    const formatCountdown = (ms: number) => {
        const total = Math.max(0, Math.floor(ms / 1000));
        const pad = (n: number) => String(n).padStart(2, "0");
        return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
    };

    onMount(() => {
        const timer = setInterval(() => (untilNextBird = msUntilNextBird()), 1000);
        return () => clearInterval(timer);
    });
</script>

<p class="countdown">
    Next bird in
    <span class="countdown-time">{formatCountdown(untilNextBird)}</span>
</p>

<style>
    .countdown {
        margin: 1rem 0 0;
        font-size: 0.85rem;
        color: rgba(255, 255, 255, 0.6);
    }

    .countdown-time {
        display: block;
        margin-top: 2px;
        font-size: 1.4rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        color: rgba(255, 255, 255, 0.87);
        font-variant-numeric: tabular-nums;
    }
</style>
