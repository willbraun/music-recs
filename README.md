# Music Recs

Music Recs is a local music recommendation tool. It finds music online, analyzes it with local audio models, and recommends songs based on your musical preferences.

## Models

Music Recs uses two models, which are downloaded from Hugging Face and run on your computer:

- [Qwen 2.5 3B Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) translates your musical taste into search queries.
- [Music Flamingo 2601](https://huggingface.co/nvidia/music-flamingo-2601-hf) listens to each song clip and decides whether you would like it.
