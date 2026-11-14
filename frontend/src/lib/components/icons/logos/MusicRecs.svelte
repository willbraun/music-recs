<script lang="ts">
	import { cn } from '#lib/utils.js'

	let { class: className }: { class?: string } = $props()

	const uid = $props.id()
	const maskId = `bars-cutout-${uid}`
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="0 0 100 100"
	class={cn('size-8', className)}
	aria-hidden="true"
>
	<defs>
		<!-- Cuts the sound bars out of the highlighted tile -->
		<mask id={maskId}>
			<rect x="54" y="6" width="40" height="40" rx="8" fill="#fff" />
			<rect x="60" y="27" width="6" height="10" rx="3" fill="#000" />
			<rect x="71" y="15" width="6" height="22" rx="3" fill="#000" />
			<rect x="82" y="21" width="6" height="16" rx="3" fill="#000" />
		</mask>
	</defs>

	<!-- Strokes are inset by half their width so every tile spans 40 units -->
	<g fill="none" stroke="currentColor" stroke-width="6">
		<rect x="9" y="9" width="34" height="34" rx="5" />
		<rect x="9" y="57" width="34" height="34" rx="5" />
		<rect x="57" y="57" width="34" height="34" rx="5" />
	</g>

	<rect
		x="54"
		y="6"
		width="40"
		height="40"
		rx="8"
		fill="currentColor"
		mask="url(#{maskId})"
	/>
</svg>
