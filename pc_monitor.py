"""
PC Server Backend สำหรับ ESP32 SmartDesk Mini (Clean Version)
รองรับเฉพาะ API ที่จำเป็นเพื่อลดการกินทรัพยากร
"""
import os
import requests
import platform
import subprocess
from flask import Flask, jsonify
import psutil
import keyboard

app = Flask(__name__)

GITHUB_REPO = "facebook/react"
PROJECT_PATH = r"C:\Users\Antonius\Documents\Home-Server"
# ──────────────────────────────────────────
#  SYSTEM HELPERS (ดึงข้อมูลแยกส่วน)
# ──────────────────────────────────────────

def get_cpu_temp() -> int:
    """ ดึงอุณหภูมิ CPU แบบ Cross-Platform พร้อม Fallback """
    # 1. พยายามดึงผ่าน psutil (ทำงานได้ดีบน Linux)
    try:
        temps = psutil.sensors_temperatures()
        for key in ('coretemp', 'k10temp', 'cpu_thermal'):
            if key in temps and temps[key]:
                return int(temps[key][0].current)
    except Exception:
        pass

    # 2. พยายามดึงผ่าน WMI สำหรับ Windows (ต้องรันแอดมิน)
    if platform.system() == "Windows":
        try:
            import wmi
            # ท่าที่ 1: ดึงผ่าน OpenHardwareMonitor (แม่นที่สุด แนะนำให้เปิดโปรแกรมนี้ทิ้งไว้)
            w_ohm = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            sensors = w_ohm.Sensor(SensorType="Temperature", Identifier="/intelcpu/0/temperature/0")
            if sensors:
                return int(sensors[0].Value)
                
            # ท่าที่ 2: ดึงผ่าน Windows พื้นฐาน (อาจจะได้ค่าความร้อนเมนบอร์ดแทน)
            w_win = wmi.WMI(namespace="root\\wmi")
            zone = w_win.MSAcpi_ThermalZoneTemperature()[0]
            return int((zone.CurrentTemperature / 10.0) - 273.15) # แปลง deci-Kelvin เป็น Celsius
        except Exception:
            pass

    return 0 # ส่ง 0 ถ้าหาเซนเซอร์ไม่เจอจริงๆ


def get_gpu_info() -> dict:
    """ ดึงข้อมูล GPU ผ่าน nvidia-smi """
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split(",")
            return {
                "util": int(parts[0].strip()),
                "temp": int(parts[1].strip())
            }
    except FileNotFoundError:
        pass # ไม่มีการ์ดจอ Nvidia หรือหา Driver ไม่เจอ
    except Exception:
        pass
        
    return {"util": 0, "temp": 0}


# ──────────────────────────────────────────
#  API ROUTES
# ──────────────────────────────────────────

@app.route("/deep")
def deep_stats():
    # 1. ดึง CPU รวม
    cpu_util = int(psutil.cpu_percent(interval=0.1))
    
    try:
        freq = psutil.cpu_freq()
        cpu_freq = int(freq.current) if freq else 0
    except Exception:
        cpu_freq = 0

    # 2. ดึง RAM
    mem = psutil.virtual_memory()

    return jsonify({
        "cpu": {
            "util": cpu_util,
            "pkg_temp": get_cpu_temp(),
            "freq": cpu_freq
        },
        "gpu": get_gpu_info(),
        "memory": {
            "used_gb": round(mem.used / (1024**3), 1),
            "total_gb": round(mem.total / (1024**3), 1)
        }
    })

@app.route("/shutdown")
def shutdown():
    """ คำสั่งปิดคอมพิวเตอร์ """
    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            subprocess.Popen(["shutdown", "/s", "/t", "3"])
        elif sys_name in ["Linux", "Darwin"]:
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return jsonify({"status": "ok", "message": "Shutting down..."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/media/<cmd>")
def media_control(cmd):
    """ ส่งคำสั่ง Media Key ลึกระดับคีย์บอร์ดจำลอง """
    try:
        if cmd == "playpause":
            keyboard.send("play/pause media")
        elif cmd == "next":
            keyboard.send("next track")
        elif cmd == "prev":
            keyboard.send("previous track")
            
        print(f"[MEDIA] Executed: {cmd}") # สั่งปรินต์บอกในหน้าจอ CMD ด้วยจะได้รู้ว่ากดติด
        return jsonify({"status": "ok", "cmd": cmd})
        
    except Exception as e:
        print(f"[MEDIA ERROR] {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
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
    print(f" 🛠️  Endpoints  : /deep, /shutdown")
    print("═"*50 + "\n")
    
    # ปิด Debug เพื่อความลื่นไหลตอนรันจริง
    app.run(host="0.0.0.0", port=5000, debug=False)