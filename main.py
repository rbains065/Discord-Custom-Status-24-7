import os
import sys
import json
import time
import requests
import websocket
import threading
import datetime
from keep_alive import keep_alive

status = os.getenv("status", "online")
custom_status = os.getenv("custom_status", "")
usertoken = os.getenv("token")

if not usertoken:
    print("[ERROR] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

def get_user_info():
    try:
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        if response.status_code != 200:
            print("[ERROR] Your token might be invalid. Please check it again.")
            sys.exit()
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch user info: {e}")
        sys.exit()

userinfo = get_user_info()
username = userinfo["username"]
userid = userinfo["id"]

class DiscordOnliner:
    def __init__(self, token, status, custom_status):
        self.token = token
        self.status = status
        self.custom_status = custom_status
        self.ws = None
        self.heartbeat_interval = None
        self.running = False
        self.heartbeat_thread = None

    def send_heartbeat(self):
        while self.running:
            if self.ws and self.ws.connected:
                try:
                    self.ws.send(json.dumps({"op": 1, "d": None}))
                    time.sleep(self.heartbeat_interval / 1000)
                except Exception:
                    self.running = False
            else:
                self.running = False

    def connect(self):
        try:
            self.ws = websocket.WebSocket()
            self.ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")
            
            hello = json.loads(self.ws.recv())
            self.heartbeat_interval = hello["d"]["heartbeat_interval"]
            
            auth = {
                "op": 2,
                "d": {
                    "token": self.token,
                    "properties": {
                        "$os": "Windows 10",
                        "$browser": "Google Chrome",
                        "$device": "Windows",
                    },
                    "presence": {"status": self.status, "afk": False},
                },
            }
            self.ws.send(json.dumps(auth))

            cstatus = {
                "op": 3,
                "d": {
                    "since": 0,
                    "activities": [
                        {
                            "type": 4,
                            "state": self.custom_status,
                            "name": "Custom Status",
                            "id": "custom",
                        }
                    ],
                    "status": self.status,
                    "afk": False,
                },
            }
            self.ws.send(json.dumps(cstatus))
            
            self.running = True
            self.heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
            self.heartbeat_thread.start()
            print(f"[INFO] Connected and set status for {username}")
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        print(f"[INFO] Disconnected for {username}")

def is_active_time():
    now = datetime.datetime.now()
    # 2 mins online, 2 mins offline, repeated 24/7
    # (minute // 2) % 2 == 0:
    # 0-1 (Online), 2-3 (Offline), 4-5 (Online)...
    if (now.minute // 2) % 2 == 0:
        return True
    return False

def run_scheduler():
    onliner = DiscordOnliner(usertoken, status, custom_status)
    print(f"Logged in as {username} ({userid}).")
    
    while True:
        should_be_online = is_active_time()
        
        if should_be_online and not onliner.running:
            onliner.connect()
        elif not should_be_online and onliner.running:
            onliner.disconnect()
        
        # Check connection health if it should be running
        if should_be_online and onliner.running:
            if not (onliner.ws and onliner.ws.connected):
                print("[WARN] Connection lost, reconnecting...")
                onliner.disconnect()
                onliner.connect()
        
        time.sleep(30) # Check every 30 seconds

keep_alive()
run_scheduler()

