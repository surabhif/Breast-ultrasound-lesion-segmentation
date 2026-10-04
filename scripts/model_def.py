"""U-Net lesion segmentation with auxiliary benign-vs-malignant head.

ONNX contract (browser demo):
  input:        float32 [N, 3, H, W]  ImageNet-normalized RGB
  seg_mask:     float32 [N, 1, H, W]  sigmoid lesion probability
  cls_prob:     float32 [N, 1]        sigmoid P(malignant | lesion present)

Normal images are trained with empty masks so the model learns 'no lesion'.
Classification loss is applied only to benign/malignant cases.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# Default inference size for the shipped browser model
DEFAULT_IMG_SIZE = 128


class ConvBNReLU(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, k: int = 3) -> None:
        super().__init__()
        pad = k // 2
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, k, padding=pad, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class DoubleConv(nn.Module):
    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            ConvBNReLU(in_ch, out_ch),
            ConvBNReLU(out_ch, out_ch),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class TinyUNet(nn.Module):
    """Small from-scratch U-Net for quick CPU baselines."""

    def __init__(self, in_ch: int = 3, base: int = 16) -> None:
        super().__init__()
        self.enc1 = DoubleConv(in_ch, base)
        self.enc2 = DoubleConv(base, base * 2)
        self.enc3 = DoubleConv(base * 2, base * 4)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = DoubleConv(base * 4, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = DoubleConv(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = DoubleConv(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = DoubleConv(base * 2, base)
        self.seg_head = nn.Conv2d(base, 1, kernel_size=1)
        self.cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(base * 8, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        b = self.bottleneck(self.pool(e3))
        d3 = self.dec3(torch.cat([self.up3(b), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
        seg_logits = self.seg_head(d1)
        cls_logits = self.cls_head(b).squeeze(1)
        return seg_logits, cls_logits


class ResNetUNet(nn.Module):
    """U-Net with a torchvision ResNet-18 encoder (ImageNet pretrained optional)."""

    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        encoder = models.resnet18(weights=weights)
        self.stem = nn.Sequential(encoder.conv1, encoder.bn1, encoder.relu)
        self.pool = encoder.maxpool
        self.layer1 = encoder.layer1  # 64
        self.layer2 = encoder.layer2  # 128
        self.layer3 = encoder.layer3  # 256
        self.layer4 = encoder.layer4  # 512

        self.up4 = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.dec4 = DoubleConv(256 + 256, 256)
        self.up3 = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.dec3 = DoubleConv(128 + 128, 128)
        self.up2 = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.dec2 = DoubleConv(64 + 64, 64)
        self.up1 = nn.ConvTranspose2d(64, 64, 2, stride=2)
        self.dec1 = DoubleConv(64 + 64, 64)
        self.up0 = nn.ConvTranspose2d(64, 32, 2, stride=2)
        self.dec0 = DoubleConv(32, 32)
        self.seg_head = nn.Conv2d(32, 1, kernel_size=1)
        self.cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        s0 = self.stem(x)           # /2, 64
        s1 = self.pool(s0)          # /4
        s1 = self.layer1(s1)        # /4, 64
        s2 = self.layer2(s1)        # /8, 128
        s3 = self.layer3(s2)        # /16, 256
        s4 = self.layer4(s3)        # /32, 512

        d4 = self.dec4(torch.cat([self.up4(s4), s3], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), s2], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), s1], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), s0], dim=1))
        d0 = self.dec0(self.up0(d1))
        # Match input spatial size if off-by-one from odd dims
        if d0.shape[-2:] != x.shape[-2:]:
            d0 = F.interpolate(d0, size=x.shape[-2:], mode="bilinear", align_corners=False)
        seg_logits = self.seg_head(d0)
        cls_logits = self.cls_head(s4).squeeze(1)
        return seg_logits, cls_logits


def build_model(kind: str = "resnet18", pretrained: bool = True) -> nn.Module:
    kind = kind.lower()
    if kind in {"tiny", "quick", "baseline"}:
        return TinyUNet(base=16)
    if kind in {"resnet18", "full"}:
        return ResNetUNet(pretrained=pretrained)
    raise ValueError(f"Unknown model kind: {kind}")


class OnnxExportWrapper(nn.Module):
    """Wraps model to emit named sigmoid outputs for onnxruntime-web."""

    def __init__(self, core: nn.Module) -> None:
        super().__init__()
        self.core = core

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        seg_logits, cls_logits = self.core(x)
        seg_mask = torch.sigmoid(seg_logits)
        cls_prob = torch.sigmoid(cls_logits).unsqueeze(1)
        return seg_mask, cls_prob


def dice_loss_with_logits(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    targets = targets.float()
    dims = (1, 2, 3) if probs.ndim == 4 else (1, 2)
    inter = (probs * targets).sum(dim=dims)
    denom = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2 * inter + eps) / (denom + eps)
    return 1 - dice.mean()


def combined_seg_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(logits, targets.float())
    return bce + dice_loss_with_logits(logits, targets)


def classification_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """BCE only on benign/malignant (target >= 0); normals have target -1."""
    mask = targets >= 0
    if mask.sum() == 0:
        return logits.sum() * 0.0
    return F.binary_cross_entropy_with_logits(logits[mask], targets[mask].float())
