#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = WORKSPACE / "data" / "image_dataset"
DEFAULT_OUTPUT = (
    WORKSPACE
    / "src"
    / "line_follower_perception"
    / "models"
    / "best_line_follower_model_xy_retrained.pth"
)
LABEL_PATTERN = re.compile(r"^xy_(\d+)_(\d+)_.*\.(?:jpg|jpeg|png)$", re.IGNORECASE)
ROI_TOP = 500
ROI_BOTTOM = 948


class XYDataset(Dataset):
    def __init__(self, image_paths, augment=False):
        self.image_paths = image_paths
        self.augment = augment
        self.color_jitter = transforms.ColorJitter(0.3, 0.3, 0.3, 0.3)

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        image_path = self.image_paths[index]
        match = LABEL_PATTERN.match(image_path.name)
        if match is None:
            raise ValueError(f"Image filename does not contain xy labels: {image_path}")

        x_px, y_px = map(int, match.groups())
        if not (0 <= x_px <= 1920 and ROI_TOP <= y_px <= ROI_BOTTOM):
            raise ValueError(f"Label is outside the expected frame ROI: {image_path.name}")

        with Image.open(image_path) as source:
            image = source.convert("RGB")

        x = x_px / 960.0 - 1.0
        y = (y_px - ROI_TOP) / ((ROI_BOTTOM - ROI_TOP) / 2.0) - 1.0
        if self.augment:
            if torch.rand(()) > 0.5:
                image = transforms.functional.hflip(image)
                x = -x
            image = self.color_jitter(image)

        image = transforms.functional.resize(image, (224, 224))
        image = transforms.functional.to_tensor(image)
        image = transforms.functional.normalize(
            image,
            [0.485, 0.456, 0.406],
            [0.229, 0.224, 0.225],
        )
        return image, torch.tensor([x, y], dtype=torch.float32)


def main():
    parser = argparse.ArgumentParser(description="Train the ResNet18 XY line model.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--pretrained", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError("epochs and batch-size must be positive")

    image_paths = sorted(
        path
        for path in args.dataset.glob("*")
        if path.is_file() and LABEL_PATTERN.match(path.name)
    )
    if len(image_paths) < 2:
        raise RuntimeError(
            f"Need at least two labeled images in {args.dataset}; found {len(image_paths)}")

    generator = torch.Generator().manual_seed(args.seed)
    order = torch.randperm(len(image_paths), generator=generator).tolist()
    test_count = max(1, int(0.1 * len(order)))
    test_paths = [image_paths[index] for index in order[:test_count]]
    train_paths = [image_paths[index] for index in order[test_count:]]

    train_loader = DataLoader(
        XYDataset(train_paths, augment=True),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )
    test_loader = DataLoader(
        XYDataset(test_paths),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    weights = models.ResNet18_Weights.DEFAULT if args.pretrained else None
    model = models.resnet18(weights=weights)
    model.fc = torch.nn.Linear(512, 2)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    best_loss = float("inf")

    for epoch in range(args.epochs):
        model.train()
        train_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = F.mse_loss(model(images), labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        train_loss /= len(train_loader)

        model.eval()
        test_loss = 0.0
        with torch.no_grad():
            for images, labels in test_loader:
                images, labels = images.to(device), labels.to(device)
                test_loss += F.mse_loss(model(images), labels).item()
        test_loss /= len(test_loader)
        print(
            f"Epoch:{epoch + 1}/{args.epochs}, "
            f"Train loss:{train_loss:.6f}, Val loss:{test_loss:.6f}")
        if test_loss < best_loss:
            torch.save(model.state_dict(), args.output)
            best_loss = test_loss
            print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
