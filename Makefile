.PHONY: train

all:
	@echo "TEST"

train:
	@echo "start re-training the model"
	.venv/bin/python main.py --train --train-rows 1804874 --val-rows 97320 --bf16
