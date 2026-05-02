# Format_Download_Final.py
import sys
import os
import ctypes
import re
import tempfile
import webbrowser
import shutil
import time
import threading
from flask import Flask, request, send_file, render_template_string
import yt_dlp

# ========== AUTO ELEVAÇÃO (SOMENTE WINDOWS) ==========
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Relança o programa com privilégios de administrador."""
    if getattr(sys, 'frozen', False):
        # Estamos no executável gerado pelo PyInstaller
        script = sys.executable
    else:
        # Estamos rodando como script .py
        script = sys.argv[0]
    
    # Reexecuta usando ShellExecute com "runas"
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", script, " ".join(sys.argv[1:]), None, 1
    )
    sys.exit(0)

if not is_admin():
    print("Programa requer privilégios de administrador. Solicitando...")
    # Mostra uma mensagem amigável antes de pedir elevação
    ctypes.windll.user32.MessageBoxW(0, "Este programa precisa ser executado como administrador. Clique OK para continuar.", "Aviso", 0x40)
    run_as_admin()
# ====================================================

# ========== CONFIGURAÇÃO DO FFMPEG ==========
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def find_ffmpeg():
    local_exe = resource_path('ffmpeg.exe')
    if os.path.isfile(local_exe):
        return local_exe, os.path.dirname(local_exe)
    if shutil.which('ffmpeg'):
        return 'ffmpeg', None
    return None, None

FF_EXE, FF_DIR = find_ffmpeg()
if FF_EXE:
    print(f'[OK] ffmpeg encontrado: {FF_EXE}')
else:
    print('[ERRO] ffmpeg.exe não encontrado. Coloque na mesma pasta do programa.')

# ========== HEARTBEAT ==========
last_heartbeat = time.time()
heartbeat_lock = threading.Lock()

def heartbeat_monitor():
    global last_heartbeat
    while True:
        time.sleep(5)
        with heartbeat_lock:
            if time.time() - last_heartbeat > 15:
                print("Navegador fechado. Encerrando...")
                os._exit(0)

threading.Thread(target=heartbeat_monitor, daemon=True).start()

app = Flask(__name__)

# ========== HTML (mesmo com logo_3.png) ==========
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Format downloaD</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #F0F0F0;
            font-family: 'Segoe UI', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: #F0F0F0;
            border-radius: 16px;
            padding: 40px;
            max-width: 1000px;
            width: 100%;
            text-align: center;
        }
        h1 { color: #B90504; font-size: 2.5rem; margin-bottom: 4px; }
        .subtitle { color: #333; margin-bottom: 24px; }
        input, select {
            width: 100%;
            padding: 12px 16px;
            background: #2a2a2a;
            border: 1px solid #ccc;
            border-radius: 8px;
            color: white;
            margin-bottom: 20px;
        }
        .quality-selector { display: flex; gap: 8px; margin-bottom: 20px; }
        .quality-btn {
            flex: 1;
            padding: 10px;
            background: #2a2a2a;
            border: 1px solid #ccc;
            border-radius: 8px;
            cursor: pointer;
            color: white;
        }
        .quality-btn.active { background: #B90504; font-weight: bold; }
        .download-btn, .shutdown-btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 10px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
        }
        .download-btn { background: #B90504; color: white; }
        .shutdown-btn { background: #555; color: white; margin-top: 20px; }
        .status { margin-top: 16px; color: #333; }
        .error { color: #B90504; }
        .spinner {
            display: inline-block;
            width: 18px; height: 18px;
            border: 2px solid #ccc;
            border-top-color: #B90504;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        #popup {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.8);
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        .popup-content {
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .close-btn {
            float: right;
            font-size: 28px;
            cursor: pointer;
        }
    </style>
</head>
<body>
<div id="popup">
    <div class="popup-content">
        <span class="close-btn" onclick="fecharPopup()">&times;</span>
        <img src="/logo_3.png" alt="Logo" style="max-width: 100%;">
        <p>Carregando sistema...</p>
    </div>
</div>
<div class="container">
    <h1>Format downloaD</h1>
    <p class="subtitle">Download de áudio e vídeo do YouTube</p>
    <form id="downloadForm">
        <input type="text" id="url" placeholder="URL do YouTube" required>
        <select id="format">
            <option value="mp3">MP3 (Áudio)</option>
            <option value="mp4">MP4 (Vídeo)</option>
        </select>
        <div id="mp3Quality" style="display:none;">
            <label>Qualidade do áudio</label>
            <div class="quality-selector" id="mp3QualityBtns">
                <div class="quality-btn active" data-quality="128">128 kbps</div>
                <div class="quality-btn" data-quality="256">256 kbps</div>
                <div class="quality-btn" data-quality="320">320 kbps</div>
            </div>
        </div>
        <div id="mp4Quality">
            <label>Qualidade do vídeo</label>
            <div class="quality-selector" id="mp4QualityBtns">
                <div class="quality-btn active" data-quality="720">720p</div>
                <div class="quality-btn" data-quality="1080">1080p</div>
                <div class="quality-btn" data-quality="2160">4K</div>
            </div>
        </div>
        <button type="submit" class="download-btn">Baixar</button>
    </form>
    <div id="status" class="status"></div>
    <button id="shutdownBtn" class="shutdown-btn">Sair do App</button>
</div>
<script>
    const popup = document.getElementById('popup');
    setTimeout(() => { popup.style.display = 'flex'; setTimeout(() => popup.style.display = 'none', 2000); }, 1000);
    function fecharPopup() { popup.style.display = 'none'; }
    setInterval(() => fetch('/heartbeat'), 5000);
    window.addEventListener('beforeunload', () => navigator.sendBeacon('/shutdown'));

    const formatSelect = document.getElementById('format');
    const mp3Div = document.getElementById('mp3Quality');
    const mp4Div = document.getElementById('mp4Quality');
    function updateQuality() {
        const isMp3 = formatSelect.value === 'mp3';
        mp3Div.style.display = isMp3 ? 'block' : 'none';
        mp4Div.style.display = isMp3 ? 'none' : 'block';
    }
    formatSelect.addEventListener('change', updateQuality);
    updateQuality();

    document.querySelectorAll('.quality-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            this.parentElement.querySelectorAll('.quality-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    document.getElementById('downloadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('url').value.trim();
        if (!url) return;
        const format = formatSelect.value;
        const quality = format === 'mp3' ?
            document.querySelector('#mp3QualityBtns .active')?.dataset.quality :
            document.querySelector('#mp4QualityBtns .active')?.dataset.quality;
        if (!quality) { statusDiv.innerHTML = '<span class="error">Selecione uma qualidade</span>'; return; }
        const statusDiv = document.getElementById('status');
        const btn = document.querySelector('.download-btn');
        btn.disabled = true;
        statusDiv.innerHTML = '<span class="spinner"></span> Processando...';
        try {
            const formData = new FormData();
            formData.append('url', url);
            formData.append('format', format);
            formData.append('quality', quality);
            const response = await fetch('/download', { method: 'POST', body: formData });
            if (!response.ok) throw new Error(await response.text());
            const blob = await response.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = response.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || `download.${format}`;
            link.click();
            URL.revokeObjectURL(link.href);
            statusDiv.innerHTML = 'Download concluído!';
        } catch (err) { statusDiv.innerHTML = `<span class="error">${err.message}</span>`; }
        finally { btn.disabled = false; }
    });

    document.getElementById('shutdownBtn').addEventListener('click', async () => {
        if (confirm('Encerrar o aplicativo?')) { await fetch('/shutdown'); window.close(); }
    });
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/logo_3.png')
def logo():
    return send_file(resource_path('logo_3.png'), mimetype='image/png')

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()
    fmt = request.form.get('format')
    quality = request.form.get('quality')

    if not url:
        return 'URL não fornecida', 400
    if fmt not in ('mp3','mp4'):
        return 'Formato inválido', 400
    if fmt == 'mp3' and quality not in ('128','256','320'):
        return 'Qualidade inválida', 400
    if fmt == 'mp4' and quality not in ('720','1080','2160'):
        return 'Qualidade inválida', 400

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        # Extrai metadados
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = re.sub(r'[\\/*?:"<>|]', '', f"{info.get('uploader','desconhecido')} - {info.get('title','video')}")
        final_path = os.path.join(temp_dir, f"{title}.{fmt}")

        ydl_opts = {
            'outtmpl': final_path,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        if FF_DIR:
            ydl_opts['ffmpeg_location'] = FF_DIR

        if fmt == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }]
            })
        else:
            ydl_opts.update({
                'format': f'bestvideo[height<={quality}]+bestaudio/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.isfile(final_path):
            for f in os.listdir(temp_dir):
                if f.endswith(f'.{fmt}'):
                    final_path = os.path.join(temp_dir, f)
                    break
        if not os.path.isfile(final_path):
            raise RuntimeError("Arquivo final não gerado")

        return send_file(final_path, as_attachment=True,
                         download_name=os.path.basename(final_path),
                         mimetype='audio/mpeg' if fmt=='mp3' else 'video/mp4')
    except Exception as e:
        return f'Erro: {str(e)}', 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/heartbeat')
def heartbeat():
    global last_heartbeat
    with heartbeat_lock:
        last_heartbeat = time.time()
    return 'ok'

@app.route('/shutdown')
def shutdown():
    os._exit(0)

if __name__ == '__main__':
    print('Iniciando Format Download...')
    threading.Timer(1, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(debug=False, host='127.0.0.1', port=5000)