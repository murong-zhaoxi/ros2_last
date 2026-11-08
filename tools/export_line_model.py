#!/usr/bin/env python3
import argparse
from pathlib import Path

import onnx
import torch
from torchvision import models


WORKSPACE = Path(__file__).resolve().parents[1]
MODEL_DIR = WORKSPACE / "src" / "line_follower_perception" / "models"
DEFAULT_CHECKPOINT = MODEL_DIR / "best_line_follower_model_xy_retrained.pth"
DEFAULT_OUTPUT = MODEL_DIR / "best_line_follower_model_xy_retrained.onnx"


def main():
    parser = argparse.ArgumentParser(description="Export a trained ResNet18 XY model to ONNX.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")

    model = models.resnet18(weights=None)
    model.fc = torch.nn.Linear(512, 2)
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu"))
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sample = torch.zeros(1, 3, 224, 224)
    torch.onnx.export(
        model,
        sample,
        args.output,
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
    )
    exported = onnx.load(args.output)
    onnx.checker.check_model(exported)
    print(f"Exported and validated {args.output}")


if __name__ == "__main__":
    main()
