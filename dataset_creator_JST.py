import argparse
from datasets import DatasetDict, Audio, load_from_disk
from SoundCodec.codec import load_codec, list_codec
# from SoundCodec.dataset import load_dataset
from datasets import load_dataset, load_from_disk
from SoundCodec.dataset.general import extract_unit, apply_audio_cast


def run_experiment(dataset_name):
    cleaned_dataset = load_dataset(dataset_name, split="test")
    d_item = next(iter(cleaned_dataset))
    sampling_rate = d_item[args.audio_name]['sampling_rate']
    
    cleaned_dataset = load_dataset(dataset_name, split="test")
    # preprocessing dataset
    cleaned_dataset = cleaned_dataset.rename_column(args.audio_name, "audio")
    id_column = [i for i in range(len(cleaned_dataset))]
    cleaned_dataset = cleaned_dataset.add_column("id", id_column)
    cleaned_dataset = cleaned_dataset.remove_columns(["answers", "question_normalized_text", "gpt4-response", "question_audio_path_transcription_whisper-small.en", "question_audio_path_transcription_whisper-medium.en", "question_audio_path_transcription_whisper-large-v3"])
    
    print("before filter duration", cleaned_dataset)
    cleaned_dataset = cleaned_dataset.filter(
        lambda x: len(x["audio"]['array']) / x["audio"]['sampling_rate'] <= args.max_duration)
    print("after filter duration", cleaned_dataset)
    cleaned_dataset = apply_audio_cast(cleaned_dataset, sampling_rate)
    if not args.extract_unit_only:
        datasets_dict = DatasetDict({'original': cleaned_dataset})
    else:
        datasets_dict = DatasetDict({})
    for codec_name in list_codec():
        print(f"Synthesizing dataset with {codec_name}")
        # load from disk if already synthesized
        try:
            synthesized_dataset = load_from_disk(f"./cached_datasets/{dataset_name}_{codec_name}/")
            datasets_dict[f'{codec_name}'] = synthesized_dataset
            continue
        except:
            pass
        codec = load_codec(codec_name)
        synthesized_dataset = apply_audio_cast(cleaned_dataset, codec.sampling_rate)
        if args.extract_unit_only:
            synthesized_dataset = synthesized_dataset.map(extract_unit, fn_kwargs={'extract_unit_class': codec})
        else:
            synthesized_dataset = synthesized_dataset.map(codec.synth)
            synthesized_dataset = synthesized_dataset.cast_column("audio", Audio(sampling_rate=sampling_rate))
        synthesized_dataset = synthesized_dataset.remove_columns(["audio"])
        print(synthesized_dataset[0]) 
        synthesized_dataset.save_to_disk(f"./cached_datasets/{dataset_name}_{codec_name}/")
        datasets_dict[f'{codec_name}'] = synthesized_dataset

    try:
        datasets_dict_unit_only = datasets_dict.remove_columns(["audio"])
        datasets_dict_unit_only.pop('original')
    except:
        datasets_dict_unit_only = datasets_dict
    datasets_dict_unit_only.save_to_disk(f"./datasets/{dataset_name}_unit")
    # remove datasets_dict columns if they have 'unit', and use datasets_dict_synth for saving
    datasets_dict_synth = DatasetDict({})
    for key in datasets_dict.keys():
        if 'unit' not in datasets_dict[key].column_names:
            datasets_dict_synth[key] = datasets_dict[key]
        else:
            datasets_dict_synth[key] = datasets_dict[key].remove_columns(['unit'])
    if not args.extract_unit_only:
        datasets_dict_synth.save_to_disk(f"./datasets/{dataset_name}_synth")

    if args.push_to_hub:
        push_to_hub_org = args.upload_name
        if not args.extract_unit_only:
            datasets_dict_synth.push_to_hub(f"{push_to_hub_org}/{dataset_name}_synth")
        datasets_dict_unit_only.push_to_hub(f"{push_to_hub_org}/{dataset_name.split('/')[-1]}_unit")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run audio encoding-decoding experiments.')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Name of the dataset to process in huggingface/datasets')
    parser.add_argument('--audio_name', type=str, required=True,
                        help='Name of the audio column of the dataset to process in huggingface/datasets')
    parser.add_argument('--extract_unit_only', required=False, action='store_false')
    parser.add_argument('--max_duration', required=False, type=int, default=120)
    parser.add_argument('--push_to_hub', required=False, action='store_false')
    parser.add_argument('--upload_name', required=False, default='JST-SUPERB')
    args = parser.parse_args()
    print(args)
    run_experiment(args.dataset)