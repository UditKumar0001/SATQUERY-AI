# finetune/lora_earthgpt_bigearthnet.py
import json
import os
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)

BASE_MODEL = os.getenv("EARTHGPT_BASE_MODEL", "hf-internal-testing/tiny-random-LlamaForCausalLM")
OUTPUT_DIR = "models/weights/earthgpt-bigearthnet-lora"


def build_instruction_dataset(processed_dir="data/processed/bigearthnet"):
    """Load synthesized (optical, sar, instruction, answer) tuples from BigEarthNet."""
    data_file = os.path.join(processed_dir, "instructions.jsonl")
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Instructions dataset not found at {data_file}. Run data/preprocess.py first.")
    return load_dataset("json", data_files=data_file)["train"]


def preprocess_dataset(dataset, tokenizer, max_length=256):
    """Format and tokenize instruction/response text for causal LM training."""
    def tokenize_fn(example):
        prompt = f"Instruction: {example['instruction']}\nResponse: {example['answer']}"
        tokens = tokenizer(
            prompt,
            truncation=True,
            max_length=max_length,
            padding="max_length"
        )
        tokens["labels"] = tokens["input_ids"].copy()
        return tokens

    return dataset.map(tokenize_fn, batched=False)


def main():
    print(f"[LoRA Fine-Tune] Base model: {BASE_MODEL}")
    print("[LoRA Fine-Tune] Target output directory:", OUTPUT_DIR)

    # 1. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or "<pad>"

    # 2. Determine safe execution device (fall back to CPU if GPU compute capability exceeds PyTorch kernel support)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if torch.cuda.is_available():
        major_cap = torch.cuda.get_device_capability(0)[0]
        if major_cap > 9:  # sm_120 (Blackwell) requires CPU fallback until torch provides sm_120 binary kernels
            print(f"[LoRA Fine-Tune] Detected CUDA capability sm_{major_cap}0. Falling back to CPU for kernel compatibility.")
            device = "cpu"

    print(f"[LoRA Fine-Tune] Training device: {device}")

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True
    )

    # 3. Apply LoRA Configuration
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
        task_type="CAUSAL_LM",
        bias="none"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. Load & Prepare BigEarthNet Instructions
    raw_ds = build_instruction_dataset()
    train_ds = preprocess_dataset(raw_ds, tokenizer)
    print(f"[LoRA Fine-Tune] Prepared {len(train_ds)} instruction samples.")

    # 5. Training Arguments
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        num_train_epochs=2,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="epoch",
        report_to="none",
        use_cpu=(device == "cpu"),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt")
    )

    print("[LoRA Fine-Tune] Initiating LoRA training on BigEarthNet instruction data...")
    train_result = trainer.train()
    print(f"[LoRA Fine-Tune] Training complete. Loss: {train_result.training_loss:.4f}")

    # 6. Save LoRA Adapter
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"[LoRA Fine-Tune] Adapter weights and configuration successfully saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
