<script lang="ts">
    import { getImageUrl } from "../api";

    const prop = $props();

    let roundID = $state<string>("");
    let guessNumber = $state<number>(0);

    // cache buster
    let refreshKey = $state<number>(0);

    $effect(() => {
        if (prop.roundID) {
            roundID = prop.roundID;
        }

        if (prop.imageVersion !== undefined) {
            guessNumber = prop.imageVersion;
        }

        refreshKey = guessNumber;
    });

    const imageUrl = $derived(
        roundID ? `${getImageUrl(roundID)}?v=${refreshKey}` : "",
    );
</script>

{#if roundID}
    <div>
        <img src={imageUrl} class="bird-image" alt="Bird of the round" />
    </div>
{/if}

<style>
</style>
