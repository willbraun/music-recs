<!-- Literal X icon, not Twitter X -->

<script lang="ts">
	import { Icon } from '@lucide/svelte'
	import type { ComponentProps } from 'svelte'

	let props: Omit<ComponentProps<typeof Icon>, 'iconNode' | 'icon'> = $props()

	// One path instead of Lucide's two, which Safari/WebKit draws with a gap where the strokes cross.
	const X_ICON_NODE: ComponentProps<typeof Icon>['iconNode'] = [
		['path', { d: 'M18 6 6 18m0-12 12 12' }],
	]
</script>

<Icon {...props} iconNode={X_ICON_NODE} class={['lucide-x', props.class]} />
