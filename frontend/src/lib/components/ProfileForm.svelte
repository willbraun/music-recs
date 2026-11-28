<script lang="ts">
	import { ApiError, type Profile } from '#lib/api.js'
	import * as Alert from '#lib/components/ui/alert/index.js'
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Dialog from '#lib/components/ui/dialog/index.js'
	import { Input } from '#lib/components/ui/input/index.js'
	import { Label } from '#lib/components/ui/label/index.js'
	import { cn } from '#lib/utils.js'
	import { toast } from 'svelte-sonner'
	import ProfileAvatar from './ProfileAvatar.svelte'

	const AVATAR_CHOICES = [
		'🎸',
		'🎹',
		'🎧',
		'🎤',
		'🥁',
		'🎷',
		'🎺',
		'🎻',
		'🦊',
		'🐼',
		'🐯',
		'🦄',
		'🐙',
		'🦉',
		'🐸',
		'🐧',
		'🌵',
		'🌈',
		'🔥',
		'🌙',
		'🍕',
		'🚀',
		'👾',
		'🤖',
	]
	const MAX_NAME_CHARS = 30

	let {
		profile,
		submitLabel = 'Save',
		cancelHref,
		onsubmit,
		ondelete,
	}: {
		profile?: Profile
		submitLabel?: string
		cancelHref?: string
		onsubmit: (input: { name: string; avatar: string }) => Promise<void>
		ondelete?: () => Promise<void>
	} = $props()

	// Initial values only: the edit page remounts this form per profile.
	// svelte-ignore state_referenced_locally
	let name = $state(profile?.name ?? '')
	// svelte-ignore state_referenced_locally
	let avatar = $state(profile?.avatar ?? AVATAR_CHOICES[0])
	let isSaving = $state(false)
	let isDeleting = $state(false)
	let isConfirmingDelete = $state(false)
	let errorMessage: string | null = $state(null)

	const trimmedName = $derived(name.trim())
	// Mirrors the API rule: letters, digits and spaces are not an avatar.
	const isAvatarValid = $derived(
		avatar.trim().length > 0 && !/[\p{L}\p{N}\s]/u.test(avatar)
	)
	const canSave = $derived(trimmedName.length > 0 && isAvatarValid && !isSaving)

	async function submitProfile(event: SubmitEvent) {
		event.preventDefault()
		if (!canSave) return
		isSaving = true
		errorMessage = null
		try {
			await onsubmit({ name: trimmedName, avatar: avatar.trim() })
		} catch (error) {
			const message =
				error instanceof Error ? error.message : 'Could not save the profile'
			// The API explains 422s, such as an avatar that is not an emoji.
			if (error instanceof ApiError && error.status === 422)
				errorMessage = message
			else toast.error(message, { duration: Infinity })
		} finally {
			isSaving = false
		}
	}

	async function confirmDelete() {
		if (!ondelete) return
		isDeleting = true
		try {
			await ondelete()
		} catch (error) {
			isConfirmingDelete = false
			toast.error(
				error instanceof Error ? error.message : 'Could not delete the profile',
				{ duration: Infinity }
			)
		} finally {
			isDeleting = false
		}
	}
</script>

<form class="flex flex-col gap-8" onsubmit={submitProfile}>
	<div class="flex items-center gap-6">
		<ProfileAvatar {avatar} class="size-24 shrink-0 text-6xl" />
		<div class="flex w-full flex-col gap-2">
			<Label for="profile-name" class="text-lg font-medium">Name</Label>
			<Input
				id="profile-name"
				bind:value={name}
				maxlength={MAX_NAME_CHARS}
				placeholder="Profile name"
				autocomplete="off"
			/>
		</div>
	</div>

	<fieldset class="flex flex-col gap-3">
		<legend class="mb-3 text-lg font-medium">Avatar</legend>
		<div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Avatar">
			{#each AVATAR_CHOICES as choice (choice)}
				<button
					type="button"
					role="radio"
					aria-checked={avatar === choice}
					aria-label="Use {choice} as avatar"
					class={cn(
						'flex size-11 cursor-pointer items-center justify-center rounded-md text-2xl outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring',
						avatar === choice && 'bg-muted ring-2 ring-primary'
					)}
					onclick={() => (avatar = choice)}>{choice}</button
				>
			{/each}
		</div>
		<div class="flex items-center gap-3">
			<Label for="profile-avatar" class="text-sm text-muted-foreground"
				>Or type your own emoji</Label
			>
			<Input
				id="profile-avatar"
				bind:value={avatar}
				class="w-24 text-center text-lg"
				maxlength={16}
				autocomplete="off"
			/>
		</div>
		{#if avatar.trim().length > 0 && !isAvatarValid}
			<p class="text-sm text-destructive" role="alert">
				The avatar must be an emoji, not letters or numbers.
			</p>
		{/if}
	</fieldset>

	{#if errorMessage}
		<Alert.Root variant="destructive">
			<Alert.Description>{errorMessage}</Alert.Description>
		</Alert.Root>
	{/if}

	<div class="flex items-center gap-3">
		{#if ondelete}
			<Button
				type="button"
				variant="destructive"
				onclick={() => (isConfirmingDelete = true)}>Delete profile</Button
			>
		{/if}
		<div class="ml-auto flex items-center gap-3">
			{#if cancelHref}
				<Button href={cancelHref} variant="outline">Cancel</Button>
			{/if}
			<Button type="submit" disabled={!canSave}>{submitLabel}</Button>
		</div>
	</div>
</form>

{#if ondelete}
	<Dialog.Root bind:open={isConfirmingDelete}>
		<Dialog.Content showCloseButton={false}>
			<Dialog.Header>
				<Dialog.Title>Delete {profile?.name}?</Dialog.Title>
				<Dialog.Description>
					This permanently removes the profile's taste and songs.
				</Dialog.Description>
			</Dialog.Header>
			<Dialog.Footer>
				<Button
					type="button"
					variant="outline"
					onclick={() => (isConfirmingDelete = false)}>Cancel</Button
				>
				<Button
					type="button"
					variant="destructive"
					disabled={isDeleting}
					onclick={confirmDelete}>Delete</Button
				>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
{/if}
