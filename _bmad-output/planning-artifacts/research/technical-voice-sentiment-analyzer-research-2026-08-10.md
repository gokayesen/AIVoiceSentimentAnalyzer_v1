---
stepsCompleted: [1, 2]
inputDocuments: ['_bmad-output/planning-artifacts/briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md', '_bmad-output/planning-artifacts/briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/addendum.md']
workflowType: 'research'
status: 'complete'
lastStep: 2
research_type: 'technical'
research_topic: 'Voice-Based & Multimodal Sentiment Analysis — Technical Landscape for AI Voice Sentiment Analyzer'
research_goals: 'Resolve the technical unknowns the Product Brief deliberately left open (SER approach, acoustic features, STT, diarization, fusion strategy, datasets, evaluation, Turkish support, local vs cloud, audio processing, licensing/privacy), producing source-backed, comparative inputs for PRD and Architecture — without selecting final technology, models, or datasets, and without starting implementation.'
user_name: 'Gokayesen'
date: '2026-08-10'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical Research — AI Voice Sentiment Analyzer

**Date:** 2026-08-10
**Author:** Gokayesen
**Research Type:** technical

---

## Executive Summary

This research resolves, with evidence, the technical unknowns the [Product Brief](../briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md) deliberately left open. Headline findings:

- **A viable, permissively-licensed SER stack exists** (Wav2Vec2/HuBERT/WavLM, apache-2.0/MIT, fine-tuned on IEMOCAP/CREMA-D), but its accuracy on *this product's actual target audio* is unknown: the best directly relevant evidence (an IEMOCAP-trained architecture applied to real call-center audio) shows accuracy dropping from 63% to 45.6% (4-class UA) moving from lab to real call-center conditions — off-the-shelf benchmark numbers should be treated as an upper bound, not an expectation.
- **A genuine, published tension exists for the voice-first principle**: the one directly on-domain study found (call-center satisfaction prediction on the AlloSat corpus) found transcript content dominant and fusion benefit "not obvious." This does not invalidate voice-first as a design commitment, but it means the product should not assume the literature guarantees acoustic signal improves sentiment accuracy — this needs in-domain validation, not assumption.
- **Turkish SER has no direct evidence base**: no Turkish-specific SER model or paper was found; the only Turkish SER dataset (TurEV-DB, 1,735 tokens, amateur actors) is tiny. Turkish support must be positioned as experimental/best-effort, not a claimed capability.
- **Diarization may be unnecessary**: dual-channel (stereo) call recording — agent and customer on separate channels — is increasingly the default in modern telephony platforms. If the product's actual audio source provides stereo, per-channel splitting replaces model-based diarization entirely, sidestepping its hardest failure mode (overlapping/emotional speech). This is a genuinely open, high-leverage question for Architecture to resolve against the real intended input source.
- **No public, freely-licensed call-center-domain training dataset exists.** The realistic path is training/evaluating on general SER corpora (IEMOCAP, CREMA-D) and validating qualitatively on synthetic/self-recorded call-like audio — a limitation to state honestly in the product's own scope documentation, not hide.
- **The closest cloud acoustic-emotion API (Hume AI) is being discontinued** (June 2026); no major cloud vendor offers a first-class acoustic (as opposed to transcript-based) sentiment product. Combined with privacy/GDPR-KVKK considerations (voice is sensitive, re-identifiable data) and this being a portfolio project, local/open-weight inference is the better-evidenced default — a recommendation for Architecture, not a final decision.
- **A defensible MVP shape emerges from the evidence**: late/rule-based fusion (not early or learned fusion) of independently-confidenced acoustic and text signals, evaluated with UAR/macro-F1 (not raw accuracy) against majority-class and single-modality baselines, with confidence calibrated via temperature scaling and low-confidence/disagreement cases explicitly surfaced.

---

## Research Questions

1. What SER approaches (feature-based and pretrained-model-based) exist, and what are their realistic strengths/limitations for this product's audio?
2. How does voice-derived emotion information relate to and inform a sentiment judgment, conceptually and in practice?
3. Which acoustic features are established and practically extractable, and which are actually worth including in an MVP?
4. What STT options (local and cloud) realistically support English and Turkish, and how does phone-quality audio affect them?
5. Is speaker diarization actually necessary for this product's primary use case, and what are the practical options if so?
6. What multimodal fusion strategies exist, and which is defensible at MVP scale without a large labeled dataset?
7. What datasets (English, Turkish, call-center-specific) are actually usable, and under what license/access terms?
8. What evaluation metrics and baselining approach give an honest picture of MVP performance given class imbalance and no proprietary data?
9. What is the actual (not assumed) evidence for Turkish SER capability?
10. What are the real cost/privacy/accuracy/portfolio-value tradeoffs between local and cloud inference for this project specifically?
11. What audio formats, durations, and preprocessing does the pipeline need to realistically handle?
12. What licensing and privacy (GDPR/KVKK) considerations constrain technology and dataset choices?

---

## Research Overview

**Inputs:** This research builds directly on the [Product Brief](../briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md) and its [addendum](../briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/addendum.md), which established the product's non-negotiable principles (voice-first, human-in-the-loop, explainability/confidence/uncertainty as first-class, honest non-fabricated differentiation) and deliberately deferred all technology, model, and dataset selection to this phase.

**Scope:** Twelve topic areas, scoped by the product owner: (1) Speech Emotion Recognition, (2) Voice-Based Sentiment Analysis, (3) Acoustic Analysis, (4) Speech-to-Text, (5) Speaker Diarization, (6) Multimodal Fusion, (7) Datasets, (8) Model Evaluation, (9) Turkish Language Support, (10) Local vs. Cloud Inference, (11) Audio Processing Requirements, (12) Licensing and Privacy.

**Methodology:** Parallel research across current web sources, official documentation (via Context7 where applicable), model cards, and academic papers. Every substantive claim is labeled:
- **[VERIFIED]** — directly confirmed against an authoritative source (official docs, model card, license file).
- **[RESEARCH FINDING]** — reported in a paper/benchmark/study, with its dataset/context noted.
- **[RECOMMENDATION]** — a reasoned suggestion for this project, explicitly flagged as opinion, not fact.
- **[ASSUMPTION]** — unverified, flagged so it isn't mistaken for established fact.

No technology, model, or dataset is selected here — this document exists to give PRD and Architecture a source-backed comparative basis to decide from. No production-level accuracy is claimed without evidence, and "emotion recognition" and "sentiment analysis" are treated as related but distinct tasks throughout (see Finding 2).

---

## Findings

### 1. Speech Emotion Recognition (SER)

#### 1.1 Acoustic feature-based (classical ML) approaches

Classical SER pipelines extract MFCCs, prosodic features (pitch/F0, energy/intensity), and spectral features (e.g., Linear Predictive Coefficients), then feed them to classifiers such as SVM, Random Forest, Decision Tree, Logistic Regression, GMM, HMM, or KNN. **[RESEARCH FINDING]** A 2025 comparison on the acted, clean Berlin EmoDB dataset found a stacking ensemble reaching 97.2% accuracy and SVM 96.6%; a separate MFCC-only + SVM study on EmoDB reported 90.65%. ([source](https://dl.acm.org/doi/10.1145/3795154.3795232), [source](https://computing.louisiana.edu/sites/computing/files/Speech_Emotion_Recognition_Using_ML_Models_and_Audio_Features.pdf))

**[RESEARCH FINDING]** The field has broadly shifted toward deep learning (CNN, LSTM, CNN-LSTM, self-supervised transformer embeddings), driven by higher accuracy on both acted and naturalistic benchmarks. ([source](https://pmc.ncbi.nlm.nih.gov/articles/PMC7916477/), [source](https://www.sciencedirect.com/science/article/pii/S2667305323000911))

**[RECOMMENDATION]** Classical feature+classifier pipelines remain relevant not as the primary emotion classifier but as an interpretable, low-compute layer: MFCCs and prosody are cheap, map to understandable acoustic phenomena, and can support this product's explainability principle even where the primary SER signal comes from a learned embedding.

#### 1.2 Pretrained speech/audio models usable for SER

Verified via Context7 (Hugging Face Transformers, torchaudio) and model cards:

- **Wav2Vec2** (Meta) — `facebook/wav2vec2-base-960h`, license **apache-2.0** **[VERIFIED]** ([model card](https://huggingface.co/facebook/wav2vec2-base-960h)). Exposed via `torchaudio.pipelines` (`WAV2VEC2_ASR_BASE_960H`, `wav2vec2_xlsr_300m`, etc.) **[VERIFIED]** (Context7 `/pytorch/audio`).
- **HuBERT** (Meta) — `facebook/hubert-large-ls960-ft`, license **apache-2.0** **[VERIFIED]** ([model card](https://huggingface.co/facebook/hubert-large-ls960-ft)). torchaudio's `extract_features()` is explicitly documented as suitable for "downstream tasks like speaker verification or emotion recognition" **[VERIFIED]**.
- **WavLM** (Microsoft) — repository licensed **MIT** **[VERIFIED]** ([license](https://github.com/microsoft/unilm/blob/master/LICENSE)). Emphasizes both content and speaker-identity modeling; available via `torchaudio.models.wavlm_base/large`.

All three are typically fine-tuned by adding a classification head on pooled hidden states, trained on a labeled emotion dataset (IEMOCAP, RAVDESS, CREMA-D, MSP-Podcast).

**[RESEARCH FINDING]** On the SUPERB benchmark (frozen-feature protocol) on IEMOCAP (4-class, 5-fold CV), HuBERT-large reached 67.62% weighted accuracy (WA); with fine-tuning allowed, a partially fine-tuned HuBERT reached 79.58% WA (speaker-dependent) / 73.01% WA (speaker-independent). ([arXiv:2111.02735](https://arxiv.org/abs/2111.02735)) This refines the Product Brief's earlier finding: Wav2Vec2/HuBERT are SOTA-class on IEMOCAP, but **frozen-feature use is meaningfully weaker than fine-tuning** (~68% vs. ~74–80%).

#### 1.3 Concrete current open-source SER model options

All verified directly from HuggingFace model cards:

| Model | Base | Training data | Reported metric | License |
|---|---|---|---|---|
| `superb/wav2vec2-base-superb-er` | Wav2Vec2-base, frozen | IEMOCAP (4-class, 5-fold CV) | **62.58% accuracy** [VERIFIED] | apache-2.0 |
| `speechbrain/emotion-recognition-wav2vec2-IEMOCAP` | Wav2Vec2-base, fine-tuned | IEMOCAP | **78.7% (avg 75.3%) accuracy** [VERIFIED] | apache-2.0 |
| `ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition` | Wav2Vec2-large-XLSR-53, fine-tuned | RAVDESS (acted, 8-class) | **82.23% eval accuracy** [VERIFIED] | apache-2.0 |
| `audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim` | Wav2Vec2-large-robust, pruned, fine-tuned | MSP-Podcast v1.7 (~84h naturalistic) | Continuous arousal/valence/dominance; no accuracy figure published | **cc-by-nc-sa-4.0, research-only — commercial use needs a separate audEERING license** [VERIFIED] |

**Known limitations:**
- SpeechBrain's own card states it provides **no warranty on performance on other datasets** [VERIFIED] — directly relevant since call-center audio ≠ IEMOCAP.
- The RAVDESS-trained model's 82% figure is on clean, acted, single-sentence audio with no documented limitations section; real-world transfer is **[ASSUMPTION]** unverified.
- The audeering dimensional model is research-only by license and trained on podcast (not telephone) audio; a domain gap to phone-quality two-party calls likely remains **[ASSUMPTION]**.

#### 1.4 Realistic emotion taxonomies

**[RESEARCH FINDING]** Two established taxonomies: **categorical** (discrete labels like angry/happy/sad/neutral — simple but "enforce rigid boundaries that overlook the continuous nature of emotional expression") and **dimensional** (valence-arousal-dominance — captures nuance but harder to collect/less human-readable). ([source](https://www.mdpi.com/2076-3417/15/2/623))

**[RECOMMENDATION]** For a call-center QA tool: a reduced, balanced categorical set (4-class, matching the SUPERB/IEMOCAP protocol) is the best-evidenced configuration; binary/coarse categories (e.g., Anger vs. Neutral) show markedly higher, more stable accuracy on real call-center-like data (see 1.5), suggesting coarse escalation-relevant categories may be the most reliable MVP signal. A dimensional (arousal/valence) layer as a secondary, continuous signal could complement discrete categories for confidence/trend visualization — this is opinion, not evidenced by a specific call-center deployment.

#### 1.5 Honest strengths, weaknesses, and limitations for call-center use

**[RESEARCH FINDING] The naturalistic domain gap is large and quantified.** A controlled study using the same architecture on IEMOCAP and CEMO (a real emergency call-center dataset: 440 dialogs, 2h16m, 485 speakers) found: 4-class UA **63% (IEMOCAP) vs. 45.6% (CEMO)**; 2-class (Anger/Neutral) UA **81.1% (IEMOCAP) vs. 76.9% (CEMO)**. ([arXiv:2110.14957](https://arxiv.org/abs/2110.14957)) This confirms and quantifies the Product Brief's earlier finding — and shows the accuracy gap **narrows sharply when the task is simplified to a coarse binary distinction**, a concrete argument for MVP scope reduction.

**[RESEARCH FINDING]** Noise/codec robustness is an open problem: "most SER models trained with clean noiseless data are not very useful in real-world conditions where noise is almost always present," and codec/bitrate choices materially affect preserved emotional cues. ([source](https://arxiv.org/html/2311.07093v4), [source](https://arxiv.org/pdf/2505.24248))

**[RESEARCH FINDING]** Cross-corpus/cross-speaker generalization is a known, actively-researched weakness (recording conditions, microphone quality, acted-vs-natural elicitation, speaker demographics, label-distribution mismatch). ([source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9514941/))

**[RECOMMENDATION]** SER on call-center audio should be assumed to perform meaningfully below both clean-dataset numbers (RAVDESS/CREMA-D) and even IEMOCAP numbers, unless validated on representative in-domain (phone-quality, overlapping, unscripted) data. Any off-the-shelf SER model's stated accuracy should be treated as an upper bound, not an expectation — directly reinforcing the Product Brief's "no accuracy claims without evidence" principle.

### 2. Voice-Based Sentiment Analysis

#### 2.1 Emotion recognition vs. sentiment analysis — the distinction

**[VERIFIED]** These are related but distinct tasks: **sentiment analysis** classifies along a polarity axis (positive/negative/neutral, sometimes with intensity); **emotion recognition** classifies discrete affective categories (anger, happiness, sadness, fear, disgust, surprise) or continuous dimensions — finer-grained than polarity. ([source](https://optiblack.com/insights/sentiment-analysis-vs-emotion-recognition), [source](https://dialzara.com/blog/emotion-recognition-vs-sentiment-analysis-differences-explained)) Two representation schemes exist: **categorical** (Ekman's 6/Plutchik's 8) and **dimensional** (Russell's 1980 valence-arousal circumplex). Sentiment polarity most directly corresponds to the **valence** axis; arousal has no direct sentiment analogue. ([Russell 1980](https://psu.pb.unizin.org/psych425/chapter/circumplex-models/))

**[RESEARCH FINDING — literature blurs the line, flagged as requested]** A 2024 survey of 154 NLP emotion-analysis papers found the field itself lacks a settled boundary between sentiment and emotion tasks ([arXiv:2403.01222](https://arxiv.org/abs/2403.01222)). Benchmark datasets institutionalize the blur: CMU-MOSI/MOSEI carry both continuous sentiment-intensity labels *and* discrete Ekman-style emotion labels on the same utterances, treating them as complementary annotations rather than cleanly separated tasks ([arXiv:2505.06110](https://arxiv.org/abs/2505.06110)). Some non-authoritative sources flatly claim "emotion detection is a subset of sentiment analysis" — this report does **not** endorse that framing; it erases the categorical-vs-polarity distinction the rigorous literature treats as real.

**Implication for this product:** SER and sentiment analysis are not interchangeable outputs. A pipeline that produces an emotion label and silently reports it as "sentiment" is imprecise. The product should keep them as distinguishable outputs (emotion categories/timeline as one artifact, sentiment polarity+confidence as a related but separate artifact).

#### 2.2 How acoustic/voice-derived emotion signals inform sentiment judgments

**[RESEARCH FINDING]** No single, universally standardized emotion→sentiment polarity lookup table exists, but there's a conceptual bridge: valence (dimensional model) is the closest formal analogue to sentiment polarity ([aclanthology.org/W18-3306](https://aclanthology.org/W18-3306.pdf)). Common heuristic mapping (inferred from how CMU-MOSEI assigns both label types to the same clips, not a codified standard): happiness/joy→positive; anger/sadness/fear/disgust→negative; neutral/surprise→ambiguous. **[ASSUMPTION]** a validated categorical-emotion→sentiment-polarity mapping specific to call-center speech does not appear to exist in the literature — it would need to be built/validated by the project itself.

**[RESEARCH FINDING — important, directly on-domain, surfaced honestly]** In a call-center satisfaction/frustration study on the **AlloSat** corpus, researchers found **linguistic (transcript) content was the dominant contributor** to satisfaction prediction and generalized best to unseen data, while "the benefit of fusing acoustic and linguistic modalities is not as obvious." ([arXiv:2310.04481](https://arxiv.org/pdf/2310.04481)) **This is real, published, call-center-domain evidence that acoustic signal does not always add clear value over text alone for satisfaction/sentiment-style targets.** It does not falsify the product's voice-first principle, but it means voice-first is a *design commitment*, not something the literature guarantees will improve sentiment accuracy — this should be stated honestly, not glossed over.

#### 2.3 End-to-end audio sentiment prediction vs. fused multi-model approaches

**[RESEARCH FINDING]** Both exist in the literature; neither is "solved." **Multimodal Sentiment Analysis (MSA)** is an established subfield studying exactly this question ([survey: arXiv:2305.07611](https://arxiv.org/pdf/2305.07611)). CMU-MOSI (2,199 utterances, 93 speakers, -3..+3 scale) and CMU-MOSEI (~23,500 clips, 1,000+ speakers, sentiment + 6 emotions + VAD) are the standard benchmarks. Audio-only end-to-end models are competitive on some benchmarks, but **fusion architectures are the more heavily represented, generally higher-performing paradigm** in the modern literature (Tensor Fusion Network, MulT, and successors are all fusion architectures) — though a 2017-era study reported linguistic modality as the biggest single-modality contributor. A middle-ground pattern is emerging: train a multimodal "teacher," distill into an audio-only "student" that's efficient at inference but has absorbed cross-modal signal during training ([arXiv:2607.06611](https://arxiv.org/html/2607.06611v1)). In a comparable domain (music), audio+text outperformed either alone, with empirically-tuned weighting (60/40) — illustrating optimal fusion weighting is task/domain-specific, not a transferable constant ([arXiv:2405.01988](https://arxiv.org/pdf/2405.01988)).

**[RECOMMENDATION]** Given (a) fusion architectures dominate published benchmarks, (b) the directly analogous AlloSat call-center study found linguistic content dominant with unclear fusion benefit, and (c) this product wants voice treated as first-class/primary evidence — a **fused, multi-signal approach (separate acoustic-emotion and text-sentiment signals combined, not one end-to-end audio→sentiment model)** is more defensible than a pure end-to-end audio model: it preserves per-modality interpretability (a voice-first requirement), doesn't require a large labeled audio-to-sentiment training set, and matches how the literature evaluates MSA today. This is about the conceptual approach, not a specific architecture — Architecture's decision.

### 3. Acoustic Analysis

#### 3.1 Relevant acoustic features

- **Prosody/pitch (F0):** Intonation contour; pitch variability/mean shifts classically associated with arousal (higher/more variable F0 with anger/fear/excitement; flatter with sadness).
- **Energy/loudness:** Correlates with vocal effort/arousal; spikes can signal emphasis or frustration.
- **Speaking rate:** Faster speech often tied to excitement/anxiety; slower to sadness/hesitancy/cognitive load.
- **Pauses/voice activity (VAD):** Pause duration/frequency and turn-taking indicate hesitation or interruption; also structurally necessary to segment agent vs. customer speech.
- **Spectral features — MFCCs:** Compact spectral-envelope (timbre) representation; the dominant handcrafted SER feature for decades. **[VERIFIED]** computable via `librosa.feature.mfcc` (Context7 `/websites/librosa_doc`).
- **Formants:** Vocal-tract resonance frequencies; used in voice-quality/stress analysis via Praat/parselmouth.
- **Jitter/shimmer:** Cycle-to-cycle F0/amplitude variation; voice-quality/perturbation markers, historically used in stress detection.

#### 3.2 Concrete open-source tools/libraries

| Tool | Purpose | License | Maintenance | Notes |
|---|---|---|---|---|
| **librosa** | MFCC, F0 (`pyin`), spectral centroid/bandwidth/contrast/rolloff, RMS energy, ZCR | **ISC** [VERIFIED] | Active — v0.11.0, Mar 2025, NumPy 2.0 support | Easiest general-purpose Python entry point (Context7 `/websites/librosa_doc`). |
| **openSMILE / eGeMAPS** (`opensmile-python`) | Industry-standard prosodic/spectral/voice-quality set purpose-built for affect (eGeMAPSv02: 25 descriptors, 88 functionals) | **Source-available — audEERING Research License; free for research/education, commercial product use requires a separate paid license** [VERIFIED] ([license](https://github.com/audeering/opensmile-python/blob/main/LICENSE)) | Active (audEERING GmbH, since 2013) | Most directly relevant off-the-shelf feature set for this product, but **license blocks commercial use** without paying — flag for Architecture. |
| **Praat/parselmouth** | Pitch, HNR, jitter, shimmer, formants (via Praat bindings) | **GNU GPLv3+** [VERIFIED] | Active | Copyleft — bundling into a commercial product may carry obligations; needs legal review. |
| **torchaudio** | Audio I/O/DSP transforms + pretrained SSL model access | **BSD-2-Clause** (PyTorch ecosystem standard) | Active (Meta/PyTorch Foundation) | One dependency for both handcrafted features and pretrained embeddings (Context7 `/pytorch/audio`). |
| **Silero VAD** | Neural voice-activity detection | **MIT** [VERIFIED] | Active, lightweight (~1–2MB, <1ms/30ms chunk CPU) | **[RESEARCH FINDING]** 2025 benchmark: 87.7% TPR @ 5% FPR; ROC-AUC 0.90 (Libryparty)/0.99 (AVA). |

#### 3.3 Features most useful for an MVP

**[RECOMMENDATION]** Given the product's voice-first + explainability + confidence-first principles: (1) F0 statistics, (2) energy/RMS statistics, (3) speaking rate, (4) VAD-derived pause/turn-taking metrics (needed anyway for two-party segmentation), (5) MFCCs (as classifier input or SSL-embedding complement). De-prioritized for MVP (not excluded later): jitter/shimmer and formants — real and evidenced in voice-quality research, but noisier to extract from phone-quality/overlapping audio and less established in SER accuracy studies specifically. A scoping judgment, not a claim these features are unhelpful.

#### 3.4 Handcrafted features vs. pretrained embeddings — is manual extraction still justified?

**[RESEARCH FINDING]** Accuracy trends favor learned SSL embeddings (67–80% WA fine-tuned on IEMOCAP vs. classical MFCC+SVM/RF), though classical pipelines still post very high numbers on clean acted datasets (90–97% on EmoDB) — a fair comparison must control for dataset.

**[RECOMMENDATION]** This is a real tradeoff, not a solved question:
- **For pretrained embeddings:** higher accuracy ceiling on harder/naturalistic data; less manual engineering; permissively licensed (Wav2Vec2/HuBERT: apache-2.0; WavLM: MIT).
- **For handcrafted features:** interpretability — a QA analyst asking "why was this flagged?" can be shown "pitch rose 40Hz, rate +20%, energy spiked," which an opaque 768-dim embedding cannot offer without extra explainability tooling; eGeMAPS was specifically designed for affective-computing interpretability, not just accuracy; cheaper to compute/audit; gives a cross-check signal independent of a black-box embedding.
- **Net assessment:** the evidence supports using **both** — pretrained embeddings as the primary accuracy-driving signal, with a parallel handcrafted-feature layer (F0/energy/rate/pauses minimum) serving explainability, confidence calibration, and sanity-checking. An architecture-level decision, not resolved here.

### 4. Speech-to-Text (STT)

#### 4.1 Open-source / local options

- **OpenAI Whisper** (large-v3/turbo) — **[VERIFIED]** MIT license, free commercial+non-commercial use ([license](https://github.com/openai/whisper/blob/main/LICENSE)). Trained on 30s chunks; long-form handled via internal sliding-window/chunk-stitch heuristics, described by Hugging Face itself as "a set of (hacky) heuristics" **[VERIFIED]**. **[RESEARCH FINDING]** ~6.43% WER on the Open ASR Leaderboard's largely-English aggregate ([HF blog](https://huggingface.co/blog/open-asr-leaderboard)) — no longer SOTA vs. newer entrants. **[VERIFIED, peer-reviewed]** Turkish WER 4.3–14.2% depending on model size/fine-tuning ([MDPI](https://www.mdpi.com/2079-9292/13/21/4227)); Turkish (like Japanese/Korean/Arabic/Hindi/Vietnamese) generally scores worse than English on Whisper. **[VERIFIED — known, current issue]** Hallucinates repeated/fabricated phrases during silence/low-energy audio (near-zero embeddings cause decoder looping; YouTube-caption training bias produces clichés like "Thank you for watching") — long-standing and still current. Mitigation: VAD pre-filtering, or trimming (not deleting) long silences to preserve sentence-boundary cues. ([discussion](https://github.com/openai/whisper/discussions/1606), [discussion](https://github.com/openai/whisper/discussions/2378))
- **faster-whisper** (CTranslate2 reimplementation) — **[VERIFIED]** up to 4x faster than reference Whisper at equal accuracy ([GitHub](https://github.com/SYSTRAN/faster-whisper), Context7 `/systran/faster-whisper`). `BatchedInferencePipeline` adds another 2-4x on batch jobs (directly relevant — this product is batch, not real-time) and enables `vad_filter=True` by default, directly mitigating the hallucination-on-silence issue. Needs CUDA12+cuDNN9 for GPU; CPU+int8 viable for lower volume. **[ASSUMPTION]** License commonly cited as MIT but not independently re-confirmed against the current LICENSE file this pass.
- **NVIDIA NeMo — Parakeet/Canary** — **[VERIFIED]** support 25 European languages; **Turkish is not among them** (an HF community request for Turkish exists with no NVIDIA commitment) ([discussion](https://huggingface.co/nvidia/canary-1b-v2/discussions/2)). Licensing split: NeMo framework Apache-2.0; **Parakeet weights CC BY 4.0 (commercial OK)**; **Canary weights CC BY-NC 4.0 (non-commercial only)**. Effectively English-only options today.
- **Vosk** — **[VERIFIED]** offline, 20+ languages incl. Turkish, ~50MB models, streaming API ([GitHub](https://github.com/alphacep/vosk-api)). **[RESEARCH FINDING — gap]** no credible Turkish WER figures found this pass.
- **wav2vec2/XLS-R Turkish fine-tunes** — **[VERIFIED]** community fine-tunes exist, e.g. `mpoyraz/wav2vec2-xls-r-300m-cv7-turkish` at 8.62% WER on Common Voice 7 TR ([model card](https://huggingface.co/mpoyraz/wav2vec2-xls-r-300m-cv7-turkish)). **[ASSUMPTION]** figures are on Common Voice (clean read-speech) — real-world/phone-quality performance is unmeasured and likely materially worse.

#### 4.2 Cloud APIs

**[VERIFIED]** Google Cloud STT (Chirp 3, 73 languages/137 variants, Turkish included), Azure AI Speech (140+ languages, `tr-TR` supported, batch+real-time+custom adaptation), AWS Transcribe/Amazon Connect Contact Lens (Turkish added to Contact Lens March 2025; purpose-built Call Analytics product for sentiment/call-drivers/summarization). **[RESEARCH FINDING — vendor marketing, unverified]** Deepgram Nova-3 explicitly added Turkish and claims sub-300ms latency and multi-dialect Turkish coverage — self-reported, not third-party verified. None of the cloud vendors publish per-language accuracy figures in the sources found.

#### 4.3 Phone-quality / conversational audio degradation

**[RESEARCH FINDING — vendor blog, directional only]** Narrowband 8kHz telephony vs. 16kHz+ wideband is estimated to add 8-12 percentage points absolute WER, up to 15-20% relative increase, because 8kHz caps frequency content at ~3.4kHz — discarding the high-frequency energy that distinguishes consonants like s/f/th, exactly what ASR confuses most. VoIP codec artifacts compound this further (G.729 codec ~10-15% relative WER degradation; 3-5% packet loss noticeably degrades performance); legacy telephony ASR is reported to see real-world WER of 40-50% even when the same model scores single digits on clean studio audio. ([source](https://docs.vobiz.ai/blogs/what-is-voice-transcription-asr)) **[VERIFIED, peer-reviewed]** Sound quality materially affects ASR-produced telephone caption accuracy ([ASHA journal](https://pubs.asha.org/doi/10.1044/2022_AJA-22-00102)). **Implication:** whichever STT is chosen must be benchmarked against phone-quality/VoIP-codec audio specifically, not clean-speech leaderboards — this gap appears larger than the English-vs-Turkish gap in some cited figures.

#### STT Comparison Table

| Option | Local/Cloud | EN support evidence | TR support evidence | License/Cost | Notable limitation |
|---|---|---|---|---|---|
| OpenAI Whisper (large-v3) | Local | ~6.43% WER (leaderboard) | 4.3–14.2% WER (peer-reviewed) | MIT, free | Hallucinates on silence; 30s native window |
| faster-whisper | Local | Same accuracy, 4x faster | Same weights, same TR caveats | MIT (re-verify) | Needs CUDA12/cuDNN9 for GPU path |
| NVIDIA Parakeet-TDT | Local | 25 EU languages, fast | **Not supported** | CC BY 4.0 (commercial OK) | No Turkish |
| NVIDIA Canary-1B-v2 | Local | Top leaderboard accuracy | **Not supported** | **CC BY-NC 4.0 — non-commercial only** | Not commercially usable; no Turkish |
| Vosk | Local | Supported, unverified WER | Supported, unverified WER | Apache 2.0 (verify) | No credible accuracy data found |
| wav2vec2/XLS-R (TR fine-tunes) | Local | N/A | 8.6–10.6% WER (Common Voice, clean only) | Varies per model | Not benchmarked on phone-quality audio |
| Google Cloud STT (Chirp 3) | Cloud | 73 languages | Supported | Usage-based | No published per-language accuracy |
| Azure AI Speech | Cloud | 140+ languages | `tr-TR` supported | Usage-based | No published per-language accuracy |
| AWS Transcribe (Call Analytics) | Cloud | Purpose-built for call-center | TR added 2025 (Contact Lens) | Usage-based | Call Analytics may be a distinct product from raw Transcribe |
| Deepgram Nova-3 | Cloud | Strong marketing claims | TR explicitly added | Usage-based | Vendor self-reported claims |

### 5. Speaker Diarization

#### 5.1 Is diarization actually necessary?

**[RECOMMENDATION — conditional, this is a key finding]** Depends entirely on input channel format. **[VERIFIED]** Dual-channel (stereo) recording — agent on one channel, customer on the other — is increasingly the *default* in modern CCaaS/telephony platforms (Twilio made it default for all accounts; Talkdesk defaults it for new accounts). ([Twilio](https://www.twilio.com/en-us/changelog/dual-channel-voice-recordings-by-default), [Talkdesk](https://support.talkdesk.com/hc/en-us/articles/115002325846-Dual-Channel-Recordings)) When stereo is available, per-channel speaker attribution is essentially free and near-perfect — no diarization model needed; a simple channel split + independent VAD/energy analysis per channel suffices, and this sidesteps the overlapping-speech problem entirely (see 5.4). When only mono/mixed-down audio is available (legacy PBX, mobile recordings, downmixed transfers), diarization becomes necessary since per-speaker sentiment attribution can't be recovered otherwise.

**[ASSUMPTION — open product question]** The Product Brief specifies "single audio file per call" but not channel count. **This is a genuinely open question for Architecture/PRD to resolve against the product's actual intended ingestion source** — not something resolvable by research alone. **[RECOMMENDATION]** Detect channel count on ingest; skip model-based diarization for plausible stereo, run a diarization model for mono. This also gives a natural cross-check signal when both are available.

#### 5.2 Open-source options

- **pyannote.audio** — **[VERIFIED]** three tiers (confirmed via Context7 `/pyannote/pyannote-audio` + HF cards): `speaker-diarization-3.1` (**MIT**, free forever), `speaker-diarization-community-1` (**CC-BY-4.0**, gated but free incl. commercial use, usable fully offline after one-time auth), `speaker-diarization-precision-2` (commercial, cloud-only via pyannoteAI's paid API — **not local/offline**). **[RESEARCH FINDING]** DER benchmarks ([pyannoteAI](https://www.pyannote.ai/benchmark)): AMI 18.8%→17.0%→12.9%; VoxConverse 11.2%→11.2%→8.5%; AISHELL-4 12.2%→11.7%→11.4% (3.1 → community-1 → paid precision-2). Paid tier is meaningfully more accurate but requires sending audio off-premises.
- **NVIDIA NeMo MSDD (telephonic)** — **[VERIFIED]** a telephonic-tuned variant exists (`diar_msdd_telephonic`, trained on ~1,500h of Fisher Corpus telephone conversations) — directly relevant to call-center audio characteristics ([NGC](https://catalog.ngc.nvidia.com/orgs/nvidia/nemo/models/diar_msdd_telephonic/-?_lr=1)). No DER figure retrieved; NGC-specific license terms not independently re-verified.
- **WhisperX** — combines faster-whisper + wav2vec2 forced alignment + pyannote community-1 into one pipeline; up to 70x real-time via batching. **[RESEARCH FINDING — inconsistent]** license reported as BSD-2 in one description vs. BSD-4 in the repo listing — needs direct LICENSE-file verification. Diarization accuracy is bounded by pyannote's own numbers (doesn't independently improve it).
- **Picovoice Falcon** (commercial SDK) — **[RESEARCH FINDING — vendor self-reported, cautioned]** claims 10.3% DER vs. its own reported 9.0% for pyannote on VoxConverse — conflicts with pyannoteAI's own self-reported 11.2%, so cross-vendor DER figures are not directly comparable without matching methodology/version.

#### 5.3 Cloud diarization options

**[VERIFIED — feature exists]** AWS Transcribe (up to 10 speakers), Azure Speech batch (diarization caps file length at 4 hours), Google STT (speaker labeling) all offer diarization as a feature. **[RESEARCH FINDING — single, uncorroborated, cautioned]** Picovoice's own benchmark reports AWS at 11.1% DER and Google at a striking 50.2% DER outlier with undisclosed methodology — **not to be treated as reliable without independent corroboration**. **[VERIFIED — general]** cloud vendors generally market diarization as a binary feature rather than a benchmarked capability, so vendor selection here can't be done on published evidence alone.

#### 5.4 Overlap, cross-talk, and the emotional-moment problem

**[RESEARCH FINDING]** Overlapping speech is one of the largest contributors to diarization error; DER in spontaneous/overlapping conversation is reported at 10-20% even for leading systems — notably worse than clean-benchmark numbers above. **[ASSUMPTION, but directly consequential]** Interruptions and talking-over are more likely during emotionally charged moments — exactly when this product cares most about accurate attribution. This means diarization confidence is likely systematically lower exactly when correct speaker attribution matters most — reinforcing the need to surface per-segment confidence rather than assume it. This is reasoned extrapolation, not a directly measured finding for emotional speech specifically — flag as a hypothesis to validate. **[VERIFIED]** Voice characteristics changing with emotion/fatigue is also cited as a diarization complication (embeddings used for clustering can drift within a single speaker over an emotional call).

#### Diarization Comparison Table

| Option | License | Accuracy evidence | Integration | Notable limitation |
|---|---|---|---|---|
| pyannote 3.1 | MIT, free forever | 11.2–18.8% DER | Low (pip install) | Superseded in accuracy by newer tiers |
| pyannote community-1 | CC-BY-4.0, gated (free) | 11.2–17.0% DER | Low, offline after one-time auth | Not the most accurate pyannote tier |
| pyannote precision-2 | Commercial cloud API | 8.5–12.9% DER (best) | Low API call | **Not local** — audio leaves premises |
| NeMo MSDD (telephonic) | Apache-2.0 framework; NGC terms unverified | No figure found | Higher (YAML-driven) | Telephonic-tuned (relevant), but license/accuracy unquantified here |
| WhisperX (wraps pyannote) | BSD-2 or BSD-4 (verify) | Bounded by pyannote community-1 | Low, single pipeline | Not an independent accuracy improvement |
| AWS/Azure/Google (built-in) | Commercial, usage-based | Single-source, uncorroborated (AWS 11.1%, Google 50.2% outlier) | Low | No official per-vendor DER published |
| Picovoice Falcon | Commercial SDK | 10.3% DER (self-reported) | Low, proprietary | Vendor self-comparison, unverified |

### 6. Multimodal Fusion Strategies

#### 6.1 Fusion strategy taxonomy: early, late, hybrid/intermediate

**[VERIFIED]** definitions, consistent across sources:

| Strategy | Mechanism | Key tradeoffs |
|---|---|---|
| **Early fusion** | Raw/low-level features from each modality concatenated before a single model | Captures fine-grained cross-modal correlation, but high-dimensional/redundant; can't cleanly handle differing modality sampling rates; brittle if one modality is noisy/missing (whole vector corrupted) |
| **Late/decision-level fusion** | Each modality modeled independently; outputs combined at the end | Computationally efficient, independently trainable/updatable, more robust to a missing/noisy modality — but ignores low-level cross-modal interaction entirely |
| **Hybrid/intermediate fusion** | Learned intermediate representations per modality that interact (cross-attention, tensor products) before/alongside independent paths | Best empirical performance in much of the MSA literature, but higher complexity, more data-hungry, less interpretable per-modality |

**[RESEARCH FINDING]** A comparative fusion-strategy study concludes: *"late fusion is well-suited for resource-constrained scenarios, hybrid fusion is preferable when pursuing peak performance, and early fusion should be applied with caution."* ([ACM 2026](https://dl.acm.org/doi/10.1145/3803686.3803688))

**Concrete examples:** Tensor Fusion Network (Zadeh et al., EMNLP 2017) — intermediate/hybrid fusion via outer-product tensor modeling intra+inter-modality dynamics ([ACL D17-1115](https://aclanthology.org/D17-1115/)); MulT (Tsai et al., ACL 2019) — intermediate fusion via directional cross-modal attention, designed for *unaligned* multimodal sequences without forcing early concatenation ([arXiv:1906.00295](https://arxiv.org/abs/1906.00295)); late/decision fusion with logit averaging — simpler, reported to outperform early fusion in at least one acoustic+text SER study ([arXiv:2403.18635](https://arxiv.org/html/2403.18635v1)).

#### 6.2 Rule-based vs. learned fusion

**[RESEARCH FINDING]** Rule-based decision-level fusion (majority voting, weighted averaging, confidence-based weighting) is the *most commonly adopted* mechanism specifically in multimodal **emotion recognition** (as opposed to large MSA benchmarks) — likely because it doesn't require jointly-trained cross-modal data. Confidence-adaptive weighting (dynamically weighting by each modality's own per-instance confidence) is reported as an improvement over fixed weights.

**[RECOMMENDATION]** Rule-based fusion (confidence-weighted averaging of acoustic-emotion and text-sentiment signals, with an explicit override/flag rule on strong disagreement) is more appropriate for this project than a trained fusion model because: (1) a learned fusion model (Tensor Fusion Network/MulT-style) needs a reasonably sized, jointly-labeled audio+text+sentiment dataset in the target domain — none exists for call-center dialogue (CMU-MOSI/MOSEI are monologue YouTube reviews, a domain-transfer risk); (2) rule-based fusion is directly auditable/explainable, a hard product requirement, vs. an opaque learned model's internal weighting; (3) late/decision fusion is specifically noted as more robust to a missing/degraded modality — directly useful when STT quality is poor or audio is noisy.

#### 6.3 A practical MVP-scale fusion approach **[RECOMMENDATION]**

Late/decision fusion, not early or full hybrid fusion. Each modality (acoustic-emotion model, text-sentiment/NLP model) produces its own calibrated confidence alongside its output. Combine via a transparent rule (confidence-weighted average of polarity/valence-mapped signals), with an explicit conflict-handling rule for strong disagreement (surface both signals + flag for human review rather than silently averaging them away) — directly serves human-in-the-loop and "surface low confidence, don't hide it." This is buildable without a large labeled multimodal dataset and leaves room to later replace the rule with a learned combiner if labeled data is collected. Final selection belongs to Architecture.

#### 6.4 Confidence/uncertainty propagation through the pipeline

**[RESEARCH FINDING]** Realistic-for-MVP techniques, simplest → most sophisticated:
1. **Native model confidence** (softmax probability) — simplest, but known to be poorly calibrated on its own.
2. **Calibration (temperature scaling)** — **[VERIFIED]** neural networks are typically overconfident; temperature scaling (a single learned scalar dividing logits before softmax) is a simple, effective fix, outperforming more complex alternatives, validated on vision and NLP tasks ([Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf)). **Realistic for MVP** — cheap, well-understood, needs only a held-out calibration set.
3. **Ensemble disagreement** — **[VERIFIED]** variance/disagreement across independently trained models as an uncertainty estimate ([Lakshminarayanan et al., NeurIPS 2017](https://proceedings.neurips.cc/paper/2017/file/9ef2ed4b7fd2c810847ffa5fa85bce38-Paper.pdf)). **[RESEARCH FINDING]** caveat: independently trained networks can converge to overly similar predictions ("epistemic collapse"), undermining the diversity the method relies on; also costly (multiple full models). Realistic only at small scale (2-3 lightweight models).
4. **Monte Carlo Dropout** — cheaper Bayesian approximation, practical to bolt onto an existing trained network, but has documented theoretical limitations (induced posterior doesn't match a proper Bayesian posterior) and mixed empirical benefit. Borderline for MVP.
5. **Conformal prediction** — **[VERIFIED]** distribution-free framework with formal statistical coverage guarantees, usable on top of any pretrained model without retraining ([Angelopoulos & Bates, arXiv:2107.07511](https://arxiv.org/abs/2107.07511)). Rigorous and model-agnostic, but produces sets not single scalars (needs UX translation work) — realistic to explore, adds overhead beyond calibration.
6. **Full Bayesian neural networks** — **[RESEARCH FINDING]** theoretically principled but computationally expensive; research-grade/overkill for an MVP.

**[RECOMMENDATION]** Calibrate each modality's native confidence via temperature scaling (even against a small held-out set); propagate calibrated confidence into the fusion rule as the weighting factor; treat large disagreement between modality confidences/outputs as an *additional* uncertainty signal that lowers fused confidence and/or triggers a "flag for review" state. Ensemble/MC-Dropout/conformal methods are reasonable stretch goals, not required for a defensible MVP.

### 8. Model Evaluation

#### 8.1 Metrics for SER and sentiment analysis

**[VERIFIED]** Metric choice matters heavily due to class imbalance. **UAR (Unweighted Average Recall / balanced accuracy)** — average of per-class recall, each class weighted equally — is the standard, community-preferred SER metric *because* SER datasets are commonly imbalanced (e.g., "neutral" dominates), and plain/weighted accuracy is dominated by majority classes, masking poor performance on minority, often more product-relevant classes like anger. **WAR (Weighted Average Recall)** ≈ plain accuracy weighted by class frequency — reported as a secondary metric, known to be inflated by majority-class performance. For general classification (including sentiment), the same logic maps to **macro-F1 vs. weighted-F1 vs. accuracy**: macro-F1 (analogous to UAR) is recommended when minority classes matter equally; weighted-F1 "can still be dominated by the majority class"; plain accuracy is explicitly called "ineffective" for imbalanced data.

#### 8.2 Class imbalance — concrete evidence

**[VERIFIED]** In IEMOCAP, one of the most-used SER benchmarks, "neutral" is consistently the largest class — reported distributions range from Neutral 30.9% (4-class merge: sad 19.6%, happy 29.6%, neutral 30.9%, angry 19.9%) to Neutral 48.8% in another split, illustrating both the imbalance itself and that even its *magnitude* is reported inconsistently across papers depending on preprocessing. ([arXiv:2312.06337](https://arxiv.org/html/2312.06337v1))

**[RECOMMENDATION]** Report UAR/macro-F1 as the *primary* metric for both the emotion classifier and any categorical sentiment classifier; report plain accuracy and weighted-F1 only as secondary context, never as the headline number — given the near-certainty of "neutral"-class dominance in any realistically obtainable call-center-style data.

#### 8.3 Cross-dataset / domain generalization

**[VERIFIED — directly relevant, reinforces Finding 1.5]** Training an SER architecture on IEMOCAP then applying it unchanged to CEMO (real emergency call-center data) dropped UA from 63% to 45.6% — a ~17-point absolute drop moving from lab to real call-center audio; the most frequent emotions also differ qualitatively between settings. ([arXiv:2110.14957](https://arxiv.org/abs/2110.14957)) **[RESEARCH FINDING]** A broader cross-corpus study across four English SER datasets found naive cross-corpus/multi-domain training "is not successful" — simple dataset pooling doesn't transfer well; domain adversarial training and targeted adaptation were needed for meaningful positive transfer, particularly acted→naturalistic. ([arXiv:2207.02104](https://arxiv.org/abs/2207.02104)) Causes: differing annotation protocols, recording/microphone conditions, acted-vs-natural elicitation, speaker demographics.

**Implication:** any accuracy/UAR claim for the SER or fusion component based on public benchmarks must be explicitly caveated as **not representative of expected in-domain (call-center) performance** without validation on representative in-domain data.

#### 8.4 Establishing a realistic MVP baseline (no proprietary labeled data) **[RECOMMENDATION]**

1. **Majority-class baseline** — predict the most frequent class always; report its UAR/macro-F1 (low by construction) as the floor any real system must clear. This operationalizes the "accuracy is misleading" lesson from §8.1 — a majority-class baseline can post deceptively high *accuracy* while having near-zero UAR.
2. **Single-modality baselines** — evaluate acoustic-only and text-only independently before evaluating the fused system, so any fusion approach must be shown to add value over the better single modality — directly motivated by the AlloSat finding (§2.2) that fusion benefit is *not automatic*.
3. **Public-benchmark sanity-check + in-domain spot validation** — use public SER/MSA benchmarks for initial model selection, but per §8.3's evidence of large cross-domain drops, label any such numbers as **upper-bound/optimistic estimates**, not expected in-product performance, until validated against even a small manually-labeled in-domain (or in-domain-like) sample.
4. **[ASSUMPTION]** A small manually-annotated validation set (dozens–low-hundreds of utterances) is likely the most cost-effective way to get an honest in-domain baseline for a solo developer — too small to *train* a robust model, but useful for validation, with results described as low-confidence/wide-interval, not a precise accuracy claim.

### 11. Audio Processing Requirements

**Formats:** **[RECOMMENDATION]** accept WAV/MP3/M4A at minimum (the likely real-world set from phones/PBX/softphone exports); normalize everything internally to 16kHz mono 16-bit PCM WAV before any model sees it — **[VERIFIED]** this is the near-universal ASR input standard, via ffmpeg (`-ar 16000 -ac 1`).

**Channels:** **[VERIFIED]** dual-channel (stereo) is increasingly the default in modern telephony platforms (see 5.1) — the single highest-leverage practical shortcut available (free near-perfect speaker separation), but not assumable as universal; older/on-prem PBX may still export mono.

**Maximum duration:** **[VERIFIED]** cloud ceilings exist (Google batch: 8h/file; Azure batch: 240min when diarization is enabled). **[RESEARCH FINDING — gap]** no AWS max-duration figure found. **[ASSUMPTION]** local models have no vendor ceiling but are bounded by GPU memory/wall-clock time; a typical call-center call (minutes to ~1h) should be tractable on a modern GPU via faster-whisper's batched pipeline, but this was not benchmarked directly — validate with representative file lengths during Architecture/prototyping.

**Preprocessing:** **[VERIFIED]** standard chain: resample to 16kHz, downmix to mono (unless preserving stereo for channel-based diarization), 16-bit PCM, VAD-based silence trimming, gain/level normalization. **[RESEARCH FINDING — vendor-blog estimate, directional]** gain normalization ~5-10% WER reduction; VAD trimming ~30-50% processing-time reduction. **[VERIFIED — caution]** naive silence *deletion* can hurt accuracy by destroying sentence-boundary cues; better practice is trimming long gaps (>1.5s) to a short fixed pause (0.3-0.5s) rather than removing them outright.

**Chunking and the emotional timeline:** **[VERIFIED]** Whisper's long-form handling uses sliding-window or chunk-and-stitch internally. **[ASSUMPTION — analogical, not audio-verified]** text-sentiment literature documents a known chunk-boundary failure mode (splitting an emotionally salient exchange across a boundary can flip the sentiment score, since each chunk is scored independently); this plausibly extends to an audio emotional timeline (a "calm→furious" transition split mid-chunk could produce two internally-consistent-but-locally-wrong readings) but is not directly measured for audio/SER — treat as a design risk to validate, not fact. **[RECOMMENDATION]** if/when a chunking strategy is designed, prefer VAD-based natural boundaries over fixed-duration windows, and carry some rolling context (prior chunk's trailing emotional state or short audio overlap) across boundaries to protect the confidence/uncertainty and voice-first principles from chunk-boundary artifacts.

### 7. Datasets

#### 7.1 English/international SER datasets beyond IEMOCAP/RAVDESS/CREMA-D

| Dataset | Size | Naturalism | License/Access | Train | Eval | Demo |
|---|---|---|---|---|---|---|
| IEMOCAP | ~12h, 10 actors, dyadic scripted+improvised | Semi-naturalistic | **[VERIFIED]** Custom non-commercial license, signed release required via USC SAIL ([source](https://sail.usc.edu/iemocap/iemocap_release.htm)) | No (NC) | Yes | Yes |
| RAVDESS | 24 actors | Acted/clean | **[VERIFIED]** CC BY-NC-SA 4.0; commercial license purchasable separately ([source](https://zenodo.org/records/1188976)) | No (NC) | Limited | Yes |
| CREMA-D | 7,442 clips, 91 actors | Acted, crowd-validated | **[VERIFIED]** ODbL 1.0 + DbCL 1.0 — open, share-alike, attribution-required, **permits commercial use** ([source](https://github.com/CheyneyComputerScience/CREMA-D/blob/master/LICENSE.txt)) — most permissive of the "big three" | Yes | Yes | Yes |
| MELD | ~13k utterances, 1,433 dialogues (*Friends* TV show), 7 emotions | Multimodal, multi-party, conversational, but scripted TV dialogue | **[RESEARCH FINDING]** GPLv3 — copyleft; community itself disputes whether this attaches to *trained models* (unresolved GitHub issue) — treat as ambiguous/risky | Risky | Yes | Yes |
| CMU-MOSEI | 65+h, 1,000+ speakers | Naturalistic (YouTube monologues) | **[RESEARCH FINDING]** Videos CC (personal use); annotations under a less-restrictive, commercially-usable license | Possible | Yes | Yes — not dyadic/call-like though |
| MSP-IMPROV / MSP-Podcast | Multi-hr / large, growing | Semi-naturalistic / naturalistic | **[VERIFIED]** Free academic license requires institutional signing authority; commercial ~$8,000 (MSP-IMPROV) — **not realistically obtainable by a solo, non-institutional developer** ([source](https://lab-msp.com/MSP/MSP-Improv.html)) | No (access barrier) | No (access barrier) | No |

**[RESEARCH FINDING]** A consistent pattern: the more naturalistic/valuable the corpus (IEMOCAP, MSP-Podcast, MSP-IMPROV), the more restrictive the access (non-commercial-only or institutional-signature-only). This materially limits what a solo developer can legally use beyond evaluation/demo.

#### 7.2 Call-center / conversational-specific datasets — honest assessment

**[RESEARCH FINDING — significant]** There is **no broadly public, freely downloadable, real call-center audio dataset with sentiment/emotion labels** suitable for training. What exists: CEMO (French medical emergency calls, 20h, research-only, no self-service download), NSED (18k+ codemixed customer-care recordings, industry-partnership only, not public), "CusEmo" (French call-center, academic/proprietary partnership), AxonData's HF listing (commercial vendor data-sales, not free — **[ASSUMPTION]** needs direct verification), LDC corpora (paid membership/per-corpus fees, not free even where "public").

**[RECOMMENDATION]** For a solo-developer portfolio project, call-center-*specific* training data essentially does not exist in the open domain. Practical path: train/fine-tune on general conversational-emotion corpora (IEMOCAP for dyadic structure, CREMA-D for permissively-licensed balanced labels) and demo/evaluate qualitatively on synthetic or self-recorded call-like audio — being transparent in the product's stated limitations that a true call-center-domain-matched dataset was not available. This finding is significant enough that it should shape the product's stated scope/limitations, not just a footnote.

#### 7.3 Turkish datasets — verification and update

- **BUEMDB** — **[RESEARCH FINDING]** small, acted, F0-focused; no self-service public download found — access appears to require contacting the original researchers. Status unchanged from Product Brief research.
- **TurEV-DB** — **[VERIFIED]** confirmed as Turkey's sole representative corpus in the EmoBox multilingual SER benchmark ([EmoBox GitHub](https://github.com/emo-box/EmoBox)). **[RESEARCH FINDING — gap]** specific numeric Turkish accuracy/UAR results from EmoBox could not be extracted from the abstract/webpage in this pass — the full paper/repo needs direct consultation before citing a number.
- **Movie-derived corpus ("TURES")** — **[RESEARCH FINDING, unverified access]** ~5,100 utterances, 55 Turkish movies, 7 emotions + VAD labels; its dedicated site (turesdatabase.com) was **unreachable** during this research (DNS failure) — current accessibility/license is uncertain, possibly defunct, needs re-check.
- **TREMO — important correction:** **[VERIFIED]** TREMO ("A dataset for emotion analysis in Turkish") is a **TEXT dataset** (27,350 written short stories, NLP-style emotion classification), **not** a speech/audio SER resource, despite surfacing in "Turkish emotion recognition" searches. Must not be conflated with a Turkish SER corpus.
- **[RESEARCH FINDING]** No newer (2023–2026) Turkish SER audio dataset was found — the Turkish SER dataset landscape appears essentially unchanged since the Product Brief research.

### 9. Turkish Language Support (open technical question)

**[VERIFIED]** No published Turkish-specific SER (audio emotion) model with reported accuracy was found on Hugging Face or in papers. All Turkish wav2vec2-based models found (`m3hrdadfi/wav2vec2-large-xlsr-turkish`, `ozcangundes/...`, `aniltrkkn/...`) are **ASR models** (transcription, e.g. WER 27.51), not emotion classifiers — this distinction matters and is easy to miss in a casual search.

**[RESEARCH FINDING, incomplete]** TurEV-DB's inclusion in EmoBox (Interspeech 2024, [arXiv:2406.07162](https://arxiv.org/abs/2406.07162)) is the only concrete Turkish SER benchmark-adjacent evidence found, but specific numeric Turkish results could not be extracted in this pass — a gap, not a negative finding.

**[RESEARCH FINDING]** No paper combining a Turkish-fine-tuned wav2vec2/XLS-R model with an emotion head and reporting Turkish SER accuracy was found — multiple targeted queries converged on the same small set of known corpora and ASR-only models, suggesting a genuine literature gap, not just a search miss.

**[RESEARCH FINDING — general cross-lingual SER evidence, not Turkish-specific]** XLS-R-style multilingual pretraining generally outperforms monolingual pretraining after fine-tuning, especially for low-resource languages ([source](https://arxiv.org/html/2306.13804v2)). However, SER-specific cross-lingual transfer research reports **degraded generalization** when models trained on one language are evaluated zero-shot on an unseen language; dimensional properties (arousal) transfer somewhat better than discrete category transfer, but not reliably into higher accuracy ([source](https://arxiv.org/abs/2606.06200)). These findings are about cross-lingual SER in general (not studied on Turkish specifically in the sources found) — extrapolating to Turkish is **[ASSUMPTION]**, not verified Turkish evidence.

**[RECOMMENDATION]** Given (a) no Turkish SER model/paper exists to fine-tune from or compare against, (b) only one tiny (1,735-token, amateur-actor) Turkish SER dataset is realistically obtainable, (c) general cross-lingual SER research shows real degradation on unseen languages — the most defensible options are: (i) fine-tune a multilingual backbone (XLS-R/Whisper-encoder-class) on the small available Turkish data, openly reporting this as a small-data exploratory result, not a validated capability; or (ii) restrict strong claims to English and treat Turkish as an explicitly labeled "experimental/best-effort" mode. This is reasoning from general transfer-learning principles plus the cross-lingual literature above — **not** from Turkish-specific validation. That distinction must be preserved downstream.

### 10. Local vs. Cloud Inference (general deployment question)

#### 10.1 Cost (order-of-magnitude)

**[RESEARCH FINDING, approximate figures from mixed-reliability sources]** Azure AI Speech: ~$1/hr real-time, ~$0.18–0.36/hr batch. AWS Transcribe: $0.024/min standard down to $0.0078/min at scale; **Call Analytics (bundles sentiment) $0.035/min**. Google Cloud STT V2: $0.016/min standard, $0.004/min with 24h-turnaround batch.

**[VERIFIED — significant finding]** **Hume AI's Expression Measurement API** — the one notable dedicated voice-*emotion* cloud API found ($0.0639/min) — **is being sunset; last day to run jobs is June 14, 2026, i.e., no longer usable going forward.** **[RESEARCH FINDING]** No major cloud provider (Azure/AWS/Google) offers a dedicated *acoustic* voice-emotion API as a first-class product — their "sentiment" offerings operate on the **text transcript**, not the raw acoustic signal. This is directly consequential for this product's voice-first principle: **the cloud path for sentiment specifically is transcript-based, not acoustic** — a genuine acoustic cloud SER API is essentially unavailable now that Hume is sunsetting.

**Local:** no per-minute marginal cost beyond already-owned hardware + electricity. **[RECOMMENDATION]** for low/irregular volume (portfolio demo, not production traffic), cloud per-minute cost is trivially small in absolute terms — cost alone doesn't strongly favor either path at this scale.

#### 10.2 Hardware requirements for local inference

**[RESEARCH FINDING]** Whisper large-v3: ~10GB VRAM unquantized, ~3-6GB with INT8 (faster-whisper) — runs on an 8-12GB consumer GPU or Apple Silicon with sufficient unified memory. Wav2Vec2-base/HuBERT-base (more relevant SER backbones): ~90-95M params, ~360-380MB FP32 — an order of magnitude smaller than Whisper-large.

**[ASSUMPTION, reasoned from model size]** Given this project is batch (not real-time), a base/large Wav2Vec2/HuBERT/XLS-R-class SER model is plausibly runnable even on CPU-only hardware within acceptable batch latency (seconds-to-low-minutes per call), without a dedicated GPU. Not directly benchmarked in this research — validate empirically rather than assume at architecture time.

#### 10.3 Latency, privacy, accuracy, DX, portfolio value

- **Latency:** irrelevant for a batch/post-call tool; neither path is a hard blocker.
- **Privacy — the most substantive differentiator:** audio sent to third-party cloud APIs leaves the developer's control, subject to each vendor's retention/training-use policies (**[RESEARCH FINDING — gap]** not independently verified per-vendor this pass). Given voice is sensitive/biometric-adjacent (§12), local inference structurally avoids third-party data transfer — a meaningful privacy-by-design argument.
- **Accuracy:** **[RESEARCH FINDING — gap]** no direct like-for-like cloud-vs-local acoustic-SER accuracy comparison exists, largely because cloud providers don't offer a comparable acoustic-SER product anymore. **[ASSUMPTION]** transcript-based cloud sentiment likely underperforms a dedicated acoustic model on the voice-first dimension specifically, consistent with general SER literature, but not independently verified with numbers here.
- **Developer experience:** HF `transformers`/`speechbrain` local APIs are mature and well-documented; cloud SDKs are polished but add account/auth/billing overhead. Neither is a major blocker.
- **Portfolio value — [RECOMMENDATION, deliberately non-diplomatic]:** calling a cloud sentiment API demonstrates integration skill, not ML engineering skill. Running/fine-tuning/evaluating a local Wav2Vec2/HuBERT-class model — including navigating the licensing/dataset-scarcity problems documented in §7/§9 — is what would actually differentiate this as an ML engineering portfolio piece versus an "API wrapper" project.

#### 10.4 Practical assessment for this project **[RECOMMENDATION]**

Given a single developer, no dedicated GPU budget, batch processing, voice-first as a stated principle, and portfolio-value goals: running a local, open-weight SER model (likely CPU-feasible given batch tolerance and small model size) is more consistent with the project's own stated principles and goals than calling a cloud API. A reasoned recommendation for Architecture to weigh — not a final decision, and STT/diarization may have different local/cloud tradeoffs than SER specifically (Whisper-class ASR needs more local resources than SER models).

### 12. Licensing and Privacy

**⚠ This entire section is informational, not legal advice. Consult a qualified lawyer before any commercial launch or handling of real personal data.**

#### 12.1 License-type summary across items surveyed above

| Category | Examples | Note |
|---|---|---|
| Permissive/commercial-OK | CREMA-D (ODbL, share-alike), CMU-MOSEI annotations | "Commercial-OK" ≠ "no strings attached" — attribution/share-alike still applies |
| Non-commercial/research-only | IEMOCAP, RAVDESS, MSP-IMPROV/Podcast academic tier | Blocks future commercial use of raw data or models trained under NC restriction |
| Copyleft on the data itself | MELD (GPLv3) | Unusually strict; community itself unsettled on whether this attaches to trained models — unresolved |
| Paid commercial licensing available | MSP-IMPROV ($8,000 tier), RAVDESS (by request) | Not free, but a real priced path if ever needed |
| Proprietary API terms | Azure/AWS/Google speech & sentiment APIs, Hume (sunsetting) | Usage rights tied to ongoing subscription; Hume's sunset illustrates single-vendor dependency risk for a core capability |
| Access-gated, terms unclear | BUEMDB, TURES (site unreachable) | Cannot be responsibly assessed until direct access to terms is obtained |

**[RESEARCH FINDING]** No dataset examined is unambiguously "freely usable for any purpose including commercial" without at least an attribution or share-alike obligation — CREMA-D (ODbL) is closest to unrestricted commercial usability, but still carries share-alike terms for derivatives.

#### 12.2 Voice/audio privacy — general risk understanding

**[RESEARCH FINDING]** Voice carries re-identification risk even after nominal "anonymization." A 2026 large-scale study (~5,000 speakers) found re-identification/linkability risk in anonymized speech is highly polarized by speaker rather than uniform, and that prior average-case metrics (equal error rate) understated real risk against modern speaker-verification attackers ([source](https://arxiv.org/pdf/2606.07210)). Related research documents "soft biometric leakage" — non-unique traits (age range, sex, dialect, speaking style) surviving de-identification even when exact identity doesn't ([source](https://arxiv.org/html/2509.14469)). **Practical takeaway:** a transcript can be trivially de-identified by removing names; raw or lightly-processed audio retains re-identification risk text does not — directly relevant to a voice-first, acoustic-signal-primary product design.

#### 12.3 GDPR — informational, not legal advice

**[RESEARCH FINDING]** GDPR Article 9 prohibits processing "special category" data (incl. biometric data used for unique identification) unless a specific Article 9(2) condition is met, in addition to a general Article 6 lawful basis — two separate, cumulative tests ([source](https://gdpr-info.eu/art-9-gdpr/)). **Nuance:** voice/biometric data is only specifically "special category" under Article 9 when processed *for the purpose of unique identification* (e.g., speaker verification) — general acoustic *analytics* (emotion/sentiment scoring, not identifying who's speaking) may fall outside strict Article 9 classification per one source, though this reading is contested ([source](https://summitnotes.app/blog/gdpr-voice-recordings-biometric-data/)). **[ASSUMPTION/caveat]** this project doesn't do speaker ID by design, but does process the acoustic signal directly — the conservative posture is to still treat voice recordings as sensitive. Where Article 9 applies, consent must be clear, affirmative, specific, unambiguous — not a bundled checkbox.

#### 12.4 KVKK — informational, not legal advice

**[RESEARCH FINDING]** KVKK (Turkey) Article 6 explicitly lists **biometric and genetic data** as "özel nitelikli kişisel veri" (special-category personal data). Turkish legal commentary states voice recordings processed for identification purposes are classified as biometric special-category data under Article 6, carrying heavier compliance obligations ([source](https://www.kvkk.gov.tr/Icerik/2051/Ozel-Nitelikli-Kisisel-Veriler)). Processing special-category data generally requires **explicit consent (açık rıza)**; the disclosure obligation (aydınlatma yükümlülüğü) applies with no exceptions regardless of legal basis.

**[RECOMMENDATION]** For a portfolio project: use synthetic/self-recorded/consented demo audio rather than real customer call recordings; if real-world-sounding data is ever used, default to the stricter of GDPR/KVKK biometric-data assumptions (explicit consent + minimal retention + no unnecessary speaker-identification capability) rather than relying on the narrower "not identification-purposed" carve-out.

---

## Technology / Model Options (Consolidated)

Full comparison tables are in each Finding section; this is a cross-cutting summary. All options below are viable candidates for Architecture to evaluate — none is selected here.

| Layer | Leading local/open options | Leading cloud options | Key cross-cutting constraint |
|---|---|---|---|
| SER (emotion) | Wav2Vec2/HuBERT/WavLM fine-tunes (apache-2.0/MIT); classical MFCC+SVM/ensemble for interpretability | None viable — Hume AI (the only dedicated acoustic-emotion API) is sunsetting June 2026; cloud "sentiment" = transcript-based only | No option benchmarked on real call-center audio; expect accuracy well below published numbers (§1.5, §8.3) |
| Acoustic features | librosa (ISC), openSMILE/eGeMAPS (research-only license, commercial needs paid license), Praat/parselmouth (GPLv3, copyleft risk), Silero VAD (MIT) | N/A | eGeMAPS licensing and parselmouth's GPLv3 both need explicit legal review before commercial use (§3.2) |
| STT | Whisper/faster-whisper (MIT); NeMo Parakeet (CC BY 4.0, no Turkish); Vosk, wav2vec2-XLS-R Turkish fine-tunes | Google Chirp 3, Azure AI Speech, AWS Transcribe (Call Analytics), Deepgram Nova-3 — all support Turkish | Phone-quality/VoIP-codec audio degrades all options materially more than the EN-vs-TR language gap (§4.3) |
| Diarization | pyannote.audio (MIT / CC-BY-4.0 tiers), NeMo MSDD-telephonic (Apache-2.0 framework) | AWS/Azure/Google built-in (unverified accuracy) | May be unnecessary if input audio is dual-channel (§5.1) — resolve this before comparing diarization models at all |
| Fusion | Rule-based/late fusion (no license concern — it's an architectural pattern, not a package) | N/A | Learned fusion (Tensor Fusion Network/MulT-style) requires labeled data this project doesn't have (§6.2) |

## Dataset Options (Consolidated)

See the full comparison table in Finding 7.4. Summary: **CREMA-D** is the only "big three" SER dataset with an unambiguously commercial-permitting license (ODbL, share-alike). IEMOCAP and RAVDESS are non-commercial by license. No public, free, call-center-domain dataset exists. Turkish SER datasets are limited to TurEV-DB (tiny, amateur actors) with uncertain access for BUEMDB and the TURES movie corpus (site unreachable during this research).

## Recommended Direction(s)

These are reasoned recommendations for Architecture to weigh, not decisions:

1. **SER**: fine-tune a permissively-licensed pretrained embedding model (Wav2Vec2/HuBERT/WavLM family) on CREMA-D + IEMOCAP (eval-only use of IEMOCAP given its NC license), paired with a lightweight handcrafted-feature layer (F0, energy, speaking rate, pauses via librosa/Silero VAD) for explainability and cross-checking (§1.2, §3.4).
2. **Emotion taxonomy**: start with a coarse/binary or small categorical set (e.g., anger vs. neutral, or a reduced 4-class scheme) rather than fine-grained categories — the evidence shows coarse categories are meaningfully more robust on real call-center-like audio (§1.4, §1.5).
3. **STT**: local faster-whisper with VAD-filtering enabled by default (mitigates hallucination-on-silence, supports batch throughput) as the primary candidate; Turkish accuracy should be benchmarked directly against representative phone-quality audio before relying on published Common Voice figures (§4.1, §4.3).
4. **Diarization**: do not assume it's needed — first determine whether the product's real audio source delivers dual-channel recordings; if so, channel-splitting replaces diarization entirely and sidesteps its hardest failure mode (§5.1).
5. **Fusion**: rule-based/late fusion of independently-confidenced acoustic and text signals at MVP scale, with an explicit disagreement-surfacing rule, not a trained fusion model (§6.2, §6.3).
6. **Confidence**: temperature-scale each modality's native confidence; propagate into the fusion rule; treat modality disagreement itself as an uncertainty signal (§6.4).
7. **Evaluation**: UAR/macro-F1 as headline metrics; majority-class and single-modality baselines before crediting fusion with any benefit; treat public-benchmark numbers as optimistic upper bounds pending in-domain validation (§8.1, §8.4).
8. **Turkish**: position as an explicitly experimental/best-effort mode (multilingual backbone fine-tuned on the small available Turkish data), not a claimed capability equal to English (§9).
9. **Deployment**: local/open-weight inference is better aligned with this project's privacy posture, batch (not real-time) nature, and portfolio-value goal than cloud APIs — but STT and SER may have different local-resource footprints and should be evaluated separately (§10.4).

## Rejected / Less Suitable Alternatives and Why

- **NVIDIA NeMo Canary** — top accuracy on the Open ASR Leaderboard, but weights are CC BY-NC 4.0 (non-commercial only) and it doesn't support Turkish — rejected for this product's needs on both license and language grounds (§4.1).
- **Cloud acoustic-emotion APIs (Hume AI)** — the one dedicated option is being discontinued; not a viable long-term dependency (§10.1).
- **openSMILE/eGeMAPS as a default choice** — the most purpose-built interpretable feature set for affective computing, but its research-only license blocks commercial use without a paid audEERING license; librosa/torchaudio-based handcrafted features are the license-safe fallback (§3.2).
- **Early/full end-to-end audio-to-sentiment fusion** — competitive on some academic benchmarks, but requires a large jointly-labeled multimodal dataset this project doesn't have, and sacrifices the per-modality interpretability the product's explainability principle requires (§2.3, §6.2).
- **Learned/trained fusion models (Tensor Fusion Network, MulT-style)** — best empirical performance in the literature, but data-hungry and opaque; rejected for MVP specifically (not permanently) in favor of rule-based fusion (§6.2).
- **Praat/parselmouth as a default dependency if bundling matters** — real, useful feature extraction, but GPLv3 copyleft creates distribution obligations that need legal review before committing to it as a core dependency (§3.2).
- **Ensemble-disagreement and Monte Carlo Dropout as primary MVP uncertainty methods** — both carry documented theoretical/practical limitations (epistemic collapse; posterior mismatch) and added engineering cost; temperature-scaled calibration is the better-justified MVP default, with these as stretch goals (§6.4).

## Technical Risks

1. **Domain gap risk (highest severity)**: every accuracy figure surfaced in this research comes from lab/acted or non-call-center-domain data; the one directly relevant cross-domain study (IEMOCAP→CEMO) shows a ~17-point absolute accuracy drop. Real performance on this product's actual audio is unknown until validated.
2. **Voice-first vs. evidence tension**: the AlloSat call-center study found transcript content dominant with fusion benefit "not obvious" — the product's core principle is a design commitment that the literature does not guarantee will win on accuracy; this must be tested in-domain, not assumed.
3. **Turkish support risk**: no direct evidence base exists; any Turkish capability claim beyond "experimental" would be unsupported by current evidence.
4. **Unresolved input-format question**: whether target audio is mono or stereo materially changes whether diarization is a required pipeline stage — an open product/architecture question, not a research one.
5. **No public call-center-domain dataset**: training/eval data scarcity is structural, not solvable by more research — it shapes what claims the finished product can honestly make.
6. **Licensing fragmentation**: eGeMAPS (research-only), Canary (non-commercial), IEMOCAP/RAVDESS (non-commercial), MELD (GPLv3, ambiguous re: trained models), parselmouth (GPLv3) — a real portfolio-to-commercial licensing cliff exists if this project is ever taken beyond a demo.
7. **Vendor dependency risk**: Hume AI's sunset illustrates the risk of anchoring a core capability to a single proprietary API.
8. **Privacy/legal exposure**: voice is re-identifiable, sensitive data under both GDPR and KVKK; using real-sounding call recordings without consent carries real (if currently low-stakes, portfolio-scale) legal exposure — informational only, not legal advice (§12).
9. **Chunking/timeline integrity risk**: splitting long audio at fixed-duration boundaries (rather than natural/VAD boundaries) risks corrupting the emotional timeline at exactly the moments (transitions) the product cares most about — reasoned by analogy from text-sentiment literature, not directly measured for audio, but a real design risk to test early (§11).

## Open Questions

*(Consolidated from all Findings sections — see each Finding for full context.)*

- What does EmoBox actually report as Turkish (TurEV-DB) SER accuracy, and are there any cross-lingual transfer numbers to Turkish specifically? (§9)
- Are BUEMDB and the TURES movie corpus currently accessible, and under what terms? (§7.3)
- What are each cloud vendor's actual audio data-retention/training-use policies? (§10.3)
- Is the product's real target audio source mono or stereo? (§5.1, §11 — the single highest-leverage open question)
- Does a codified categorical-emotion→sentiment-polarity mapping need to be built and validated in-house, given none exists in the literature for this use case? (§2.2)
- Does MELD's GPLv3 license attach to models trained on it — even the dataset's own user community hasn't resolved this? (§7.1)
- What is AWS Transcribe's actual maximum batch file duration? (§11)
- Is the emotional-timeline chunk-boundary risk real for audio/SER specifically, not just analogically reasoned from text sentiment? (§11, Technical Risk 9)
- Is cross-corpus domain adaptation (DAT or similar) worth the added complexity for MVP, or should the product rely on in-domain validation data instead? (§8.3)

## Implications for PRD

- **Turkish language support should not be stated as a committed MVP feature without an explicit "experimental/best-effort" qualifier** — the evidence does not support a stronger claim (§9).
- **The dashboard/UX should have a designed way to surface acoustic-vs-text disagreement**, not just a single fused number — this follows directly from the fusion recommendation (§6.3) and the human-in-the-loop principle.
- **Any stated accuracy/confidence expectations in the PRD must avoid numbers pulled from public benchmarks** (RAVDESS/CREMA-D/IEMOCAP) — those are known to overstate real-world, in-domain performance (§1.5, §8.3).
- **Whether the product requires per-speaker (agent vs. customer) breakdown should be explicitly scoped as depending on input audio format** — this is a PRD-level scoping decision informed by §5.1, not purely a technical one.
- **A "collect/label a small in-domain validation set" step may need to become an explicit product task**, not an implicit assumption, since it's the only way to get honest MVP accuracy numbers (§8.4).

## Implications for Architecture

- **Resolve the mono-vs-stereo input question first** — it determines whether a diarization component is even needed, which affects most of the pipeline design downstream (§5.1).
- **Design the fusion layer as rule-based/late fusion with explicit confidence propagation**, not an end-to-end or early-fusion model, given no proprietary labeled dataset exists (§6.2, §6.3).
- **Budget for licensing review before committing to openSMILE/eGeMAPS or parselmouth** as core dependencies if the project's license posture needs to stay clean for any future non-portfolio use (§3.2).
- **Local/open-weight inference is the better-evidenced default** for privacy, cost-at-low-volume, and portfolio-value reasons — but STT and SER should be evaluated separately for local resource footprint, since Whisper-class models need meaningfully more compute than Wav2Vec2/HuBERT-class SER models (§10.2, §10.4).
- **Design chunking (if needed for long audio) around VAD-detected natural boundaries, not fixed windows**, and carry rolling context across chunk boundaries to protect timeline integrity (§11).
- **Calibration (temperature scaling) should be budgeted as a required MVP step, not an optional enhancement**, given how directly it serves the confidence/uncertainty-first-class principle at low implementation cost (§6.4).

## Sources / References

All sources are cited inline within each Finding section as `[source](URL)` links. Key primary sources by topic:

**SER & Acoustic:** [SUPERB benchmark (arXiv:2111.02735)](https://arxiv.org/abs/2111.02735) · [IEMOCAP→CEMO domain-gap study (arXiv:2110.14957)](https://arxiv.org/abs/2110.14957) · [SpeechBrain IEMOCAP model card](https://huggingface.co/speechbrain/emotion-recognition-wav2vec2-IEMOCAP) · [librosa docs](https://librosa.org/) · [openSMILE/eGeMAPS license](https://github.com/audeering/opensmile-python/blob/main/LICENSE)

**Voice Sentiment & Fusion & Evaluation:** [AlloSat call-center fusion study (arXiv:2310.04481)](https://arxiv.org/pdf/2310.04481) · [MulT (arXiv:1906.00295)](https://arxiv.org/abs/1906.00295) · [Tensor Fusion Network](https://aclanthology.org/D17-1115/) · [Temperature scaling calibration (Guo et al. 2017)](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf) · [Conformal prediction (arXiv:2107.07511)](https://arxiv.org/abs/2107.07511) · [Cross-corpus SER study (arXiv:2207.02104)](https://arxiv.org/abs/2207.02104)

**STT & Diarization:** [Open ASR Leaderboard](https://huggingface.co/blog/open-asr-leaderboard) · [Whisper license](https://github.com/openai/whisper/blob/main/LICENSE) · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) · [Turkish Whisper WER (MDPI, peer-reviewed)](https://www.mdpi.com/2079-9292/13/21/4227) · [pyannote.audio benchmarks](https://www.pyannote.ai/benchmark) · [Twilio dual-channel default](https://www.twilio.com/en-us/changelog/dual-channel-voice-recordings-by-default)

**Datasets, Turkish, Deployment, Legal:** [CREMA-D license](https://github.com/CheyneyComputerScience/CREMA-D/blob/master/LICENSE.txt) · [IEMOCAP access terms](https://sail.usc.edu/iemocap/iemocap_release.htm) · [EmoBox (arXiv:2406.07162)](https://arxiv.org/abs/2406.07162) · [Hume AI API sunset notice](https://dev.hume.ai/docs/expression-measurement/faq) · [Voice re-identification risk study (arXiv:2606.07210)](https://arxiv.org/pdf/2606.07210) · [GDPR Article 9](https://gdpr-info.eu/art-9-gdpr/) · [KVKK special-category data](https://www.kvkk.gov.tr/Icerik/2051/Ozel-Nitelikli-Kisisel-Veriler)

*All legal/privacy content in this document (§12) is informational research, not legal advice.*
