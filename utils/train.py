import os
from contextlib import nullcontext
import torch
from datasets import load_dataset
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from utils import logger

MODEL_ID = os.environ.get("COMMENT_MODEL", "FacebookAI/xlm-roberta-base")

LABELS = [
    "toxicity",
    "severe_toxicity",
    "obscene",
    "threat",
    "insult",
    "identity_attack",
    "sexual_explicit",
]

TRAIN_ROWS = int(os.environ.get("COMMENT_TRAIN_ROWS", 50000))
VAL_ROWS = int(os.environ.get("COMMENT_VAL_ROWS", 5000))
BATCH_SIZE = int(os.environ.get("COMMENT_BATCH_SIZE", 32))
EPOCHS = int(os.environ.get("COMMENT_EPOCHS", 1))
MAX_LEN = int(os.environ.get("COMMENT_MAX_LEN", 128))
LR = float(os.environ.get("COMMENT_LR", 2e-5))


class Classifier:
    def __init__(self, retrain: bool = False, **train_config):
        self.config = {
            "model_id": MODEL_ID,
            "train_rows": TRAIN_ROWS,
            "val_rows": VAL_ROWS,
            "batch_size": BATCH_SIZE,
            "epochs": EPOCHS,
            "max_len": MAX_LEN,
            "lr": LR,
            "bf16": False,
        }
        self.config.update(train_config)
        self.output_dir = os.path.join(
            os.getcwd(), "model", self.config["model_id"].split("/")[-1]
        )
        if retrain:
            self.__retrain_model()

    def __retrain_model(self):
        """Trains a transformer model on the civil_comments multi-label toxicity task."""
        cfg = self.config
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")

        logger.info(f"Loading tokenizer and model: {cfg['model_id']}")
        tokenizer = AutoTokenizer.from_pretrained(cfg["model_id"])
        model = AutoModelForSequenceClassification.from_pretrained(
            cfg["model_id"], num_labels=len(LABELS)
        ).to(device)

        logger.info("Loading google/civil_comments")
        dataset = load_dataset("google/civil_comments")

        def tokenize(batch):
            tokenized = tokenizer(
                batch["text"],
                truncation=True,
                padding="max_length",
                max_length=cfg["max_len"],
            )
            tokenized["labels"] = [
                [float(batch[label][i]) for label in LABELS]
                for i in range(len(batch["text"]))
            ]
            return tokenized

        train = (
            dataset["train"]
            .select(range(cfg["train_rows"]))
            .map(tokenize, batched=True)
            .with_format("torch", columns=["input_ids", "attention_mask", "labels"])
        )
        val = (
            dataset["validation"]
            .select(range(cfg["val_rows"]))
            .map(tokenize, batched=True)
            .with_format("torch", columns=["input_ids", "attention_mask", "labels"])
        )
        train_loader = DataLoader(
            train, batch_size=cfg["batch_size"], shuffle=True  # pyright: ignore
        )
        val_loader = DataLoader(val, batch_size=cfg["batch_size"])  # pyright: ignore

        optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"])
        loss_fn = torch.nn.BCEWithLogitsLoss()

        for epoch in range(cfg["epochs"]):
            model.train()
            running = 0.0
            for step, batch in enumerate(train_loader):
                batch = {k: v.to(device) for k, v in batch.items()}
                cast_ctx = (
                    torch.autocast("cuda", dtype=torch.bfloat16)
                    if cfg["bf16"] and device.type == "cuda"
                    else nullcontext()
                )
                with cast_ctx:
                    logits = model(
                        input_ids=batch["input_ids"],
                        attention_mask=batch["attention_mask"],
                    ).logits
                    loss = loss_fn(logits, batch["labels"])

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                running += loss.item()
                if step % 1000 == 0:
                    logger.info(
                        f"epoch {epoch + 1} step {step} loss {running / (step + 1):.4f}"
                    )

            avg_val_loss = self.__evaluate(model, val_loader, loss_fn, device)
            logger.info(
                f"epoch {epoch + 1} train loss {running / len(train_loader):.4f} val loss {avg_val_loss:.4f}"
            )

        os.makedirs(self.output_dir, exist_ok=True)
        model.save_pretrained(self.output_dir)
        tokenizer.save_pretrained(self.output_dir)
        logger.info(f"Model saved to {self.output_dir}")

    def predict(self, comments):
        """Run the trained model on comments and return per-label probabilities.

        Args:
            comments: iterable of comment strings.

        Returns:
            list of dicts mapping each label to its probability in [0, 1].
            A label is flagged when its probability is >= 0.5.
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        tokenizer = AutoTokenizer.from_pretrained(self.output_dir)
        model = AutoModelForSequenceClassification.from_pretrained(self.output_dir).to(
            device
        )
        model.eval()

        results = []
        with torch.no_grad():
            for comment in comments:
                inputs = tokenizer(
                    str(comment),
                    truncation=True,
                    padding="max_length",
                    max_length=self.config["max_len"],
                    return_tensors="pt",
                ).to(device)
                logits = model(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                ).logits
                probs = torch.sigmoid(logits).squeeze().cpu().tolist()
                results.append({label: prob for label, prob in zip(LABELS, probs)})
        return results

    def __evaluate(self, model, loader, loss_fn, device):
        model.eval()
        total = 0.0
        cast_ctx = (
            torch.autocast("cuda", dtype=torch.bfloat16)
            if self.config["bf16"] and device.type == "cuda"
            else nullcontext()
        )
        with torch.no_grad():
            for batch in loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                with cast_ctx:
                    logits = model(
                        input_ids=batch["input_ids"],
                        attention_mask=batch["attention_mask"],
                    ).logits
                    total += loss_fn(logits, batch["labels"]).item()
        return total / len(loader)
