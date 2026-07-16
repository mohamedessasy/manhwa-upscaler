"""GPU upscaling via spandrel (supports Real-ESRGAN / Real-CUGAN .pth models)."""
import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader

Image.MAX_IMAGE_PIXELS = None  # webtoon pages can be very tall


class Upscaler:
    def __init__(self, model_path: str, tile: int = 512, overlap: int = 16, fp16: bool = True):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        loaded = ModelLoader().load_from_file(model_path)
        self.scale = loaded.scale
        self.model = loaded.model.eval().to(self.device)
        self.fp16 = fp16 and self.device == "cuda"
        if self.fp16:
            self.model = self.model.half()
        self.tile = tile
        self.overlap = overlap
        print(f"[upscaler] model={model_path} scale={self.scale}x device={self.device} fp16={self.fp16}")

    @torch.inference_mode()
    def _run(self, t: torch.Tensor) -> torch.Tensor:
        return self.model(t)

    def upscale(self, img: Image.Image) -> Image.Image:
        arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
        t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(self.device)
        if self.fp16:
            t = t.half()
        out = self._tiled(t)
        out = out.squeeze(0).permute(1, 2, 0).float().clamp_(0, 1).cpu().numpy()
        return Image.fromarray((out * 255.0).round().astype(np.uint8))

    def _tiled(self, t: torch.Tensor) -> torch.Tensor:
        """Process in overlapping tiles so tall webtoon pages never OOM the GPU."""
        _, _, h, w = t.shape
        tile, ov, s = self.tile, self.overlap, self.scale
        if h <= tile and w <= tile:
            return self._run(t)
        out = torch.zeros(1, 3, h * s, w * s, device=t.device, dtype=t.dtype)
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(y - ov, 0), max(x - ov, 0)
                y1, x1 = min(y + tile + ov, h), min(x + tile + ov, w)
                patch = self._run(t[:, :, y0:y1, x0:x1])
                oy1, ox1 = min(y + tile, h), min(x + tile, w)
                iy0, ix0 = (y - y0) * s, (x - x0) * s
                out[:, :, y * s:oy1 * s, x * s:ox1 * s] = \
                    patch[:, :, iy0:iy0 + (oy1 - y) * s, ix0:ix0 + (ox1 - x) * s]
        return out
