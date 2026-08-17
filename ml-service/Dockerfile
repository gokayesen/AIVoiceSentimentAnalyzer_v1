FROM python:3.13.15-slim

WORKDIR /app

# torchaudio.load() delegates to TorchCodec, which requires FFmpeg's shared
# libraries at runtime (versions 4-8 supported) — not just at test-fixture
# generation time (that's web-api's imageio-ffmpeg, a separate, portable
# binary never used here).
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app

# --extra-index-url points pip at PyTorch's CPU-only wheel index so the
# CPU-only torch/torchaudio builds are installed instead of the default PyPI
# wheels, which pull in unused CUDA runtime libraries despite this being a
# CPU-only deployment target (AD-18).
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu .

# Story 1.3 (AD-14): pre-fetch the SER classifier's weights at build time so
# the RQ worker's per-job execution path never needs network access —
# "local-only inference" means no per-request cloud call, not that weights
# can never be fetched once from the Hugging Face Hub (same category as the
# Silero VAD download, Story 1.2).
RUN python -c "from transformers import AutoFeatureExtractor, AutoModelForAudioClassification; m = 'superb/wav2vec2-base-superb-er'; AutoModelForAudioClassification.from_pretrained(m); AutoFeatureExtractor.from_pretrained(m)"

# Story 1.4 (AD-14): pre-fetch faster-whisper's model weights at build time
# too, same rationale as the SER classifier above — the RQ worker's per-job
# execution path never needs network access for STT either.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

# Story 1.5 (AD-14): pre-fetch the text-sentiment classifier's weights at
# build time too, same rationale as the SER/STT pre-fetches above.
RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; m = 'SamLowe/roberta-base-go_emotions'; AutoModelForSequenceClassification.from_pretrained(m); AutoTokenizer.from_pretrained(m)"

# Story 3.2: deliberately NOT pre-fetched here, unlike the three models
# above. pyannote's Community-1 diarization pipeline is HF-gated — unlike
# those three public models, downloading it requires a valid, license-
# accepted HF_TOKEN. Baking a pre-fetch into the image build would make
# `docker build` itself fail for anyone without one, breaking the build for
# every contributor/CI run lacking a personal gated-model token, not just
# degrading a runtime feature. Loaded lazily instead, at first mono-Call job
# execution (ml-service/app/pipeline/transcript/diarize.py's
# _get_diarize_pipeline) — a missing/invalid HF_TOKEN there degrades to a
# per-Call diarization failure (AD-1), never a build-time or worker-startup
# failure.

# Same baked-in-defaults rationale as web-api/Dockerfile: correct regardless
# of how the image is launched, not just under docker-compose.
ENV STORAGE_DIR=/storage
ENV DB_PATH=/storage/app.db
ENV REDIS_URL=redis://redis:6379/0
VOLUME ["/storage"]

CMD ["python", "-m", "app.worker"]
