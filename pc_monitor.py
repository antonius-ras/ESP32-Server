import os
import platform
import subprocess
from flask import Flask, jsonify
import psutil
import keyboard
import requests
import random       # <== เพิ่มตัวนี้แล้ว (แก้บั๊ก Discord / Dev)
import webbrowser
import asyncio
try:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
except ImportError:
    MediaManager = None

app = Flask(__name__)

# ══════════════════════════════════════════
#  ตั้งค่า DEV WORKSPACE 
# ══════════════════════════════════════════
GITHUB_REPO = "antonius-ras/ESP32-Server" 
PROJECT_PATH = r"C:\Users\Antonius\Documents\ESP32-Server" 
# ══════════════════════════════════════════
discord_state = {
    "channel": "General - Gaming",
    "muted": False,
    "deafened": False,
    "is_speaking": False
}

def get_cpu_temp() -> int:
    try:
        temps = psutil.sensors_temperatures()
        for key in ('coretemp', 'k10temp', 'cpu_thermal'):
            if key in temps and temps[key]:
                return int(temps[key][0].current)
    except Exception:
        pass

    if platform.system() == "Windows":
        try:
            import wmi
            w_ohm = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w_ohm.Sensor(SensorType="Temperature", Identifier="/intelcpu/0/temperature/0")
            if sensors:
                return int(sensors[0].Value)
                
            w_win = wmi.WMI(namespace="root\\wmi")
            zone = w_win.MSAcpi_ThermalZoneTemperature()[0]
            return int((zone.CurrentTemperature / 10.0) - 273.15) 
        except Exception:
            pass
    return 0

def get_gpu_info() -> dict:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split(",")
            return {"util": int(parts[0].strip()), "temp": int(parts[1].strip())}
    except Exception:
        pass
    return {"util": 0, "temp": 0}

# ──────────────────────────────────────────
#  API ROUTES
# ──────────────────────────────────────────

@app.route("/deep")
def deep_stats():
    cpu_util = int(psutil.cpu_percent(interval=0.1))
    try:
        freq = psutil.cpu_freq()
        cpu_freq = int(freq.current) if freq else 0
    except Exception:
        cpu_freq = 0
    mem = psutil.virtual_memory()

    return jsonify({
        "cpu": {"util": cpu_util, "pkg_temp": get_cpu_temp(), "freq": cpu_freq},
        "gpu": get_gpu_info(),
        "memory": {"used_gb": round(mem.used / (1024**3), 1), "total_gb": round(mem.total / (1024**3), 1)}
    })

@app.route("/dev")
def dev_dashboard():
    # --- 1. เช็กสถานะ CI/CD จาก GitHub Actions ---
    pipeline = {"build": "---", "test": "---", "deploy": "---"}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=1"
        resp = requests.get(url, timeout=2).json()
        
        if "workflow_runs" in resp and len(resp["workflow_runs"]) > 0:
            run = resp["workflow_runs"][0]
            status = run.get("status")
            conclusion = run.get("conclusion")
            
            if status != "completed":
                pipeline["build"] = "PASS"
                pipeline["test"] = "PENDING"
                pipeline["deploy"] = "PENDING"
            elif conclusion == "success":
                pipeline["build"] = "PASS"
                pipeline["test"] = "PASS"
                pipeline["deploy"] = "PASS"
            else:
                pipeline["build"] = "FAIL"
                pipeline["test"] = "FAIL"
                pipeline["deploy"] = "FAIL"
    except Exception:
        pipeline["build"] = "FAIL"

    # --- 2. ดึง Logs จากเครื่อง (Git หรือ Local Services) ---
    logs = []
    try:
        if os.path.exists(PROJECT_PATH):
            r = subprocess.run(["git", "log", "-n", "4", "--oneline"], cwd=PROJECT_PATH, capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout:
                for line in r.stdout.strip().split('\n'):
                    if line: logs.append(f"> {line[:40]}") 
        
        if not logs:
            logs.append("[INFO] Environment Check:")
            import socket
            def check_port(port):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    return "[PASS]" if s.connect_ex(('127.0.0.1', port)) == 0 else "[WARN]"

            logs.append(f"{check_port(3000)} React Web (Port 3000)")
            logs.append(f"{check_port(5000)} API Server (Port 5000)")
            logs.append(f"{check_port(3306)} Database (Port 3306)")
            
    except Exception:
        logs.append(f"[ERROR] Cannot fetch terminal logs")

    return jsonify({"pipeline": pipeline, "logs": logs[:4]})

@app.route("/shutdown")
def shutdown():
    sys_name = platform.system()
    try:
        if sys_name == "Windows": subprocess.Popen(["shutdown", "/s", "/t", "3"])
        elif sys_name in ["Linux", "Darwin"]: subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return jsonify({"status": "ok", "message": "Shutting down..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/media/<cmd>")
def media_control(cmd):
    try:
        if cmd == "playpause": keyboard.send("play/pause media")
        elif cmd == "next": keyboard.send("next track")
        elif cmd == "prev": keyboard.send("previous track")
        # --- เพิ่ม 2 บรรทัดนี้ ---
        elif cmd == "volup": keyboard.send("volume up")
        elif cmd == "voldown": keyboard.send("volume down")
        # ----------------------
        
        print(f"[MEDIA] Executed: {cmd}") 
        return jsonify({"status": "ok", "cmd": cmd})
    except Exception as e:
        print(f"[MEDIA ERROR] {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/macro/<cmd>")
def macro_run(cmd):
    try:
        # --- เปิดเว็บไซต์ ---
        if cmd == "google": webbrowser.open("https://google.com")
        elif cmd == "youtube": webbrowser.open("https://youtube.com")
        elif cmd == "facebook": webbrowser.open("https://facebook.com")
        
        # --- เปิดโปรแกรมในเครื่อง ---
        elif cmd == "steam": webbrowser.open("steam://open/main")
        elif cmd == "vscode": os.system("code")
        elif cmd == "cmd": os.system("start cmd")
        
        # --- ควบคุม Discord ---
        elif cmd == "discord":
            # พยายามเปิด Discord (เปลี่ยน path ได้ถ้าคอมคุณอยู่โฟลเดอร์อื่น)
            os.system(f"start {os.getenv('LOCALAPPDATA')}\\Discord\\Update.exe --processStart Discord.exe")
        elif cmd == "mute":
            keyboard.send("ctrl+shift+m")
            discord_state["muted"] = not discord_state["muted"]
        elif cmd == "deafen":
            keyboard.send("ctrl+shift+d")
            discord_state["deafened"] = not discord_state["deafened"]

        print(f"[MACRO] Executed: {cmd}")
        return jsonify({"status": "ok", "cmd": cmd})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/discord/status")
def discord_status():
    # จำลองวงแหวนสีเขียว (ถ้าไม่ได้ Mute ให้สุ่มสถานะกำลังพูด)
    if not discord_state["muted"] and not discord_state["deafened"]:
        discord_state["is_speaking"] = random.choice([True, True, False]) # สุ่มให้เขียวบ่อยกว่าดับ
    else:
        discord_state["is_speaking"] = False

    return jsonify(discord_state)

def get_now_playing():
    if not MediaManager:
        # ถ้าไม่มีไลบรารี จะส่งข้อความไปเตือนที่จอ ESP32
        return {"title": "Not Installed", "artist": "pip install winrt-Windows.Media.Control", "time": "00:00 / 00:00"}
    
    async def fetch_media():
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        if not current_session:
            return {"title": "No Media Playing", "artist": "Play some music...", "time": "00:00 / 00:00"}
        
        info = await current_session.try_get_media_properties_async()
        timeline = current_session.get_timeline_properties()
        
        title = info.title if info.title else "Unknown"
        artist = info.artist if info.artist else "Unknown Artist"
        
        # ฟังก์ชันแปลงเวลา
        def fmt_time(td):
            if not td: return "00:00"
            try:
                if hasattr(td, 'total_seconds'): secs = int(td.total_seconds())
                elif hasattr(td, 'Duration'): secs = int(td.Duration / 10000000)
                else: secs = int(td / 10000000)
                return f"{secs//60:02d}:{secs%60:02d}"
            except:
                return "00:00"
            
        pos = fmt_time(timeline.position) if timeline else "00:00"
        end = fmt_time(timeline.end_time) if timeline else "00:00"
        
        return {"title": title, "artist": artist, "time": f"{pos} / {end}"}
        
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(fetch_media())
        loop.close()
        return res
    except Exception as e:
        return {"title": "Error", "artist": str(e), "time": "00:00 / 00:00"}

@app.route("/media/nowplaying")
def now_playing():
    return jsonify(get_now_playing())

@app.route("/weather")
def get_weather():
    try:
        # พิกัด กรุงเทพฯ/นนทบุรี (เปลี่ยนเลข latitude/longitude ได้ถ้าต้องการ)
        lat, lon = 13.82, 100.45 
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code&timezone=Asia%2FBangkok"
        
        response = requests.get(url, timeout=3).json()
        current = response.get("current", {})
        
        temp = current.get("temperature_2m", 0)
        humidity = current.get("relative_humidity_2m", 0)
        code = current.get("weather_code", 0)
        
        # แปลงรหัสสภาพอากาศเป็นข้อความ
        condition = "Clear"
        if code in [1, 2, 3]: condition = "Cloudy"
        elif code in [45, 48]: condition = "Foggy"
        elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]: condition = "Rainy"
        elif code in [95, 96, 99]: condition = "Storm"
        
        return jsonify({
            "status": "ok",
            "temp": temp,
            "humidity": humidity,
            "condition": condition
        })
    except Exception as e:
        return jsonify({"status": "error", "temp": 0, "humidity": 0, "condition": "Offline"})

# ──────────────────────────────────────────
#  MAIN ENTRY POINT
# ──────────────────────────────────────────
if __name__ == "__main__":
    import socket
    ip = socket.gethostbyname(socket.gethostname())
    
    print("\n" + "═"*50)
    print(" 🚀 ESP32 SmartDesk Backend (Clean Version)")
    print("═"*50)
    print(f" 📡 IP Address : {ip}")
    print(f" 🔌 Port       : 5000")
    print(f" 🛠️  Endpoints  : /deep, /dev, /media, /shutdown")
    print("═"*50 + "\n")
    
    app.run(host="0.0.0.0", port=5000, debug=False)