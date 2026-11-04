<script lang="ts">
	import type { ModelLicense } from '#lib/models.js'
	import DownloadIcon from '@lucide/svelte/icons/download'
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link'

	let { license, modelName }: { license: ModelLicense; modelName: string } =
		$props()

	const linkClass =
		'inline-flex w-fit items-center gap-1 rounded-sm text-muted-foreground underline underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-ring'
</script>

{#if license.original.action === 'download'}
	<a
		class={linkClass}
		href={license.original.url}
		download
		aria-label="Download original {license.name} for {modelName}"
	>
		Download Original
		<DownloadIcon class="size-3.5" />
	</a>
{:else}
	<a
		class={linkClass}
		href={license.original.url}
		target="_blank"
		rel="noopener noreferrer"
		aria-label="View original {license.name} for {modelName} (opens in a new tab)"
	>
		View Original
		<ExternalLinkIcon class="size-3.5" />
	</a>
{/if}
