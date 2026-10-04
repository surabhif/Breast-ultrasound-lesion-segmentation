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

DEFAULT_IMG_SIZE = 160


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


class _Up(nn.Module):
    """Bilinear upsample + 1×1 proj (fewer params than ConvTranspose for ONNX size)."""

    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.proj = nn.Conv2d(in_ch, out_ch, kernel_size=1, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = F.relu(self.bn(self.proj(x)), inplace=True)
        return torch.cat([x, skip], dim=1)


class ResNetUNet(nn.Module):
    """U-Net with torchvision ResNet-18 encoder; slim bilinear decoder for ~15MB INT8."""

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

        # Slimmer decoder than classic DoubleConv@256 to keep INT8 ≤ ~15 MB
        self.up4 = _Up(512, 128)
        self.dec4 = DoubleConv(128 + 256, 128)
        self.up3 = _Up(128, 64)
        self.dec3 = DoubleConv(64 + 128, 64)
        self.up2 = _Up(64, 32)
        self.dec2 = DoubleConv(32 + 64, 64)
        self.up1 = _Up(64, 32)
        self.dec1 = DoubleConv(32 + 64, 32)
        self.final_up = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False),
            ConvBNReLU(32, 16),
            nn.Conv2d(16, 1, kernel_size=1),
        )
        self.cls_head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(0.25),
            nn.Linear(512, 1),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        s0 = self.stem(x)  # /2, 64
        s1 = self.layer1(self.pool(s0))  # /4, 64
        s2 = self.layer2(s1)  # /8, 128
        s3 = self.layer3(s2)  # /16, 256
        s4 = self.layer4(s3)  # /32, 512

        d4 = self.dec4(self.up4(s4, s3))
        d3 = self.dec3(self.up3(d4, s2))
        d2 = self.dec2(self.up2(d3, s1))
        d1 = self.dec1(self.up1(d2, s0))
        seg_logits = self.final_up(d1)
        if seg_logits.shape[-2:] != x.shape[-2:]:
            seg_logits = F.interpolate(
                seg_logits, size=x.shape[-2:], mode="bilinear", align_corners=False
            )
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


def soft_dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    targets = targets.float()
    dims = (1, 2, 3)
    inter = (probs * targets).sum(dim=dims)
    denom = probs.sum(dim=dims) + targets.sum(dim=dims)
    dice = (2 * inter + eps) / (denom + eps)
    return 1.0 - dice.mean()


def combined_seg_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    dice_weight: float = 1.5,
    bce_pos_weight: float = 2.5,
) -> torch.Tensor:
    """BCE with positive weighting (lesions are sparse) + soft Dice."""
    pw = torch.tensor([bce_pos_weight], device=logits.device, dtype=logits.dtype)
    bce = F.binary_cross_entropy_with_logits(logits, targets.float(), pos_weight=pw)
    return bce + dice_weight * soft_dice_loss(logits, targets)


def classification_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """BCE only on benign/malignant (target >= 0); normals have target -1."""
    mask = targets >= 0
    if mask.sum() == 0:
        return logits.sum() * 0.0
    return F.binary_cross_entropy_with_logits(logits[mask], targets[mask].float())
