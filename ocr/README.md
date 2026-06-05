# Tesseract OCR (Windows)

Plate scanning on the **entry button** uses [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) via Python `pytesseract`.

## Install (one time)

1. Run the installer in this folder (double-click or PowerShell):

   ```powershell
   cd D:\IOT-Parking\ocr
   .\install_tesseract.ps1
   ```

   Or open **`tesseract-ocr-w64-setup-5.5.0.20241111.exe`** and use the wizard.

2. Default install path:

   ```text
   C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

3. In **`backend/.env`** (already in `.env.example`):

   ```env
   GATE_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

4. Restart the API:

   ```powershell
   cd D:\IOT-Parking\backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Test from the project root:

   ```powershell
   & "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
   ```

## Verify OCR with the API

With the API running, open the Wokwi **green entry** button or:

```powershell
cd backend
python devices/lane_workstation.py entry
```

You should see the camera window, then **OK &lt;plate&gt;** and the window closes when a plate is read.
