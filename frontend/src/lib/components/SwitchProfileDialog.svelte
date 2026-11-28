<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Dialog from '#lib/components/ui/dialog/index.js'
	import {
		cancelProfileSwitch,
		confirmProfileSwitch,
		profiles,
	} from '#lib/profiles.svelte.js'
	import { goto } from '$app/navigation'

	let isSwitching = $state(false)

	async function switchProfile() {
		isSwitching = true
		try {
			if (await confirmProfileSwitch()) await goto('/')
		} finally {
			isSwitching = false
		}
	}
</script>

<Dialog.Root
	bind:open={
		() => profiles.pendingSwitchId !== null,
		(next) => {
			if (!next) cancelProfileSwitch()
		}
	}
>
	<Dialog.Content showCloseButton={false}>
		<Dialog.Header>
			<Dialog.Title>Switch profiles?</Dialog.Title>
			<Dialog.Description>
				Songs are still being analyzed. Switching now cancels the run. Songs
				already analyzed stay saved.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button type="button" variant="outline" onclick={cancelProfileSwitch}>
				Stay
			</Button>
			<Button type="button" disabled={isSwitching} onclick={switchProfile}>
				Cancel and switch
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
