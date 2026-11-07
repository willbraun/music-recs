# Music Recs

Music Recs is a local music recommendation tool. It finds music online, analyzes it with local audio models, and recommends songs based on your musical preferences.

## Models

Music Recs uses two models, which are downloaded from Hugging Face and run on your computer:

- [Qwen3 8B (MLX 4-bit)](https://huggingface.co/Qwen/Qwen3-8B-MLX-4bit) translates your musical taste into search queries. It runs on Apple Silicon.
- [MOSS Music 8B Instruct (MLX 5-bit)](https://huggingface.co/FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit) listens to each song clip and decides whether you would like it. It runs on Apple Silicon.
