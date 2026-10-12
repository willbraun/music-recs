<script lang="ts">
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle'

	let { title, artist }: { title: string; artist: string } = $props()
</script>

<article class="w-full" aria-busy="true" aria-label="Analyzing {title}">
	<div class="bg-muted relative flex aspect-square items-center justify-center rounded-lg">
		<LoaderCircleIcon class="text-muted-foreground size-8 animate-spin motion-reduce:animate-none" aria-hidden="true" />
	</div>
	<div class="mt-2 min-w-0 opacity-60">
		<p class="truncate text-sm font-medium" title={title}>{title}</p>
		<p class="text-muted-foreground truncate text-sm">{artist}</p>
	</div>
</article>
