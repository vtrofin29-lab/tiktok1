# Ghid Presetări Setări (Settings Preset)

## Prezentare Generală

Funcția de Presetări Setări permite salvarea TUTUROR setărilor curente într-un fișier și restaurarea lor automată când deschizi aplicația. Economisește timp și asigură consistență între sesiuni.

## Funcții

### 💾 Salvează Preset
- Salvează toate setările curente într-un fișier preset
- Locație fișier: `~/.tiktok_preset.json` (în directorul tău home)
- Include TOATE setările din aplicație
- Format JSON ușor de editat

### 📂 Încarcă Preset
- Încarcă și aplică toate setările salvate
- Actualizează instant tot UI-ul
- Arată mesaj de confirmare
- Funcționează corect chiar dacă fișierul lipsește sau e corupt

### 🔄 Resetează la Valori Implicite
- Resetează TOATE setările la valorile lor implicite
- Cere confirmare înainte de a continua
- Util pentru a începe de la zero sau a repara probleme

### ⚡ Auto-Încărcare la Pornire
- Încarcă automat presetul când pornești aplicația
- Restaurare perfectă a sesiunii anterioare
- Operare silențioasă (scrie în log în loc de popup)

## Setări Salvate

Presetul salvează **TOATE** setările din aplicație:

### Căi Fișiere
- Calea video
- Calea voce
- Calea muzică
- Calea output

### Setări Video
- Oglindire video (on/off)
- Folosește rezoluție 4K (on/off)
- Crop personalizat activat (on/off)
- Procent crop sus
- Procent crop jos

### Setări Audio
- Voice gain (amplificare voce)
- Music gain (amplificare muzică)

### Setări Traducere & TTS
- Traducere activată (on/off)
- Limbă țintă
- Folosește înlocuire voce AI (on/off)
- Limbă TTS
- Selecție voce TTS
- Prag tăcere (ms)

### Setări Captions
- Cuvinte per caption
- Culoare text (RGBA)
- Culoare contur/border (RGBA)
- Lățime contur
- Offset Y caption

### Efecte Video (Toate 5)
- **Resilience (Sharpness)**: activat + intensitate
- **Vibrance (Saturation)**: activat + intensitate
- **HDR (Contrast)**: activat + intensitate
- **Brightness Boost**: activat + intensitate
- **Vintage (Film Grain)**: activat + intensitate

### Efecte Background
- Blur radius (raza blur)
- Background scale (scară fundal)
- Dim factor (factor întunericare)

## Cum se Folosește

### Salvează Setările

1. Configurează toate setările după preferințe:
   - Efecte video
   - Culori
   - Niveluri audio
   - Opțiuni traducere
   - Tot!

2. Apasă butonul **"💾 Save Preset"**

3. Vei vedea un mesaj de confirmare cu locația fișierului

4. Setările tale sunt acum salvate!

### Încarcă Setările

**Încărcare Manuală:**
1. Apasă butonul **"📂 Load Preset"**
2. Toate setările vor fi aplicate instant
3. Vei vedea un mesaj de confirmare

**Încărcare Automată:**
- Doar deschide aplicația!
- Dacă există un fișier preset, va fi încărcat automat
- Vei vedea un mesaj în log: "📂 Auto-loaded preset from: ..."

### Resetează la Valori Implicite

1. Apasă butonul **"🔄 Reset to Defaults"**
2. Confirmă că vrei să resetezi
3. Toate setările revin la valorile lor implicite originale

## Format Fișier Preset

Presetul este salvat ca JSON în `~/.tiktok_preset.json`:

```json
{
  "video_path": "",
  "voice_path": "",
  "music_path": "",
  "output_path": "final_tiktok.mp4",
  "mirror_video": false,
  "use_4k": true,
  "effect_sharpness": true,
  "effect_sharpness_intensity": 1.6,
  "caption_text_color": [255, 200, 100, 255],
  ...
}
```

## Utilizare Avansată

### Editare Manuală

Poți edita manual fișierul preset cu orice editor de text:

1. Găsește fișierul: `~/.tiktok_preset.json`
   - Windows: `C:\Users\NumeTau\.tiktok_preset.json`
   - Mac/Linux: `/home/username/.tiktok_preset.json`

2. Editează cu orice editor (Notepad, VS Code, etc.)

3. Salvează fișierul

4. Reîncarcă în aplicație cu butonul "📂 Load Preset"

### Partajare Preseturi

1. Localizează fișierul preset
2. Copiază-l pentru a-l partaja cu alții
3. Alții pot să-l pună în directorul lor home
4. Se va încărca automat la următoarea pornire

### Preseturi Multiple

Deși aplicația folosește un singur fișier preset, poți menține mai multe:

1. Salvează un preset
2. Redenumește `~/.tiktok_preset.json` în `preset_social_media.json`
3. Configurează alte setări
4. Salvează alt preset
5. Redenumește în `preset_profesional.json`
6. Când ai nevoie, copiază presetul dorit înapoi la `~/.tiktok_preset.json`

## Rezolvarea Problemelor

### Presetul Nu Se Încarcă

**Problemă**: Apăs "Load Preset" dar nu se întâmplă nimic

**Soluții**:
1. Verifică dacă fișierul preset există la `~/.tiktok_preset.json`
2. Verifică dacă fișierul este JSON valid
3. Verifică log-ul pentru mesaje de eroare
4. Încearcă "Reset to Defaults" și salvează un preset nou

### Setările Nu Se Salvează

**Problemă**: Am apăsat "Save Preset" dar setările nu persistă

**Soluții**:
1. Verifică permisiunile pe directorul home
2. Verifică dacă ai acces de scriere
3. Verifică log-ul pentru mesaje de eroare

### Auto-Load Nu Funcționează

**Problemă**: Presetul nu se încarcă automat la pornire

**Soluții**:
1. Verifică dacă fișierul preset există și are numele corect
2. Verifică log-ul pentru mesajul "Auto-loaded preset"
3. Încearcă încărcarea manuală cu "Load Preset"

## Sfaturi & Best Practices

### Când Să Salvezi

✅ **Momente bune pentru a salva**:
- După ce ai configurat setările ideale
- Înainte de a experimenta cu efecte noi
- După ce ai găsit o combinație bună
- Înainte de a actualiza aplicația

❌ **Nu salva**:
- Când ai setări de test
- Înainte de a testa rezultatele
- Cu căi temporare de fișiere (decât dacă le vrei)

### Organizare Preseturi

Creează un folder pentru preseturile tale:

```bash
mkdir ~/tiktok_presets
```

Numele descriptive pentru preseturi:
- `preset_social_media_luminos.json`
- `preset_profesional_curat.json`
- `preset_vintage_film.json`
- `preset_4k_calitate_inalta.json`

## Întrebări Frecvente

**Î: Unde este stocat fișierul preset?**
R: În directorul tău home: `~/.tiktok_preset.json`

**Î: Pot avea preseturi multiple?**
R: Aplicația folosește un preset activ, dar poți menține mai multe redenumindu-le.

**Î: Pot edita fișierul preset?**
R: Da! Este JSON standard. Doar menține structura.

**Î: Ce se întâmplă dacă stric fișierul preset?**
R: Pur și simplu șterge-l și salvează unul nou. Sau folosește "Reset to Defaults".

**Î: Pot partaja presetul?**
R: Da! Copiază fișierul `.tiktok_preset.json`.

**Î: Va funcționa presetul după actualizări?**
R: De obicei da. Setările noi vor folosi valori implicite dacă lipsesc.

## Sumar

Funcția Settings Preset economisește timp:

✅ Salvează TOATE setările într-un click
✅ Se încarcă automat la pornire
✅ Funcționează cu toate features
✅ Folosește JSON ușor de citit
✅ Ușor de backup și partajat
✅ Include funcție de resetare

Nu mai pierde timp reconfigurând setările!
