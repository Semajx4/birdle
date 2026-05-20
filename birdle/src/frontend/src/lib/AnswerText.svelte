<script lang="ts">
    let prop = $props();

    const guess = prop.guess;
    const hints = prop.guess.hints;
</script>

<div class="guess-card">
    <div class="name-line">
        <b>{guess.common_name}</b>
        <p><em>{guess.scientific_name}</em></p>
    </div>

    <div class="taxonomy-line">
        <h6 class={hints.order ? "correct" : "wrong"}>
            {guess.order}
        </h6>

        <h6 class={hints.family ? "correct" : "wrong"}>
            {guess.family}
        </h6>

        <h6 class={hints.genus ? "correct" : "wrong"}>
            {guess.genus}
        </h6>
    </div>
</div>

<style>
    .correct {
        color: #538d4e;
    }

    .wrong {
        color: #b91c1c;
    }
</style>
