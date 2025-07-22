<script lang="ts">

    const BASE_PATH = "../public/images/";
    const prop = $props();

    const maxBlur = 10;

    let imagePath = $state<string>('');
    let blurAmount = $state<number>(10);  // start fully blurred



    $effect(() => {
        if (prop.bird) {
            imagePath = BASE_PATH + prop.bird.image_path;
        }
    });

    $effect(() => {
        blurAmount = prop.correct[prop.guessNumber-1] ? 0 :  Math.max(0, maxBlur - prop.guessNumber * 2);
    });



</script>


<div>
    <img src={imagePath}
         class="blurred-image bird-image "
         style="filter: blur({blurAmount}px);"
         alt="Blurred image of the mystery bird"
    />
</div>


<style>
    .blurred-image {
        transition: filter 0.3s ease;
    }
    .bird-image {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;              /* ensures it fills box without distortion */

        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
        overflow: hidden;              /* if nested inside a div, use this there too */
    }

    .bird-image:hover {
        transform: scale(1.05);       /* gentle zoom */
        box-shadow: 0 8px 16px rgba(0,0,0,0.15); /* stronger shadow */
    }
</style>