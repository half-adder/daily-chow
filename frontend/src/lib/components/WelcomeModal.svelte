<script lang="ts">
	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onclose}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<h3>Welcome to Daily Chow</h3>
			<button class="close-btn" onclick={onclose}>&times;</button>
		</div>

		<div class="modal-body">
			<p class="intro">A meal solver that finds the right amount of each ingredient to hit your nutrition targets.</p>

			<dl>
				<dt>Targets</dt>
				<dd>Set your daily calories, protein, fiber, and carb/protein/fat ratio.</dd>

				<dt>Ingredients</dt>
				<dd>Add foods and set min/max gram bounds. The solver figures out exactly how much of each.</dd>

				<dt>Pinned Meals</dt>
				<dd>Already know what you're eating for one meal? Pin it, and the solver plans around it.</dd>

				<dt>Micronutrients</dt>
				<dd>Track 19 vitamins and minerals. The solver optimizes for coverage across all of them.</dd>
			</dl>
		</div>

		<div class="modal-footer">
			<button class="got-it-btn" onclick={onclose}>Got it</button>
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: var(--shadow-overlay);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 100;
		backdrop-filter: blur(2px);
	}

	.modal {
		background: var(--bg-panel);
		border: 1px solid var(--border);
		border-radius: 12px;
		width: 420px;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 20px 60px var(--shadow-modal);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px 0;
	}

	h3 {
		margin: 0;
		color: var(--text-primary);
		font-size: 16px;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--text-muted);
		font-size: 22px;
		cursor: pointer;
		padding: 0 4px;
	}

	.close-btn:hover {
		color: var(--text-primary);
	}

	.modal-body {
		padding: 16px 20px;
		overflow-y: auto;
	}

	.intro {
		margin: 0 0 12px;
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.5;
	}

	dl {
		margin: 0;
	}

	dt {
		font-weight: 600;
		color: var(--text-primary);
		font-size: 13px;
		margin-top: 10px;
	}

	dt:first-of-type {
		margin-top: 0;
	}

	dd {
		margin: 2px 0 0;
		color: var(--text-secondary);
		font-size: 13px;
		line-height: 1.4;
	}

	.modal-footer {
		padding: 12px 20px 16px;
		display: flex;
		justify-content: flex-end;
	}

	.got-it-btn {
		background: #3b82f6;
		color: #fff;
		border: none;
		border-radius: 8px;
		padding: 8px 20px;
		font-size: 14px;
		font-weight: 500;
		cursor: pointer;
	}

	.got-it-btn:hover {
		background: #2563eb;
	}
</style>
