# Whisper GPU Diagnostic Guide / Ghid Diagnostic GPU pentru Whisper

## English Version

### Overview

Whisper now includes enhanced GPU detection that provides detailed diagnostic information to help you understand exactly what's happening with GPU acceleration.

### What You'll See

#### ✅ GPU Working Correctly

```
[whisper] GPU detected: NVIDIA GeForce RTX 3080
[whisper] Will use CUDA acceleration for transcription
[whisper] Loading model 'large-v3' on CUDA (attempt 1/3)...
[whisper] Model 'large-v3' loaded successfully on CUDA.
```

**What this means:** Your GPU is detected and will be used for 10-20x faster transcription.

#### ⚠️ PyTorch Without CUDA Support

```
[whisper] CUDA not available in PyTorch - will use CPU (slower)
[whisper] For GPU support, install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**What this means:** You have a GPU, but PyTorch was installed without CUDA support (CPU-only version).

**How to fix:**
1. Uninstall current PyTorch: `pip uninstall torch`
2. Install PyTorch with CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu118`
3. Restart the application

#### ⚠️ CUDA Driver Issue

```
[whisper] CUDA available but no GPU devices found - will use CPU
```

**What this means:** PyTorch has CUDA support, but can't find your GPU. This usually means:
- CUDA drivers not installed
- CUDA drivers outdated
- GPU not properly detected by system

**How to fix:**
1. Install/update NVIDIA CUDA drivers: https://developer.nvidia.com/cuda-downloads
2. Check GPU is detected: `nvidia-smi` (should show your GPU)
3. Restart the application

#### ⚠️ GPU Detection Failed

```
[whisper] GPU detection failed (error message) - will use CPU
```

**What this means:** Something went wrong during GPU detection. The error message will tell you what.

### Automatic Fallback

If Whisper tries to use CUDA but encounters an error (like out of memory), it will automatically fall back to CPU:

```
[whisper] CUDA error loading model: CUDA out of memory
[whisper] Falling back to CPU...
[whisper] Loading model 'large-v3' on CPU (attempt 2/3)...
```

This ensures your processing continues even if GPU fails.

---

## Versiunea în Română 🇷🇴

### Prezentare Generală

Whisper include acum detecție îmbunătățită a GPU care oferă informații diagnostice detaliate pentru a te ajuta să înțelegi exact ce se întâmplă cu accelerarea GPU.

### Ce Vei Vedea

#### ✅ GPU Funcționează Corect

```
[whisper] GPU detectat: NVIDIA GeForce RTX 3080
[whisper] Va folosi accelerare CUDA pentru transcriere
[whisper] Se încarcă modelul 'large-v3' pe CUDA (încercare 1/3)...
[whisper] Modelul 'large-v3' a fost încărcat cu succes pe CUDA.
```

**Ce înseamnă:** GPU-ul tău este detectat și va fi folosit pentru transcriere de 10-20 ori mai rapidă.

#### ⚠️ PyTorch Fără Suport CUDA

```
[whisper] CUDA nu este disponibil în PyTorch - va folosi CPU (mai lent)
[whisper] Pentru suport GPU, instalează PyTorch cu CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118
```

**Ce înseamnă:** Ai GPU, dar PyTorch a fost instalat fără suport CUDA (versiune doar CPU).

**Cum să rezolvi:**
1. Dezinstalează PyTorch curent: `pip uninstall torch`
2. Instalează PyTorch cu CUDA: `pip install torch --index-url https://download.pytorch.org/whl/cu118`
3. Repornește aplicația

#### ⚠️ Problemă cu Driver-ul CUDA

```
[whisper] CUDA disponibil dar nu s-au găsit dispozitive GPU - va folosi CPU
```

**Ce înseamnă:** PyTorch are suport CUDA, dar nu poate găsi GPU-ul. De obicei înseamnă:
- Driver-ele CUDA nu sunt instalate
- Driver-ele CUDA sunt depășite
- GPU-ul nu este detectat corect de sistem

**Cum să rezolvi:**
1. Instalează/actualizează driver-ele NVIDIA CUDA: https://developer.nvidia.com/cuda-downloads
2. Verifică că GPU-ul este detectat: `nvidia-smi` (ar trebui să arate GPU-ul tău)
3. Repornește aplicația

#### ⚠️ Detecția GPU a Eșuat

```
[whisper] GPU detection failed (mesaj de eroare) - will use CPU
```

**Ce înseamnă:** Ceva a mers greșit în timpul detecției GPU. Mesajul de eroare îți va spune ce.

### Fallback Automat

Dacă Whisper încearcă să folosească CUDA dar întâmpină o eroare (cum ar fi memorie insuficientă), va trece automat la CPU:

```
[whisper] CUDA error loading model: CUDA out of memory
[whisper] Falling back to CPU...
[whisper] Loading model 'large-v3' on CPU (attempt 2/3)...
```

Acest lucru asigură că procesarea continuă chiar dacă GPU eșuează.

---

## Common Issues / Probleme Comune

### Issue: "CUDA not available in PyTorch"

**English:** You need PyTorch with CUDA support.
- Install: `pip install torch --index-url https://download.pytorch.org/whl/cu118`

**Română:** Ai nevoie de PyTorch cu suport CUDA.
- Instalează: `pip install torch --index-url https://download.pytorch.org/whl/cu118`

### Issue: "No GPU devices found"

**English:** CUDA drivers issue.
- Install NVIDIA CUDA drivers
- Check with: `nvidia-smi`

**Română:** Problemă cu driver-ele CUDA.
- Instalează driver-ele NVIDIA CUDA
- Verifică cu: `nvidia-smi`

### Issue: "CUDA out of memory"

**English:** GPU doesn't have enough memory for the model.
- Try a smaller Whisper model (medium, small, base)
- Automatic fallback to CPU will occur

**Română:** GPU-ul nu are suficientă memorie pentru model.
- Încearcă un model Whisper mai mic (medium, small, base)
- Va avea loc fallback automat la CPU

---

## Performance / Performanță

### With GPU / Cu GPU:
- **Transcription Speed / Viteză transcriere:** 10-20x faster / mai rapid
- **Model Loading / Încărcare model:** Instant / Instant
- **Power Usage / Consum energie:** Higher / Mai mare

### With CPU / Cu CPU:
- **Transcription Speed / Viteză transcriere:** Baseline / De bază
- **Model Loading / Încărcare model:** Slower / Mai lent
- **Power Usage / Consum energie:** Lower / Mai mic

---

## Verification / Verificare

### Check GPU is Being Used / Verifică că GPU este folosit

Look for this in logs / Caută în log-uri:
```
[whisper] GPU detected: [GPU name]
[whisper] Will use CUDA acceleration
```

### Check Processing Speed / Verifică viteza de procesare

With GPU, a 5-minute video should transcribe in ~30 seconds.
Cu GPU, un video de 5 minute ar trebui transcris în ~30 secunde.

With CPU, the same video might take 10 minutes.
Cu CPU, același video ar putea dura 10 minute.

---

## Support / Suport

If you continue seeing "No GPU detected" after following the guide:

1. Share the full Whisper log output
2. Run `nvidia-smi` and share output
3. Run `python -c "import torch; print(torch.cuda.is_available())"` and share output

Dacă continui să vezi "No GPU detected" după ce ai urmat ghidul:

1. Partajează output-ul complet din log-ul Whisper
2. Rulează `nvidia-smi` și partajează output-ul
3. Rulează `python -c "import torch; print(torch.cuda.is_available())"` și partajează output-ul
