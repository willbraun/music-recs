<script lang="ts">
	import { Input } from '#lib/components/ui/input/index.js'
	import { Label } from '#lib/components/ui/label/index.js'
	import { hasItem, MAX_ITEM_CHARS, MAX_ITEMS } from '#lib/profile.js'
	import ChipList from './ChipList.svelte'

	let {
		id,
		label,
		items = $bindable(),
		blocked,
		blockedMessage,
		placeholder = 'Type a name, press Enter',
	}: {
		id: string
		label: string
		items: string[]
		blocked: string[]
		blockedMessage: string
		placeholder?: string
	} = $props()

	let inputRef: HTMLInputElement | null = $state(null)
	let text = $state('')
	let message = $state('')
	let status = $state('')

	function addItems(names: string[]) {
		// Names are never split on commas, since artist names can contain them.
		for (const raw of names) {
			const name = raw.trim()
			if (!name || hasItem(items, name)) continue
			if (hasItem(blocked, name)) {
				message = blockedMessage
				continue
			}
			if (items.length >= MAX_ITEMS) {
				message = `You can add at most ${MAX_ITEMS} names`
				return
			}
			items = [...items, name]
			status = `Added ${name}`
			message = ''
		}
	}

	function removeItem(name: string) {
		items = items.filter((item) => item !== name)
		status = `Removed ${name}`
		message = ''
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			// Keeps Enter from submitting the form.
			event.preventDefault()
			const name = text.trim()
			if (!name) return
			message = ''
			const countBefore = items.length
			addItems([name])
			if (items.length > countBefore) text = ''
		} else if (event.key === 'Backspace' && text === '' && items.length > 0) {
			removeItem(items[items.length - 1])
		}
	}

	function handlePaste(event: ClipboardEvent) {
		const pasted = event.clipboardData?.getData('text') ?? ''
		if (!/[\r\n]/.test(pasted)) return
		// Pasted lines become one chip each.
		event.preventDefault()
		message = ''
		addItems(pasted.split(/\r?\n/))
	}
</script>

<div class="flex flex-col gap-2">
	<Label for={id}>{label}</Label>
	<!-- Clicking the empty part of the field focuses the input; keyboard users reach it directly. -->
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div
		class="flex min-h-9 cursor-text flex-wrap items-center gap-1.5 rounded-md border border-input px-2.5 py-1.5 shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 has-[input[aria-invalid=true]]:border-destructive has-[input[aria-invalid=true]]:ring-3 has-[input[aria-invalid=true]]:ring-destructive/20 dark:bg-input/30"
		onclick={() => inputRef?.focus()}
	>
		<ChipList {items} label="{label} list" {status} onremove={removeItem} />
		<Input
			{id}
			bind:ref={inputRef}
			bind:value={text}
			placeholder={items.length === 0 ? placeholder : ''}
			maxlength={MAX_ITEM_CHARS}
			autocomplete="off"
			class="h-6 min-w-24 flex-1 border-0 bg-transparent p-0 shadow-none focus-visible:ring-0 aria-invalid:ring-0 dark:bg-transparent"
			aria-describedby={message ? `${id}-message` : undefined}
			aria-invalid={message ? true : undefined}
			onkeydown={handleKeydown}
			onpaste={handlePaste}
			oninput={() => (message = '')}
		/>
	</div>
	{#if message}
		<p id="{id}-message" class="text-sm text-destructive">{message}</p>
	{/if}
</div>
