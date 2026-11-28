<script lang="ts">
	import { cn } from '#lib/utils.js'

	let { avatar, class: className }: { avatar: string; class?: string } =
		$props()
</script>

<span
	aria-hidden="true"
	class={cn(
		'flex shrink-0 items-center justify-center truncate rounded-md bg-muted leading-none select-none',
		className
	)}>{avatar}</span
>
