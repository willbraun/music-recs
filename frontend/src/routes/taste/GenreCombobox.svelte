<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js'
	import * as Command from '#lib/components/ui/command/index.js'
	import { Label } from '#lib/components/ui/label/index.js'
	import * as Popover from '#lib/components/ui/popover/index.js'
	import { GENRES } from '#lib/genres.js'
	import { hasItem, MAX_ITEM_CHARS, MAX_ITEMS } from '#lib/profile.js'
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down'
	import ChipList from './ChipList.svelte'

	let {
		id,
		label,
		selected = $bindable(),
		blocked,
		blockedHint,
	}: {
		id: string
		label: string
		selected: string[]
		blocked: string[]
		blockedHint: string
	} = $props()

	let isOpen = $state(false)
	let search = $state('')
	let status = $state('')

	const options = $derived([
		...GENRES,
		...selected.filter((genre) => !hasItem(GENRES, genre)),
	])
	const customGenre = $derived(search.trim())
	const canAddCustom = $derived(
		customGenre !== '' &&
			!hasItem(options, customGenre) &&
			selected.length < MAX_ITEMS
	)

	function addGenre(genre: string) {
		selected = [...selected, genre]
		status = `Added ${genre}`
	}

	function removeGenre(genre: string) {
		selected = selected.filter((item) => !hasItem([genre], item))
		status = `Removed ${genre}`
	}

	function toggleGenre(genre: string) {
		if (hasItem(selected, genre)) removeGenre(genre)
		else if (selected.length < MAX_ITEMS) addGenre(genre)
	}

	function addCustomGenre() {
		addGenre(customGenre)
		search = ''
	}
</script>

<div class="flex flex-col gap-2">
	<Label for={id}>{label}</Label>
	<!-- The trigger fills the field behind the chips so remove buttons are not nested inside it. -->
	<div class="relative min-h-9">
		<Popover.Root bind:open={isOpen}>
			<Popover.Trigger>
				{#snippet child({ props })}
					<Button
						{...props}
						{id}
						variant="outline"
						class="absolute inset-0 h-full w-full justify-end px-2.5 font-normal"
						role="combobox"
						aria-expanded={isOpen}
					>
						<ChevronDownIcon class="text-muted-foreground" />
					</Button>
				{/snippet}
			</Popover.Trigger>
			<Popover.Content
				class="w-(--bits-floating-anchor-width) min-w-56 p-0"
				align="start"
			>
				<Command.Root>
					<Command.Input
						placeholder="Search or add a genre"
						maxlength={MAX_ITEM_CHARS}
						bind:value={search}
					/>
					<Command.List>
						{#if !canAddCustom}
							<Command.Empty>No genres found.</Command.Empty>
						{/if}
						<Command.Group>
							{#each options as genre (genre)}
								{@const isBlocked = hasItem(blocked, genre)}
								<Command.Item
									value={genre}
									data-checked={hasItem(selected, genre)}
									disabled={isBlocked}
									onSelect={() => toggleGenre(genre)}
								>
									{genre}
									{#if isBlocked}
										<span
											class="flex-1 text-right text-xs text-muted-foreground"
											>{blockedHint}</span
										>
									{/if}
								</Command.Item>
							{/each}
						</Command.Group>
						{#if canAddCustom}
							{@const isCustomBlocked = hasItem(blocked, customGenre)}
							<Command.Group>
								<Command.Item
									value="add {customGenre}"
									forceMount
									disabled={isCustomBlocked}
									onSelect={addCustomGenre}
								>
									Add {customGenre}
									{#if isCustomBlocked}
										<span
											class="flex-1 text-right text-xs text-muted-foreground"
											>{blockedHint}</span
										>
									{/if}
								</Command.Item>
							</Command.Group>
						{/if}
					</Command.List>
				</Command.Root>
			</Popover.Content>
		</Popover.Root>
		<div
			class="pointer-events-none relative flex min-h-9 flex-wrap items-center gap-1.5 py-1.5 pr-9 pl-2.5"
		>
			{#if selected.length === 0}
				<span class="text-sm text-muted-foreground">Select genres</span>
			{/if}
			<ChipList
				items={selected}
				label="{label} list"
				{status}
				onremove={removeGenre}
			/>
		</div>
	</div>
</div>
