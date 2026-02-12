<script lang="ts">
	let { children } = $props();
</script>

<svelte:head>
	<title>Daily Chow</title>
</svelte:head>

{@render children()}
