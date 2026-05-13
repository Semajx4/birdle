<script lang="ts">
    const BASE_PATH = "/images/";
    const prop = $props();

    const maxBlur = 10;

    let imagePath = $state<string>("");
    let blurAmount = $state<number>(10); // start fully blurred

    $effect(() => {
        if (prop.bird) {
            imagePath = BASE_PATH + prop.bird.image_path;
        }
    });

    $effect(() => {
        blurAmount = prop.correct[prop.guessNumber - 1]
            ? 0
            : Math.max(0, maxBlur - prop.guessNumber * 2);
    });
</script>

<div>
    <img
        src={imagePath}
        class="blurred-image bird-image"
        style="filter: blur({blurAmount}px);"
        alt="Blurred image of the mystery bird"
    />
</div>

<style>
</style>
