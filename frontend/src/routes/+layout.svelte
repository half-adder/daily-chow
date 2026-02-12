<script lang="ts">
	let { children } = $props();
</script>

<svelte:head>
	<title>Daily Chow</title>
</svelte:head>

{@render children()}

<style>
	:global(:root) {
		/* Backgrounds */
		--bg-body: #0a0a0a;
		--bg-panel: #0f172a;
		--bg-input: #1e1e2e;
		--bg-hover: #1a1a2e;
		--bg-detail: #111827;
		--bg-track: #2a2a2a;
		--bg-badge: #1e3a5f;

		/* Borders */
		--border: #1e293b;
		--border-input: #334155;
		--border-row: #1e1e1e;

		/* Text */
		--text-primary: #e2e8f0;
		--text-secondary: #94a3b8;
		--text-muted: #64748b;
		--text-dim: #475569;
		--text-micro: #cbd5e1;
		--text-segment: #fff;

		/* Shadows */
		--shadow-overlay: rgba(0, 0, 0, 0.6);
		--shadow-modal: rgba(0, 0, 0, 0.5);
		--shadow-tooltip: rgba(0, 0, 0, 0.4);
		--shadow-text: rgba(0, 0, 0, 0.3);
	}

	:global([data-theme='light']) {
		--bg-body: #f8fafc;
		--bg-panel: #ffffff;
		--bg-input: #f1f5f9;
		--bg-hover: #f1f5f9;
		--bg-detail: #f8fafc;
		--bg-track: #e2e8f0;
		--bg-badge: #dbeafe;

		--border: #e2e8f0;
		--border-input: #cbd5e1;
		--border-row: #f1f5f9;

		--text-primary: #0f172a;
		--text-secondary: #475569;
		--text-muted: #64748b;
		--text-dim: #94a3b8;
		--text-micro: #334155;
		--text-segment: #fff;

		--shadow-overlay: rgba(0, 0, 0, 0.3);
		--shadow-modal: rgba(0, 0, 0, 0.15);
		--shadow-tooltip: rgba(0, 0, 0, 0.1);
		--shadow-text: rgba(0, 0, 0, 0.15);
	}
</style>
