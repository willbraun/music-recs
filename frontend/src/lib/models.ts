export interface ModelInfo {
	id: string
	name: string
	url: string
}

// Keep ids in sync with MODEL_ID in api/analyze.py and api/queries.py.
export const MODELS: ModelInfo[] = [
	{
		id: 'Qwen/Qwen2.5-3B-Instruct',
		name: 'Qwen 2.5 3B Instruct',
		url: 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct',
	},
	{
		id: 'nvidia/music-flamingo-2601-hf',
		name: 'Music Flamingo 2601',
		url: 'https://huggingface.co/nvidia/music-flamingo-2601-hf',
	},
]

// A model the list does not know falls back to its id and its Hugging Face page.
export function findModel(id: string): ModelInfo {
	return (
		MODELS.find((model) => model.id === id) ?? {
			id,
			name: id,
			url: `https://huggingface.co/${id}`,
		}
	)
}
