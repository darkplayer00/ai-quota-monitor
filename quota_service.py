import subprocess
import re
import urllib.request
import json
import ssl
from datetime import datetime, timezone, timedelta

CREATE_NO_WINDOW = 0x08000000

class QuotaService:
    def __init__(self):
        self._cached_data = None
        self._last_error = None
        self._csrf_token = None
        self._ports = []
        self._proc_id = None

    def _discover_language_server(self):
        # Filtra únicamente el proceso de language_server que tenga el token CSRF activo
        ps_script = (
            '$proc = Get-CimInstance Win32_Process -Filter "name like \'%language_server%\'" | '
            'Where-Object { $_.CommandLine -like "*--csrf_token*" } | Select-Object -First 1 ProcessId, CommandLine;'
            'if ($proc) {'
            '$ports = (Get-NetTCPConnection -State Listen -OwningProcess $proc.ProcessId -ErrorAction SilentlyContinue | Select-Object -Unique -ExpandProperty LocalPort) -join ",";'
            '[PSCustomObject]@{ ProcessId = $proc.ProcessId; CommandLine = $proc.CommandLine; Ports = $ports } | ConvertTo-Json -Compress'
            '}'
        )
        res = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script], 
            capture_output=True, 
            text=True,
            creationflags=CREATE_NO_WINDOW
        )
        out = res.stdout.strip()
        if not out:
            self._csrf_token = None
            self._ports = []
            return False, 'Antigravity / Language Server no detectado.'
        
        try:
            proc_info = json.loads(out)
            cmdline = proc_info.get('CommandLine', '')
            ports_str = proc_info.get('Ports', '')
            self._proc_id = proc_info.get('ProcessId')
            self._ports = [int(p.strip()) for p in ports_str.split(',') if p.strip().isdigit()]
        except Exception as e:
            self._csrf_token = None
            self._ports = []
            return False, f'Error al leer proceso: {e}'
        
        csrf_match = re.search(r'--csrf_token\s+([a-zA-Z0-9\-]+)', cmdline)
        if not csrf_match:
            self._csrf_token = None
            self._ports = []
            return False, 'Token CSRF no encontrado en el proceso.'
        self._csrf_token = csrf_match.group(1)
        return True, None

    def fetch_quota(self, force_rediscover=False):
        if force_rediscover or not self._csrf_token or not self._ports:
            ok, err = self._discover_language_server()
            if not ok:
                self._last_error = err
                return {'success': False, 'error': err, 'data': self._cached_data}

        ctx = ssl._create_unverified_context()
        for port in self._ports:
            for proto in ['http', 'https']:
                url = f'{proto}://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary'
                headers = {
                    'Content-Type': 'application/json',
                    'x-codeium-csrf-token': self._csrf_token,
                    'Connect-Protocol-Version': '1'
                }
                try:
                    req = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
                    with urllib.request.urlopen(req, context=ctx, timeout=2) as resp:
                        raw_data = json.loads(resp.read().decode('utf-8'))
                        res_data = raw_data.get('response', {})
                        self._cached_data = res_data
                        self._last_error = None
                        return {'success': True, 'data': res_data, 'error': None}
                except Exception:
                    continue

        if not force_rediscover:
            # Si falló la comunicación, intentar redescubrir (pudo haber reiniciado Antigravity en otro puerto)
            return self.fetch_quota(force_rediscover=True)
            
        self._csrf_token = None
        self._ports = []
        self._last_error = 'No se pudo comunicar con el Language Server.'
        return {'success': False, 'error': self._last_error, 'data': self._cached_data}

    @staticmethod
    def calculate_time_remaining(reset_time_iso):
        """Calcula el tiempo restante en formato de cuenta regresiva."""
        if not reset_time_iso:
            return "N/A"
        try:
            clean_iso = reset_time_iso.replace("Z", "+00:00")
            reset_dt = datetime.fromisoformat(clean_iso)
            now_utc = datetime.now(timezone.utc)
            diff = reset_dt - now_utc
            total_seconds = int(diff.total_seconds())

            if total_seconds <= 0:
                return "¡Reiniciado!"

            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0 or days > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m")
            if days == 0:
                parts.append(f"{seconds}s")

            return " ".join(parts)
        except Exception:
            return "N/A"

    @staticmethod
    def format_exact_reset_time(reset_time_iso):
        """Devuelve el día, fecha y hora exacta del reinicio en hora local."""
        if not reset_time_iso:
            return "N/A"
        try:
            clean_iso = reset_time_iso.replace("Z", "+00:00")
            reset_dt = datetime.fromisoformat(clean_iso).astimezone()
            now = datetime.now().astimezone()

            dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

            dia_sem = dias[reset_dt.weekday()]
            mes_nom = meses[reset_dt.month - 1]
            hora_corta = reset_dt.strftime("%H:%M")

            if reset_dt.date() == now.date():
                return f"Hoy {reset_dt.day:02d} {mes_nom}, {hora_corta} hrs"
            elif reset_dt.date() == (now + timedelta(days=1)).date():
                return f"Mañana {reset_dt.day:02d} {mes_nom}, {hora_corta} hrs"
            else:
                return f"{dia_sem} {reset_dt.day:02d} {mes_nom}, {hora_corta} hrs"
        except Exception:
            return "N/A"
