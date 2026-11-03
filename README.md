# Diario de Trading (local)

Diario para Oro, S&P 500 y Nasdaq 100 (CFD en MT5). Todo corre en tu PC: servidor en `127.0.0.1:8765`, base SQLite en `datos/`.

## Uso
- Ejecutable: `dist\DiarioTrading.exe` (doble clic; abre el navegador). Los datos quedan en `dist\datos\` junto al .exe. Cierra la ventana negra para detenerlo.
- Desde código: `.venv\Scripts\python run.py`
- Reconstruir el .exe: `powershell -File build.ps1`
- Pruebas: `.venv\Scripts\python -m pytest tests`

## Importar de MT5
Historial de cuenta → clic derecho → Informe → HTML. Súbelo en la pestaña Importar. Los duplicados se ignoran.

## Estructura
`app/db.py` esquema · `app/importer.py` MT5/CSV · `app/metrics.py` métricas · `app/server.py` API · `app/static/` interfaz · `docs/REQUERIMIENTOS.md`

## Instalar
Descarga de la pestaña **Releases**: DiarioTrading-Setup-X.Y.Z.exe (instalador, crea acceso directo y guarda los datos en %APPDATA%\DiarioTrading\datos) o el .zip portable (datos junto al .exe). Publicar una versión nueva: sube la versión en pp/__init__.py, crea el tag X.Y.Z y haz push del tag; GitHub Actions compila y publica el release.

