"""
Format Download - Download de audio/video do YouTube
Versao: 3.3 Final
"""
import sys
import os
import re
import tempfile
import webbrowser
import shutil
import time
import threading
import socket
import logging
from flask import Flask, request, send_file, render_template_string
import yt_dlp

# Desabilitar logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('yt_dlp').setLevel(logging.ERROR)

HOST = '127.0.0.1'
PORT = 5000

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
if not FF_EXE:
    print("ERRO: ffmpeg.exe nao encontrado!")
    sys.exit(1)

last_heartbeat = time.time()
heartbeat_lock = threading.Lock()

def heartbeat_monitor():
    global last_heartbeat
    while True:
        time.sleep(10)
        with heartbeat_lock:
            if time.time() - last_heartbeat > 45:
                os._exit(0)

threading.Thread(target=heartbeat_monitor, daemon=True).start()

app = Flask(__name__)
app.logger.setLevel(logging.ERROR)

HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Format Download</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            font-family: 'Segoe UI', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 25px 45px rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo img { max-width: 120px; margin-bottom: 15px; }
        h1 { color: #e94560; font-size: 2.5rem; margin-bottom: 5px; }
        .subtitle { color: #a0a0b0; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; color: #e0e0e0; margin-bottom: 8px; font-weight: 600; }
        input, select {
            width: 100%;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            color: white;
            font-size: 1rem;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #e94560;
        }
        .quality-group { display: flex; gap: 10px; margin-bottom: 25px; }
        .quality-btn {
            flex: 1;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            cursor: pointer;
            color: white;
            text-align: center;
        }
        .quality-btn.active {
            background: #e94560;
            font-weight: bold;
        }
        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 10px;
            font-weight: bold;
            cursor: pointer;
            font-size: 1rem;
            text-transform: uppercase;
        }
        .btn-download {
            background: #e94560;
            color: white;
            margin-bottom: 15px;
        }
        .btn-download:disabled { background: #666; cursor: not-allowed; }
        .btn-exit {
            background: transparent;
            color: #a0a0b0;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .status.success { background: rgba(0, 255, 0, 0.1); color: #4ade80; }
        .status.error { background: rgba(255, 0, 0, 0.1); color: #f87171; }
        .status.info { background: rgba(233, 69, 96, 0.1); color: #e94560; }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(233, 69, 96, 0.2);
            border-top-color: #e94560;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .version { text-align: center; color: #666; font-size: 0.8rem; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <img src="/logo" alt="Logo" onerror="this.style.display='none'">
            <h1>Format Download</h1>
            <p class="subtitle">Download de Audio e Video do YouTube</p>
        </div>
        <form id="downloadForm">
            <div class="form-group">
                <label>URL do YouTube</label>
                <input type="text" id="url" placeholder="https://www.youtube.com/watch?v=..." required>
            </div>
            <div class="form-group">
                <label>Formato</label>
                <select id="format">
                    <option value="mp4">Video MP4</option>
                    <option value="mp3">Audio MP3</option>
                </select>
            </div>
            <div class="form-group">
                <label>Qualidade</label>
                <div class="quality-group" id="qualityGroup"></div>
            </div>
            <button type="submit" class="btn btn-download" id="downloadBtn">
                <span id="btnText">Iniciar Download</span>
            </button>
        </form>
        <div id="status" class="status"></div>
        <button class="btn btn-exit" onclick="exitApp()">Sair do Aplicativo</button>
        <div class="version">v3.3</div>
    </div>
    <script>
        var qualities = {
            mp4: [{value:'720',label:'720p'},{value:'1080',label:'1080p'},{value:'2160',label:'4K'}],
            mp3: [{value:'128',label:'128 kbps'},{value:'256',label:'256 kbps'},{value:'320',label:'320 kbps'}]
        };
        var currentQuality = '720';
        var formatSelect = document.getElementById('format');
        var qualityGroup = document.getElementById('qualityGroup');
        var downloadBtn = document.getElementById('downloadBtn');
        var btnText = document.getElementById('btnText');
        var statusDiv = document.getElementById('status');
        var urlInput = document.getElementById('url');

        function updateQualityButtons() {
            var format = formatSelect.value;
            var currentQualities = qualities[format];
            var html = '';
            for (var i = 0; i < currentQualities.length; i++) {
                html += '<button type="button" class="quality-btn' + (i === 0 ? ' active' : '') + '" data-quality="' + currentQualities[i].value + '">' + currentQualities[i].label + '</button>';
            }
            qualityGroup.innerHTML = html;
            currentQuality = currentQualities[0].value;
            
            var buttons = qualityGroup.querySelectorAll('.quality-btn');
            for (var j = 0; j < buttons.length; j++) {
                buttons[j].addEventListener('click', function() {
                    var allBtns = qualityGroup.querySelectorAll('.quality-btn');
                    for (var k = 0; k < allBtns.length; k++) {
                        allBtns[k].classList.remove('active');
                    }
                    this.classList.add('active');
                    currentQuality = this.getAttribute('data-quality');
                });
            }
        }

        formatSelect.addEventListener('change', updateQualityButtons);
        updateQualityButtons();

        setInterval(function() {
            fetch('/heartbeat').catch(function(){});
        }, 10000);

        function exitApp() {
            if (confirm('Tem certeza que deseja sair?')) {
                fetch('/shutdown').catch(function(){});
                window.close();
            }
        }

        window.addEventListener('beforeunload', function() {
            navigator.sendBeacon('/shutdown');
        });

        document.getElementById('downloadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            var url = urlInput.value.trim();
            
            if (!url) {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = 'Por favor, insira uma URL do YouTube';
                return;
            }

            var format = formatSelect.value;
            downloadBtn.disabled = true;
            btnText.innerHTML = '<span class="spinner"></span>Processando...';
            statusDiv.className = 'status info';
            statusDiv.innerHTML = '<span class="spinner"></span>Analisando video...';

            try {
                var formData = new FormData();
                formData.append('url', url);
                formData.append('format', format);
                formData.append('quality', currentQuality);

                var response = await fetch('/download', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    var errorText = await response.text();
                    throw new Error(errorText || 'Erro ao processar download');
                }

                var blob = await response.blob();
                var contentDisposition = response.headers.get('Content-Disposition');
                var filename = 'download.' + format;
                
                if (contentDisposition) {
                    var match = contentDisposition.match(/filename="(.+)"/);
                    if (match) filename = match[1];
                }

                var link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);

                statusDiv.className = 'status success';
                statusDiv.innerHTML = 'Download concluido com sucesso!';
                urlInput.value = '';

            } catch (err) {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = 'Erro: ' + err.message;
            } finally {
                downloadBtn.disabled = false;
                btnText.textContent = 'Iniciar Download';
            }
        });

        urlInput.focus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/logo')
def logo():
    logo_path = resource_path('logo_3.png')
    if os.path.isfile(logo_path):
        return send_file(logo_path, mimetype='image/png')
    return '', 404

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.form.get('url', '').strip()
        fmt = request.form.get('format', 'mp4').strip()
        quality = request.form.get('quality', '720').strip()

        if not url:
            return 'URL nao fornecida', 400
        if fmt not in ('mp3', 'mp4'):
            return 'Formato invalido', 400

        temp_dir = tempfile.mkdtemp(prefix='fd_')
        
        try:
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
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
                    }],
                })
            else:
                ydl_opts.update({
                    'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
                    'merge_output_format': 'mp4',
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            final_path = None
            for f in os.listdir(temp_dir):
                if f.endswith('.' + fmt):
                    final_path = os.path.join(temp_dir, f)
                    break
            
            if not final_path or not os.path.isfile(final_path):
                return 'Arquivo nao foi gerado', 500
            
            return send_file(
                final_path,
                as_attachment=True,
                download_name=os.path.basename(final_path),
                mimetype='audio/mpeg' if fmt == 'mp3' else 'video/mp4'
            )
            
        except Exception as e:
            error_msg = str(e)
            if 'Video unavailable' in error_msg:
                return 'Video nao disponivel', 400
            elif 'Private video' in error_msg:
                return 'Video privado', 400
            else:
                return 'Erro no download: ' + error_msg[:200], 500
        finally:
            def cleanup():
                time.sleep(1)
                shutil.rmtree(temp_dir, ignore_errors=True)
            threading.Thread(target=cleanup, daemon=True).start()
            
    except Exception as e:
        return 'Erro: ' + str(e)[:200], 500

@app.route('/heartbeat')
def heartbeat():
    global last_heartbeat
    with heartbeat_lock:
        last_heartbeat = time.time()
    return 'ok'

@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return 'ok'

if __name__ == '__main__':
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://' + HOST + ':' + str(PORT))
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)