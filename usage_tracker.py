import os
import sys
import json
import re
import glob
import urllib.parse
from datetime import datetime, timezone, timedelta

class UsageTracker:
    def __init__(self, storage_dir=None):
        if storage_dir is None:
            self.storage_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AIQuotaWidget")
        else:
            self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.file_path = os.path.join(self.storage_dir, "usage_history.json")
        self.data = self._load()

    def _load(self):
        default = {
            "events": [],
            "last_fractions": {},
            "last_spend_weekly_pct": 0.0,
            "last_spend_5h_pct": 0.0,
            "last_spend_time": None,
            "last_spend_project": None
        }
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    default.update(saved)
            except Exception:
                pass
        return default

    def _save(self):
        try:
            if len(self.data["events"]) > 3000:
                self.data["events"] = self.data["events"][-3000:]
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _extract_project_from_path(p_str):
        if not p_str:
            return "General"
        clean = urllib.parse.unquote(p_str).replace("\\\\", "/").replace("\\", "/")
        parts = [part.strip() for part in clean.split("/") if part.strip()]
        if not parts:
            return "General"
        
        last = parts[-1]
        if "." in last and len(parts) > 1:
            last = parts[-2]
            
        ignore_names = {
            "logs", ".system_generated", "brain", "scratch", "temp", "dist", "build", 
            "user_uploaded", ".gemini", "antigravity", "appdata", "windows", "local", 
            "roaming", "programs", "python", "python313", "site-packages", "hooks", "..."
        }
        if last.lower() in ignore_names:
            if len(parts) > 2:
                for alt in reversed(parts[:-1]):
                    if alt.lower() not in ignore_names and len(alt) > 1 and not alt.endswith(":"):
                        return alt
            return "General"
                
        return last if len(last) > 1 and not last.endswith(":") else "General"

    def detect_active_project(self):
        """Detecta automáticamente el nombre del proyecto o workspace activo en Antigravity."""
        try:
            user_profile = os.environ.get("USERPROFILE", "")
            brain_dir = os.path.join(user_profile, ".gemini", "antigravity", "brain")
            
            # 1. Buscar en los transcripts más recientes de Antigravity
            transcripts = glob.glob(os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript.jsonl"))
            if transcripts:
                transcripts.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                for t in transcripts[:3]:
                    try:
                        f_size = os.path.getsize(t)
                        with open(t, "r", encoding="utf-8", errors="ignore") as f:
                            sample_head = f.read(8192)
                            sample_tail = ""
                            if f_size > 8192:
                                f.seek(max(0, f_size - 16384))
                                sample_tail = f.read(16384)
                            sample = sample_tail + "\n" + sample_head
                            matches = re.findall(r'\"([a-zA-Z]:(?:\\\\|/)[^\"*?<>|\r\n]+)\"', sample)
                            for m in matches:
                                proj = self._extract_project_from_path(m)
                                if proj and proj != "General":
                                    return proj
                    except Exception:
                        continue

            # 2. Buscar en agyhub_summaries_proto.pb
            proto_path = os.path.join(user_profile, ".gemini", "antigravity", "agyhub_summaries_proto.pb")
            if os.path.exists(proto_path):
                with open(proto_path, "rb") as f:
                    proto_data = f.read()
                matches = re.findall(rb"file:///([a-zA-Z0-9%_/\\\-\.]+)", proto_data)
                if matches:
                    decoded = urllib.parse.unquote(matches[-1].decode("latin1", errors="ignore"))
                    proj = self._extract_project_from_path(decoded)
                    if proj and proj not in ["General", "AppData", "Windows"]:
                        return proj
        except Exception:
            pass
        return "General"

    def record_quota_update(self, current_groups):
        """Registra el consumo detectado tanto para el Cupo Semanal como para la Ventana de 5 Horas."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        current_project = self.detect_active_project()
        
        last_fractions = self.data.get("last_fractions", {})
        has_new_spend = False

        for group in current_groups:
            group_name = "Gemini" if "Gemini" in group.get("displayName", "") else "Claude/GPT"
            buckets = group.get("buckets", [])
            for b in buckets:
                b_id = b.get("bucketId", b.get("displayName", ""))
                disp = b.get("displayName", "")
                frac = float(b.get("remainingFraction", 1.0))
                
                prev_frac = last_fractions.get(b_id)
                last_fractions[b_id] = frac
                
                is_weekly = ("weekly" in b_id.lower() or "weekly" in disp.lower())
                is_5h = ("5h" in b_id.lower() or "5-hour" in disp.lower() or "five hour" in disp.lower())
                
                if prev_frac is not None and frac < prev_frac:
                    delta_frac = prev_frac - frac
                    delta_pct = round(delta_frac * 100, 2)
                    
                    if delta_pct >= 0.01:
                        bucket_type = "weekly" if is_weekly else ("5h" if is_5h else "other")
                        event = {
                            "timestamp": now_iso,
                            "group": group_name,
                            "bucket_id": b_id,
                            "bucket_type": bucket_type,
                            "delta_pct": delta_pct,
                            "project": current_project
                        }
                        self.data["events"].append(event)
                        if is_weekly:
                            self.data["last_spend_weekly_pct"] = delta_pct
                        elif is_5h:
                            self.data["last_spend_5h_pct"] = delta_pct
                            
                        self.data["last_spend_time"] = now_iso
                        self.data["last_spend_project"] = current_project
                        has_new_spend = True

        self.data["last_fractions"] = last_fractions
        self._save()
        return has_new_spend

    def get_statistics(self, filter_group=None, bucket_type="weekly"):
        """
        Calcula estadísticas agregadas para el tipo de cupo seleccionado ('weekly' o '5h').
        Por defecto 'weekly' para analizar el impacto real sobre el cupo semanal por proyecto.
        """
        now = datetime.now().astimezone()
        today_date = now.date()
        current_year = now.year
        current_month = now.month
        current_isoweek = now.isocalendar()[1]

        events = self.data.get("events", [])
        if filter_group:
            events = [e for e in events if e.get("group") == filter_group or filter_group in e.get("group", "")]

        # Filtrar por tipo de bucket ('weekly' vs '5h')
        # Si un evento viejo no tenía bucket_type, asociarlo por su bucket_id
        filtered_events = []
        for e in events:
            btype = e.get("bucket_type")
            if not btype:
                bid = e.get("bucket_id", "").lower()
                btype = "weekly" if "weekly" in bid else "5h"
            
            if btype == bucket_type:
                filtered_events.append(e)

        today_spend = 0.0
        week_spend = 0.0
        month_spend = 0.0
        projects_spend = {}
        last_spend = 0.0

        for e in filtered_events:
            try:
                e_dt = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
                pct = float(e.get("delta_pct", 0.0))
                proj = e.get("project", "General")
                last_spend = pct

                # Hoy
                if e_dt.date() == today_date:
                    today_spend += pct
                
                # Semana actual
                if e_dt.year == current_year and e_dt.isocalendar()[1] == current_isoweek:
                    week_spend += pct

                # Mes actual
                if e_dt.year == current_year and e_dt.month == current_month:
                    month_spend += pct
                    projects_spend[proj] = projects_spend.get(proj, 0.0) + pct
            except Exception:
                continue

        # Si aún no hay eventos semanales registrados pero hay de 5h, podemos estimar proporcionalmente
        if bucket_type == "weekly" and not filtered_events and events:
            # Fallback elegante mientras se registran las próximas consultas
            pass

        last_time_str = "Ninguno"
        last_spend_iso = self.data.get("last_spend_time")
        if last_spend_iso:
            try:
                l_dt = datetime.fromisoformat(last_spend_iso.replace("Z", "+00:00")).astimezone()
                diff_sec = int((now - l_dt).total_seconds())
                if diff_sec < 60:
                    last_time_str = "hace un momento"
                elif diff_sec < 3600:
                    last_time_str = f"hace {diff_sec // 60}m"
                elif diff_sec < 86400:
                    last_time_str = f"hace {diff_sec // 3600}h"
                else:
                    last_time_str = l_dt.strftime("%d/%m %H:%M")
            except Exception:
                last_time_str = "N/A"

        sorted_projects = sorted(
            [{"name": k, "spend_pct": round(v, 1)} for k, v in projects_spend.items()],
            key=lambda x: x["spend_pct"],
            reverse=True
        )

        key_last = "last_spend_weekly_pct" if bucket_type == "weekly" else "last_spend_5h_pct"
        recorded_last = self.data.get(key_last, last_spend)

        return {
            "bucket_type": bucket_type,
            "last_spend_pct": round(recorded_last, 1),
            "last_spend_time_str": last_time_str,
            "last_spend_project": self.data.get("last_spend_project", "General"),
            "today_spend_pct": round(today_spend, 1),
            "week_spend_pct": round(week_spend, 1),
            "month_spend_pct": round(month_spend, 1),
            "projects": sorted_projects,
            "current_project": self.detect_active_project()
        }

    def get_recent_history(self, filter_group=None, bucket_type="weekly", limit=5):
        """Devuelve las últimas consultas registradas con hora, proyecto y porcentaje de gasto."""
        now = datetime.now().astimezone()
        events = self.data.get("events", [])
        if filter_group:
            events = [e for e in events if e.get("group") == filter_group or filter_group in e.get("group", "")]

        filtered = []
        for e in events:
            btype = e.get("bucket_type")
            if not btype:
                bid = e.get("bucket_id", "").lower()
                btype = "weekly" if "weekly" in bid else "5h"
            if btype == bucket_type:
                filtered.append(e)

        results = []
        for e in reversed(filtered[-limit * 2:]):
            try:
                e_dt = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
                time_label = e_dt.strftime("%H:%M")
                pct = float(e.get("delta_pct", 0.0))
                proj = e.get("project", "General")
                tag = "sem" if bucket_type == "weekly" else "5h"
                results.append({
                    "time": time_label,
                    "project": proj,
                    "spend_pct": round(pct, 1),
                    "spend_str": f"-{round(pct, 1)}% {tag}"
                })
                if len(results) >= limit:
                    break
            except Exception:
                continue
        return results

    def calculate_burn_rate(self, remaining_fraction, reset_time_iso):
        """Calcula el ritmo de consumo respecto al tiempo restante de reseteo del cupo semanal."""
        if remaining_fraction is None or not reset_time_iso:
            return {"status": "normal", "text": "🟢 Ritmo normal"}
        try:
            now = datetime.now().astimezone()
            r_dt = datetime.fromisoformat(reset_time_iso.replace("Z", "+00:00")).astimezone()
            hours_left = max((r_dt - now).total_seconds() / 3600.0, 0.1)
            days_left = max(hours_left / 24.0, 0.1)

            rem_pct = remaining_fraction * 100.0
            daily_budget = rem_pct / days_left

            # Calcular gasto de las últimas 24 horas
            one_day_ago = now - timedelta(hours=24)
            spend_24h = 0.0
            for e in self.data.get("events", []):
                btype = e.get("bucket_type") or ("weekly" if "weekly" in e.get("bucket_id", "").lower() else "5h")
                if btype == "weekly":
                    try:
                        edt = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
                        if edt >= one_day_ago:
                            spend_24h += float(e.get("delta_pct", 0.0))
                    except Exception:
                        pass

            if spend_24h > 0:
                burn_per_hour = spend_24h / 24.0
                runway_hours = rem_pct / burn_per_hour if burn_per_hour > 0 else 999
            else:
                runway_hours = 999

            if runway_hours < hours_left and rem_pct < 30:
                return {
                    "status": "warning",
                    "text": f"⚡ Ritmo alto: ~{int(runway_hours)}h de cupo restante"
                }
            elif daily_budget > 0:
                return {
                    "status": "safe",
                    "text": f"🟢 Ritmo seguro: ~{round(daily_budget, 1)}%/día dispon."
                }
        except Exception:
            pass
        return {"status": "normal", "text": "🟢 Ritmo estable"}

    def export_to_csv(self, file_path=None):
        """Exporta todo el historial de eventos a un archivo CSV estructurado."""
        if file_path is None:
            desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
            file_path = os.path.join(desktop, f"Reporte_Consumo_AI_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")

        try:
            with open(file_path, "w", encoding="utf-8-sig") as f:
                f.write("Fecha,Hora,Modelo,Tipo_Cupo,Proyecto,Consumo_Pct\n")
                for e in self.data.get("events", []):
                    try:
                        edt = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).astimezone()
                        f_date = edt.strftime("%Y-%m-%d")
                        f_time = edt.strftime("%H:%M:%S")
                        grp = e.get("group", "Gemini")
                        btype = e.get("bucket_type", "weekly")
                        proj = e.get("project", "General")
                        pct = e.get("delta_pct", 0.0)
                        f.write(f'"{f_date}","{f_time}","{grp}","{btype}","{proj}",{pct}\n')
                    except Exception:
                        continue
            return file_path
        except Exception as ex:
            return None

    def generate_summary_text(self):
        """Genera un reporte textual formateado para copiar directamente al portapapeles."""
        stats_w = self.get_statistics(bucket_type="weekly")
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        lines = [
            "📊 REPORTE DE CONSUMO IA (Antigravity)",
            f"📅 Generado: {now_str}",
            "─" * 38,
            "📈 CONSUMO DEL CUPO SEMANAL:",
            f"  • Hoy:         -{stats_w['today_spend_pct']}%",
            f"  • Esta Semana: -{stats_w['week_spend_pct']}%",
            f"  • Este Mes:    -{stats_w['month_spend_pct']}%",
            "",
            "📁 DESGLOSE POR PROYECTO (Mes):"
        ]
        projects = stats_w.get("projects", [])
        if projects:
            for p in projects:
                lines.append(f"  • {p['name']}: -{p['spend_pct']}% del cupo semanal")
        else:
            lines.append("  • (Sin proyectos registrados este mes)")
            
        lines.append("─" * 38)
        lines.append(f"Proyecto activo: {stats_w.get('current_project', 'General')}")
        return "\n".join(lines)
