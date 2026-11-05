export interface ModelInfo {
	id: string
	name: string
	url: string
	purpose: string
}

// Keep ids in sync with MODEL_IDS in api/model_download.py.
export const MODELS: ModelInfo[] = [
	{
		id: 'Qwen/Qwen2.5-3B-Instruct',
		name: 'Qwen 2.5 3B Instruct',
		url: 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct',
		purpose:
			'Translates your taste into search queries for artists to look up.',
	},
	{
		id: 'FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit',
		name: 'MOSS Music 8B Instruct',
		url: 'https://huggingface.co/FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit',
		purpose:
			'Listens to a clip of each song and decides whether you would like it, with a confidence score.',
	},
]

// A model the list does not know falls back to its id and its Hugging Face page.
export function findModel(id: string): Pick<ModelInfo, 'id' | 'name' | 'url'> {
	return (
		MODELS.find((model) => model.id === id) ?? {
			id,
			name: id,
			url: `https://huggingface.co/${id}`,
		}
	)
}
