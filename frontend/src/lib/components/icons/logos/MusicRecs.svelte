<script lang="ts">
	import {
		LOGO_GRADIENT,
		LOGO_OUTLINES,
		LOGO_STROKE_WIDTH,
		LOGO_TILE_PATH,
		LOGO_VIEWBOX,
	} from '#lib/logo.js'
	import { cn } from '#lib/utils.js'

	let { class: className }: { class?: string } = $props()

	const uid = $props.id()
	const gradientId = `tile-gradient-${uid}`
	const { x, y, size } = LOGO_VIEWBOX
</script>

<svg
	xmlns="http://www.w3.org/2000/svg"
	viewBox="{x} {y} {size} {size}"
	class={cn('size-8', className)}
	aria-hidden="true"
>
	<defs>
		<linearGradient
			id={gradientId}
			x1={LOGO_GRADIENT.x1}
			y1="0"
			x2={LOGO_GRADIENT.x2}
			y2="0"
			gradientUnits="userSpaceOnUse"
		>
			<stop offset="0" stop-color={LOGO_GRADIENT.from} />
			<stop offset="1" stop-color={LOGO_GRADIENT.to} />
		</linearGradient>
	</defs>

	<g fill="none" stroke="currentColor" stroke-width={LOGO_STROKE_WIDTH}>
		{#each LOGO_OUTLINES as outline (`${outline.x},${outline.y}`)}
			<rect
				x={outline.x}
				y={outline.y}
				width={outline.size}
				height={outline.size}
				rx={outline.radius}
			/>
		{/each}
	</g>

	<path fill="url(#{gradientId})" fill-rule="evenodd" d={LOGO_TILE_PATH} />
</svg>
