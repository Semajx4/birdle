<script lang="ts">
    import { onMount } from "svelte";
    import type { Bird } from "../types";
    let prop = $props();
    let self = $state<Bird | null>(null);
</script>

<div class="autoCompleteRow">
    {prop.bird.common_name} - {prop.bird.scientific_name.toLowerCase()}
</div>
