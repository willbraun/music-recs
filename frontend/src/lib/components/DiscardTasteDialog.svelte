<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Dialog from '#lib/components/ui/dialog/index.js'
	import {
		cancelLeave,
		confirmLeave,
		requestLeave,
		tasteDraft,
	} from '#lib/tasteDraft.svelte.js'
	import { beforeNavigate, goto } from '$app/navigation'

	// Covers leaving the taste page; the modal calls requestLeave itself.
	beforeNavigate(({ cancel, to, willUnload }) => {
		if (!tasteDraft.isDirty) return
		cancel()
		// Reloads and external links can only use the browser's own prompt.
		if (willUnload || !to) return
		const target = to.url
		requestLeave(() => void goto(target))
	})
</script>

<Dialog.Root
	bind:open={
		() => tasteDraft.pendingLeave !== null,
		(next) => {
			if (!next) cancelLeave()
		}
	}
>
	<!-- Stacks above the taste modal, which renders later in the DOM at z-50. -->
	<Dialog.Content showCloseButton={false} overlayClass="z-[60]" class="z-60">
		<Dialog.Header>
			<Dialog.Title>Discard unsaved changes?</Dialog.Title>
			<Dialog.Description>
				If you leave now, you'll lose them.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button type="button" variant="outline" onclick={cancelLeave}>
				Keep editing
			</Button>
			<Button type="button" variant="destructive" onclick={confirmLeave}>
				Discard
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
