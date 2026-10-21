<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.js'
	import XIcon from '@lucide/svelte/icons/x'

	let {
		items,
		label,
		status = '',
		onremove,
	}: {
		items: string[]
		label: string
		status?: string
		onremove: (item: string) => void
	} = $props()
</script>

{#if items.length > 0}
	<ul class="flex flex-wrap gap-1.5" aria-label={label}>
		{#each items as item (item)}
			<li>
				<Badge variant="secondary" class="h-6 gap-1 pr-1 pl-2.5">
					{item}
					<button
						type="button"
						class="pointer-events-auto cursor-pointer rounded-full outline-none hover:bg-foreground/10 focus-visible:ring-2 focus-visible:ring-ring"
						aria-label="Remove {item}"
						onclick={() => onremove(item)}
					>
						<XIcon size={16} />
					</button>
				</Badge>
			</li>
		{/each}
	</ul>
{/if}
<p class="sr-only" aria-live="polite">{status}</p>
