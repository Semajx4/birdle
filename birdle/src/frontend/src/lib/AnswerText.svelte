<script lang="ts">
    let prop = $props();

    let guess = prop.guess;
    let answer = prop.answer;


    const sameOrder = answer.order === guess.order
    const sameFamily = answer.family === guess.family
    const sameGenus = answer.genus === guess.genus


</script>

<div class="guess-card" >
  <div class="name-line">
    <b>{guess.common_name}</b>
    <p><em>{guess.scientific_name}</em></p>
  </div>

    {#if sameFamily && sameFamily && sameGenus}
        <div class="taxonomy-line">
            <h6 class="correct">{guess.order}</h6>
            <h6 class="correct">{guess.family}</h6>
            <h6 class="correct">{guess.genus}</h6>
        </div>

    {:else}
      <div class="taxonomy-line">
        {#if sameOrder}
            <h6 class="success">{guess.order}</h6>
        {:else}
            <h6 class="failure">{guess.order}</h6>
        {/if}
        {#if sameFamily}
            <h6 class="success">{guess.family}</h6>
        {:else}
            <h6 class="failure">{guess.family}</h6>
        {/if}

        {#if sameGenus}
            <h6 class="success">{guess.genus}</h6>
        {:else}
            <h6 class="failure">{guess.genus}</h6>
        {/if}
      </div>
    {/if}
</div>
<style>
    .name-line {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.name-line p {
  font-style: italic;
  margin: 0;
}

.taxonomy-line {
  display: flex;
  gap: 1rem;
  margin-top: 0.25rem;
}

.taxonomy-line h6 {
  margin: 0;
  font-style: italic;
}

.success {
    color: #B59F3B;
}
.failure {
    color: red;
}

.correct {
    color: #538D4E;
}
</style>
