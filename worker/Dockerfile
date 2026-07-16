# RunPod Serverless worker — GPU upscale (Real-ESRGAN anime via spandrel)
FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Default model: Real-ESRGAN x4plus anime 6B (best for colored manhwa/webtoon).
# Swap MODEL_URL for any spandrel-supported .pth (Real-CUGAN, etc.).
ARG MODEL_URL=https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth
RUN mkdir -p /models && wget -q -O /models/model.pth "$MODEL_URL"
ENV MODEL_PATH=/models/model.pth

COPY handler.py upscale.py ./

CMD ["python", "-u", "handler.py"]
