<script lang="ts">
	import { ApiError, saveTaste } from '#lib/api.js'
	import * as Alert from '#lib/components/ui/alert/index.js'
	import { Button } from '#lib/components/ui/button/index.js'
	import { Label } from '#lib/components/ui/label/index.js'
	import { Textarea } from '#lib/components/ui/textarea/index.js'
	import {
		cloneProfile,
		createEmptyProfile,
		isSameProfile,
		MAX_NOTES_CHARS,
		normalizeNotes,
	} from '#lib/profile.js'
	import { saveTasteResult, taste } from '#lib/taste.svelte.js'
	import { goto } from '$app/navigation'
	import { toast } from 'svelte-sonner'
	import GenreCombobox from './GenreCombobox.svelte'
	import TagInput from './TagInput.svelte'

	let form = $state(
		cloneProfile(taste.current?.profile ?? createEmptyProfile())
	)
	let isSaving = $state(false)
	let errorMessage: string | null = $state(null)

	const savedProfile = $derived(taste.current?.profile ?? createEmptyProfile())
	const hasLike = $derived(
		form.liked_genres.length > 0 || form.liked_artists.length > 0
	)
	const canSave = $derived(
		hasLike && !isSaving && !isSameProfile(form, savedProfile)
	)

	async function submitTaste(event: SubmitEvent) {
		event.preventDefault()
		if (!canSave) return
		const isSetup = taste.status === 'none'
		isSaving = true
		errorMessage = null
		try {
			const saved = await saveTaste({
				...form,
				notes: normalizeNotes(form.notes),
			})
			saveTasteResult(saved)
			form = cloneProfile(saved.profile)
			toast.success('Taste saved')
			if (isSetup) await goto('/')
		} catch (error) {
			const message =
				error instanceof Error ? error.message : 'Could not save your taste'
			if (error instanceof ApiError && error.status === 422)
				errorMessage = message
			else toast.error(message)
		} finally {
			isSaving = false
		}
	}
</script>

<form class="flex flex-col gap-6" onsubmit={submitTaste}>
	<div class="grid gap-4 sm:grid-cols-2">
		<fieldset class="flex min-w-0 flex-col gap-4 rounded-lg border p-4">
			<legend class="px-2 text-lg font-medium">I like</legend>
			<GenreCombobox
				id="liked-genres"
				label="Genres"
				bind:selected={form.liked_genres}
				blocked={form.disliked_genres}
				blockedHint="In your dislikes"
			/>
			<TagInput
				id="liked-artists"
				label="Artists"
				bind:items={form.liked_artists}
				blocked={form.disliked_artists}
				blockedMessage="Already in your dislikes"
			/>
		</fieldset>

		<fieldset class="flex min-w-0 flex-col gap-4 rounded-lg border p-4">
			<legend class="px-2 text-lg font-medium">I don't like</legend>
			<GenreCombobox
				id="disliked-genres"
				label="Genres"
				bind:selected={form.disliked_genres}
				blocked={form.liked_genres}
				blockedHint="In your likes"
			/>
			<TagInput
				id="disliked-artists"
				label="Artists"
				bind:items={form.disliked_artists}
				blocked={form.liked_artists}
				blockedMessage="Already in your likes"
			/>
		</fieldset>
	</div>

	<div class="flex flex-col gap-2">
		<Label for="taste-notes" class="text-lg font-medium">Anything else</Label>
		<Textarea
			id="taste-notes"
			bind:value={form.notes}
			placeholder="Era, mood, language, anything else"
			maxlength={MAX_NOTES_CHARS}
		/>
		<p class="text-right text-xs text-muted-foreground tabular-nums">
			{form.notes.length}/{MAX_NOTES_CHARS}
		</p>
	</div>

	<div class="flex flex-col gap-3">
		{#if errorMessage}
			<Alert.Root variant="destructive">
				<Alert.Description>{errorMessage}</Alert.Description>
			</Alert.Root>
		{/if}
		<div class="flex justify-end">
			<Button type="submit" disabled={!canSave}>Save taste</Button>
		</div>
	</div>
</form>
