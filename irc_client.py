import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from tkinter import ttk
import os, json
import datetime



try:
    import winsound
except ImportError:
    winsound = None

class IRCClient:
    def __init__(self, server, port, nickname, channel, gui):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui = gui
        self.gui.client = self  # Reference to this client in the GUI
        self.log_file = os.path.join(os.path.dirname(__file__), "chat_log.txt")
        self.auto_reconnect = True  # New feature: auto-reconnect toggle
    def connect(self):
        try:
            self.sock.connect((self.server, self.port))
            self.sock.send(f"NICK {self.nickname}\r\n".encode('utf-8'))
            self.sock.send(f"USER {self.nickname} 0 * :{self.nickname}\r\n".encode('utf-8'))
            threading.Thread(target=self.listen, daemon=True).start()
        except Exception as e:
            self.gui.append_message(f"Connection error: {e}")

    def reconnect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connect()
            self.gui.append_message("Reconnected to server.")
        except Exception as e:
            self.gui.append_message(f"Reconnect error: {e}")

    def listen(self):
        last_line = None
        while True:
            try:
                resp = self.sock.recv(2048).decode('utf-8', errors='ignore')
                for line in resp.split('\r\n'):
                    if line:
                        # Do not post NAMES (user list) responses to chat
                        if (' 353 ' in line or ' 366 ' in line):
                            continue
                        # Only post to main chat if not a LIST response (322/323)
                        if not (' 322 ' in line or ' 323 ' in line):
                            # Filter out repeated lines
                            if line != last_line:
                                self.gui.append_message(line)
                                self._log_message(line)
                                last_line = line
                    if line.startswith('PING'):
                        self.sock.send(f"PONG {line.split()[1]}\r\n".encode('utf-8'))
            except Exception as e:
                self.gui.append_message(f"Disconnected: {e}")
                if self.auto_reconnect:
                    self.gui.append_message("Attempting auto-reconnect...")
                    threading.Thread(target=self.reconnect, daemon=True).start()
                break

    def _log_message(self, message):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception:
            pass

    def send_message(self, message):
        try:
            self.sock.send(f"PRIVMSG {self.channel} :{message}\r\n".encode('utf-8'))
        except Exception as e:
            self.gui.append_message(f"Send error: {e}")

class IRCGui:
    def __init__(self, root):
        self.root = root
        self.root.title("IRC Client")
        self.root.geometry("700x500")   
        # Theme and colors must be set before any widget uses them
        self.theme = "modern"
        self.theme_colors = {
            "modern": {
                "bg": "#2c2c2c",           # dark grey background
                "fg": "#eafcfa",           # light blue text
                "entry_bg": "#16213e",     # slightly lighter blue
                "entry_fg": "#00ffb0",     # green text in entry
                "tab_bg": "#0f3460",       # blue tab background
                "tab_fg": "#ffd700",       # yellow tab text
                "listbox_bg": "#16213e",   # blue listbox background
                "listbox_fg": "#00ffb0",   # green listbox text
                "button_bg": "#00a8cc",    # blue-green button
                "button_fg": "#ffd700",    # yellow button text
                "label_fg": "#ffd700",     # yellow label text
            }
        }
        

        self.settings_file = os.path.join(os.path.dirname(__file__), "client_settings.json")
        self.settings = {
            "nickname": "",
            "server": "",
            "port": 6667,
            "channel": ""
        }
        self._load_all_settings()

        # Menu setup before any frames/widgets
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)
        self.connection_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Connection", menu=self.connection_menu)
        self.connection_menu.add_command(label="Connect", command=self.setup_connection)
        self.connection_menu.add_command(label="Disconnect", command=self.disconnect)
        self.connection_menu.add_command(label="Reconnect", command=self.reconnect)  # New feature
        self.connection_menu.add_separator()
        self.connection_menu.add_command(label="Room Search", command=self.room_search)
        self.connection_menu.add_separator()
        self.connection_menu.add_command(label="Add Bookmark", command=self.add_bookmark)
        self.connection_menu.add_command(label="Select Bookmark", command=self.select_bookmark)
        self.connection_menu.add_separator()
        self.connection_menu.add_command(label="Exit", command=self.root.quit)
        # Theme menu
        self.theme_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Theme", menu=self.theme_menu)
        self.theme_menu.add_command(label="Modern", command=lambda: self.set_theme("modern"))
        # Settings top-level menu
        self.settings_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Settings", menu=self.settings_menu)
        self.settings_menu.add_command(label="Client Settings", command=self.edit_settings)

        self.frame = tk.Frame(root)
        self.frame.pack(fill=tk.BOTH, expand=True)
        # User listbox on the right
        self.user_listbox = tk.Listbox(self.frame, width=35, bg=self.theme_colors[self.theme]["listbox_bg"],
                                       fg=self.theme_colors[self.theme]["listbox_fg"])
        self.user_listbox.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,15), pady=15)
        self.user_listbox.bind('<Double-Button-1>', self._open_private_message)
        self.theme = "modern"
        self.tabs = ttk.Notebook(self.frame)
        self.tabs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Add main tab for general messages
        self.main_tab = tk.Frame(self.tabs, bg=self.theme_colors[self.theme]["tab_bg"])
        self.tabs.add(self.main_tab, text="main")
        self.main_text = scrolledtext.ScrolledText(self.main_tab, state='disabled', width=60, height=20,
                                                  bg=self.theme_colors[self.theme]["tab_bg"],
                                                  fg=self.theme_colors[self.theme]["tab_fg"],
                                                  insertbackground=self.theme_colors[self.theme]["tab_fg"])
        self.main_text.pack(fill=tk.BOTH, expand=False)
        self.entry = tk.Entry(root, width=80)
        self.entry.pack(padx=0, pady=(0,10))
        self.entry.bind('<Return>', self.send_message)
        self.entry.config(state='disabled')  # Start disabled until connected
        self.client = None
        self.users = set()
        
        self.bookmarks = []
        self.last_connection = None
        

        # Add right-click context menu for main chat
        self.chat_menu = tk.Menu(self.root, tearoff=0)
        self.chat_menu.add_command(label="Copy Message", command=self.copy_selected_message)
        self.main_text.bind("<Button-3>", self.show_chat_menu)

        # Add right-click context menu for user list
        
        self.user_menu = tk.Menu(self.root, tearoff=0)
        
        self.user_menu.add_command(label="Whois", command=self.whois_selected_user)
        self.user_listbox.bind("<Button-3>", self.show_user_menu)

        

        self.tab_histories = {}  # <-- Add this line to initialize tab_histories
        self.auto_update_interval = 10000  # 10 seconds
        self._auto_update_user_list()      # Start auto-update loop
    def _auto_update_user_list(self):
        # Periodically request user list for current channel
        if self.client and self.client.channel:
            try:
                self.client.sock.send(f"NAMES {self.client.channel}\r\n".encode('utf-8'))
            except Exception:
                pass
        self.root.after(self.auto_update_interval, self._auto_update_user_list)

    def _load_all_settings(self):
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.bookmarks = data.get("bookmarks", [])
                    self.last_connection = data.get("last_connection", None)
                    self.settings.update(data.get("settings", {}))
                    # Always start with modern theme
                    self.theme = "modern"
            except Exception as e:
                print(f"Settings load error: {e}")

    def _save_all_settings(self):
        
        data = {
            "settings": self.settings,
            "bookmarks": self.bookmarks,
            "last_connection": self.last_connection,
            "theme": self.theme
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Settings save error: {e}")

    def _on_close(self):
        # Save everything before closing
        self._save_all_settings()
        self.root.destroy()
    def add_bookmark(self):
        win = tk.Toplevel(self.root)
        win.title("Add Bookmark")
        win.geometry("300x200")
        tk.Label(win, text="IRC server:").pack()
        server_entry = tk.Entry(win)
        server_entry.pack()
        tk.Label(win, text="Port (default 6667):").pack()
        port_entry = tk.Entry(win)
        port_entry.insert(0, "6667")
        port_entry.pack()
        tk.Label(win, text="Nickname:").pack()
        nick_entry = tk.Entry(win)
        nick_entry.pack()
        tk.Label(win, text="Channel (e.g. #test):").pack()
        chan_entry = tk.Entry(win)
        chan_entry.pack()

        def save():
            server = server_entry.get().strip()
            port = port_entry.get().strip()
            nickname = nick_entry.get().strip()
            channel = chan_entry.get().strip()
            if not all([server, port, nickname, channel]):
                messagebox.showerror("Error", "All fields are required.", parent=win)
                return
            try:
                port = int(port)
            except ValueError:
                messagebox.showerror("Error", "Port must be a number.", parent=win)
                return
            self.bookmarks.append({
                "server": server,
                "port": port,
                "nickname": nickname,
                "channel": channel
            })
            self._save_all_settings()
            messagebox.showinfo("Bookmark Added", f"Added: {server}:{port} {nickname} {channel}", parent=win)
            win.destroy()

        tk.Button(win, text="Save", command=save).pack(pady=10)

    def select_bookmark(self):
        if not self.bookmarks:
            messagebox.showinfo("No Bookmarks", "No bookmarks available. Add one first.")
            return
        # Show a list of bookmarks to select
        options = [f"{b['server']}:{b['port']} {b['nickname']} {b['channel']}" for b in self.bookmarks]
        selected = simpledialog.askstring("Select Bookmark", f"Available bookmarks:\n" + '\n'.join(f"{i+1}. {opt}" for i, opt in enumerate(options)) + "\nEnter number to connect:", parent=self.root)
        try:
            idx = int(selected) - 1
            if 0 <= idx < len(self.bookmarks):
                b = self.bookmarks[idx]
                self.client = IRCClient(b["server"], b["port"], b["nickname"], b["channel"], self)
                self.append_message(f"Connecting to {b['server']} on {b['channel']} as {b['nickname']}...")
                self.client.connect()
                self.last_connection = (b["server"], b["port"], b["nickname"], b["channel"])
                self._save_all_settings()
            else:
                messagebox.showerror("Error", "Invalid selection.")
        except Exception:
            messagebox.showerror("Error", "Invalid input.")

    def room_search(self):
        if not self.client:
            messagebox.showinfo("Info", "Connect to a server first.")
            return
        # Only open one channel window at a time
        if hasattr(self, 'channel_win') and self.channel_win and tk.Toplevel.winfo_exists(self.channel_win):
            self.channel_win.lift()
            return
        self._show_channel_select_window([])

    def _show_channel_select_window(self, channels):
        # Save reference to window and listbox for later update
        self.channel_win = tk.Toplevel(self.root)
        self.channel_win.title("Select Channel to Join")
        self.channel_win.geometry("350x450")
        tk.Label(self.channel_win, text="Available Channels:").pack(pady=5)
        self.channel_listbox = tk.Listbox(self.channel_win, height=12)
        self.channel_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.loading_label = None
        if not channels:
            self.loading_label = tk.Label(self.channel_win, text="Press Refresh to load channels.", fg="blue")
            self.loading_label.pack(pady=5)
        else:
            for ch in channels:
                self.channel_listbox.insert(tk.END, ch)
        def join_selected():
            sel = self.channel_listbox.curselection()
            if sel:
                channel = self.channel_listbox.get(sel[0])
                self.client.channel = channel  # Set current channel for main chat
                self.client.sock.send(f"JOIN {channel}\r\n".encode('utf-8'))
                self.append_message(f"Joining channel {channel}...")
                self.entry.config(state='normal')  # Enable entry after joining channel
                self.channel_win.destroy()
        join_btn = tk.Button(self.channel_win, text="Join Channel", command=join_selected)
        join_btn.pack(pady=10)
        self.channel_listbox.bind('<Double-Button-1>', lambda e: join_selected())
        refresh_btn = tk.Button(self.channel_win, text="Refresh", command=self._refresh_channel_list)
        refresh_btn.pack(pady=5)

    def _refresh_channel_list(self):
        # Show loading label
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.config(text="Loading channels...", fg="blue")
        self.channel_listbox.delete(0, tk.END)
        # Remove any previous "No channels" label
        if hasattr(self, 'no_channels_label') and self.no_channels_label:
            self.no_channels_label.destroy()
            self.no_channels_label = None
        try:
            self.client.sock.send(b"LIST\r\n")
            threading.Thread(target=self._capture_list_response_window, daemon=True).start()
        except Exception as e:
            self.append_message(f"Error requesting channel list: {e}")

    def _capture_list_response_window(self):
        import time
        start = time.time()
        channels = set()
        while time.time() - start < 3:
            try:
                resp = self.client.sock.recv(4096).decode('utf-8', errors='ignore')
                for line in resp.split('\r\n'):
                    # Robustly parse IRC LIST response for channel names
                    if ' 322 ' in line or (line.startswith(':') and ' 322 ' in line):
                        parts = line.split()
                        for part in parts:
                            if part.startswith('#'):
                                channels.add(part)
                                break
                    if ' 323 ' in line:
                        break
            except Exception:
                break
        self.root.after(0, self._update_channel_select_window, sorted(channels))

    def _update_channel_select_window(self, channels):
        # Remove loading label if present
        if hasattr(self, 'loading_label') and self.loading_label:
            self.loading_label.destroy()
            self.loading_label = None
        # Check if channel_listbox still exists before updating
        if hasattr(self, 'channel_listbox') and self.channel_listbox.winfo_exists():
            self.channel_listbox.delete(0, tk.END)
            # Remove any previous "No channels" label
            if hasattr(self, 'no_channels_label') and self.no_channels_label:
                self.no_channels_label.destroy()
                self.no_channels_label = None
            if channels:
                for ch in channels:
                    self.channel_listbox.insert(tk.END, ch)
            else:
                self.no_channels_label = tk.Label(self.channel_win, text="No channels found or server did not respond.", fg="red")
                self.no_channels_label.pack(pady=5)
        # If the window was closed, do nothing
    def disconnect(self):
        if self.client and self.client.sock:
            try:
                self.client.sock.close()
                self.append_message("Disconnected from server.")
            except Exception as e:
                self.append_message(f"Error disconnecting: {e}")
            self.client = None
            # Disable entry after disconnect
            self.entry.config(state='disabled')

    def setup_connection(self):
        win = tk.Toplevel(self.root)
        win.title("Connect to IRC Server")
        win.geometry("300x220")
        tk.Label(win, text="IRC server:").pack()
        server_entry = tk.Entry(win)
        server_entry.pack()
        tk.Label(win, text="Port (default 6667):").pack()
        port_entry = tk.Entry(win)
        port_entry.insert(0, "6667")
        port_entry.pack()
        tk.Label(win, text="Nickname:").pack()
        nick_entry = tk.Entry(win)
        nick_entry.pack()
        tk.Label(win, text="Channel (optional):").pack()
        chan_entry = tk.Entry(win)
        chan_entry.pack()

        def connect():
            server = server_entry.get().strip()
            port = port_entry.get().strip()
            nickname = nick_entry.get().strip()
            channel = chan_entry.get().strip()
            if not all([server, port, nickname]):
                messagebox.showerror("Error", "Server, port, and nickname are required.", parent=win)
                return
            try:
                port = int(port)
            except ValueError:
                messagebox.showerror("Error", "Port must be a number.", parent=win)
                return
            self.client = IRCClient(server, port, nickname, channel if channel else None, self)
            self.append_message(f"Connecting to {server} as {nickname}...")
            self.client.connect()
            if channel:
                self.client.channel = channel
                self.client.sock.send(f"JOIN {channel}\r\n".encode('utf-8'))
                self.append_message(f"Joining channel {channel}...")
                self.entry.config(state='normal')  # Enable input after joining channel
            else:
                self.entry.config(state='disabled')
            self.last_connection = (server, port, nickname, channel)
            self._save_all_settings()
            win.destroy()
        connect_btn = tk.Button(win, text="Connect", command=connect)
        connect_btn.pack(fill=tk.X, padx=10, pady=10)

    def _open_private_message(self, event):
        selection = self.user_listbox.curselection()
        if not selection:
            return
        user = self.user_listbox.get(selection[0])
        # Check if tab already exists
        for tab_id in self.tabs.tabs():
            if self.tabs.tab(tab_id, "text") == user:
                self.tabs.select(tab_id)
                return
        # Create new tab for private message
        pm_tab = tk.Frame(self.tabs)
        self.tabs.add(pm_tab, text=user)
        pm_text = scrolledtext.ScrolledText(pm_tab, state='disabled', width=60, height=20)
        pm_text.pack(fill=tk.BOTH, expand=True)
        pm_entry = tk.Entry(pm_tab, width=80)
        pm_entry.pack(fill=tk.X, padx=10, pady=(0,10))
        # Load chat history if exists
        history_key = f"pm_{user}"
        if history_key in self.tab_histories:
            pm_text.config(state='normal')
            pm_text.insert(tk.END, self.tab_histories[history_key])
            pm_text.config(state='disabled')
        def send_pm(event=None):
            msg = pm_entry.get()
            if msg:
                self.client.sock.send(f"PRIVMSG {user} :{msg}\r\n".encode('utf-8'))
                timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
                pm_text.config(state='normal')
                pm_text.insert(tk.END, f"{timestamp} You -> {user}: {msg}\n")
                pm_text.yview(tk.END)
                pm_text.config(state='disabled')
                pm_entry.delete(0, tk.END)
                # Save history
                self.tab_histories[history_key] = pm_text.get('1.0', tk.END)
        pm_entry.bind('<Return>', send_pm)
        send_btn = tk.Button(pm_tab, text="Send", command=send_pm)
        send_btn.pack(padx=10, pady=(0,10))

        def undock():
            # Remove tab and create a new window with the chat widgets
            self.tabs.forget(pm_tab)
            win = tk.Toplevel(self.root)
            win.title(f"Private chat with {user}")
            win.geometry("500x400")
            pm_text2 = scrolledtext.ScrolledText(win, state='disabled', width=60, height=20)
            pm_text2.pack(fill=tk.BOTH, expand=True)
            pm_entry2 = tk.Entry(win, width=80)
            pm_entry2.pack(fill=tk.X, padx=10, pady=(0,10))
            def send_pm2(event=None):
                msg = pm_entry2.get()
                if msg:
                    # Send only to the selected user, not to the main channel
                    self.client.sock.send(f"PRIVMSG {user} :{msg}\r\n".encode('utf-8'))
                    pm_text2.config(state='normal')
                    pm_text2.insert(tk.END, f"You -> {user}: {msg}\n")
                    pm_text2.yview(tk.END)
                    pm_text2.config(state='disabled')
                    pm_entry2.delete(0, tk.END)
            pm_entry2.bind('<Return>', send_pm2)
            send_btn2 = tk.Button(win, text="Send", command=send_pm2)
            send_btn2.pack(padx=10, pady=(0,10))
            # Load chat history if exists
            if history_key in self.tab_histories:
                pm_text2.config(state='normal')
                pm_text2.insert(tk.END, self.tab_histories[history_key])
                pm_text2.config(state='disabled')
            else:
                pm_text2.config(state='normal')
                pm_text2.insert(tk.END, pm_text.get('1.0', tk.END))
                pm_text2.config(state='disabled')
        undock_btn = tk.Button(pm_tab, text="Undock", command=undock)
        undock_btn.pack(padx=10, pady=(0,10))

    def _open_channel_tab(self, channel):
        # Check if tab already exists
        for tab_id in self.tabs.tabs():
            if self.tabs.tab(tab_id, "text") == channel:
                self.tabs.select(tab_id)
                return
        # Remove all channel tabs before opening the new one
        for tab_id in self.tabs.tabs():
            if self.tabs.tab(tab_id, "text").startswith("#"):
                self.tabs.forget(tab_id)
        # Create new tab for channel
        chan_tab = tk.Frame(self.tabs, bg=self.theme_colors[self.theme]["tab_bg"])
        self.tabs.add(chan_tab, text=channel)
        # Always add a ScrolledText chat view to the channel tab
        chan_text = scrolledtext.ScrolledText(chan_tab, state='disabled', width=60, height=20,
                                              bg=self.theme_colors[self.theme]["tab_bg"],
                                              fg=self.theme_colors[self.theme]["tab_fg"],
                                              insertbackground=self.theme_colors[self.theme]["tab_fg"])
        chan_text.pack(fill=tk.BOTH, expand=True)
        self.tabs.select(chan_tab)
        # Load chat history if exists
        history_key = f"chan_{channel}"
        if history_key in self.tab_histories:
            chan_text.config(state='normal')
            chan_text.insert(tk.END, self.tab_histories[history_key])
            chan_text.config(state='disabled')
        # Request updated user list for the channel after joining
        if self.client and channel:
            try:
                self.client.sock.send(f"NAMES {channel}\r\n".encode('utf-8'))
            except Exception:
                pass

    def append_message(self, message):
        # Route all messages to the correct tab
        routed = False
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        if 'PRIVMSG' in message:
            try:
                parts = message.split()
                # Handle both server and client PRIVMSG formats
                if len(parts) >= 4 and parts[1] == 'PRIVMSG':
                    sender = message.split('!')[0][1:]
                    target = parts[2]
                    msg_text = message.split(' :',1)[-1]
                elif len(parts) >= 3:
                    sender = message.split('!')[0][1:] if '!' in message else parts[0][1:] if parts[0].startswith(':') else parts[0]
                    target = parts[2]
                    msg_text = message.split(' :',1)[-1]
                else:
                    sender = None
                    target = None
                    msg_text = message
                # Private message to us
                if target == self.client.nickname:
                    for tab_id in self.tabs.tabs():
                        if self.tabs.tab(tab_id, "text") == sender:
                            tab_widget = self.tabs.nametowidget(tab_id)
                            for child in tab_widget.winfo_children():
                                if isinstance(child, scrolledtext.ScrolledText):
                                    child.config(state='normal')
                                    child.insert(tk.END, f"{timestamp} {sender} -> You: {msg_text}\n")
                                    child.yview(tk.END)
                                    child.config(state='disabled')
                                    # Save history
                                    history_key = f"pm_{sender}"
                                    self.tab_histories[history_key] = child.get('1.0', tk.END)
                                    routed = True
                                    # Sound notification
                                    if winsound:
                                        winsound.Beep(1000, 200)
                                    break
                            break
                # Channel message
                elif target and target.startswith("#"):
                    for tab_id in self.tabs.tabs():
                        if self.tabs.tab(tab_id, "text") == target:
                            tab_widget = self.tabs.nametowidget(tab_id)
                            for child in tab_widget.winfo_children():
                                if isinstance(child, scrolledtext.ScrolledText):
                                    child.config(state='normal')
                                    child.insert(tk.END, f"{timestamp} {sender}: {msg_text}\n")
                                    child.yview(tk.END)
                                    child.config(state='disabled')
                                    # Save history
                                    history_key = f"chan_{target}"
                                    self.tab_histories[history_key] = child.get('1.0', tk.END)
                                    routed = True
                                    break
                            break
            except Exception:
                pass
        # Fallback: show in main tab's ScrolledText if not routed
        if not routed:
            self.main_text.config(state='normal')
            self.main_text.insert(tk.END, f"{timestamp} {message}\n")
            self.main_text.yview(tk.END)
            self.main_text.config(state='disabled')
            # Save history
            self.tab_histories["main"] = self.main_text.get('1.0', tk.END)
        self._parse_user_list(message)

    def set_theme(self, theme):
        self.theme = theme
        self._save_all_settings()
        colors = self.theme_colors[theme]
        self.root.config(bg=colors["bg"])
        self.frame.config(bg=colors["bg"])
        self.user_listbox.config(bg=colors["listbox_bg"], fg=colors["listbox_fg"])
        self.entry.config(bg=colors["entry_bg"], fg=colors["entry_fg"], insertbackground=colors["entry_fg"])
        for tab_id in self.tabs.tabs():
            tab_widget = self.tabs.nametowidget(tab_id)
            tab_widget.config(bg=colors["tab_bg"])
            for child in tab_widget.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    child.config(bg=colors["tab_bg"], fg=colors["tab_fg"], insertbackground=colors["tab_fg"])
                elif isinstance(child, tk.Entry):
                    child.config(bg=colors["entry_bg"], fg=colors["entry_fg"], insertbackground=colors["entry_fg"])
                elif isinstance(child, tk.Button):
                    child.config(bg=colors["button_bg"], fg=colors["button_fg"])
                elif isinstance(child, tk.Label):
                    child.config(fg=colors["label_fg"])
        # Channel select window
        if hasattr(self, "channel_win") and self.channel_win and tk.Toplevel.winfo_exists(self.channel_win):
            self.channel_win.config(bg=colors["bg"])
            self.channel_listbox.config(bg=colors["listbox_bg"], fg=colors["listbox_fg"])
            for child in self.channel_win.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=colors["bg"], fg=colors["label_fg"])
                elif isinstance(child, tk.Button):
                    child.config(bg=colors["button_bg"], fg=colors["button_fg"])
    def _open_channel_tab(self, channel):
        # Check if tab already exists
        for tab_id in self.tabs.tabs():
            if self.tabs.tab(tab_id, "text") == channel:
                self.tabs.select(tab_id)
                return
        # Remove all channel tabs before opening the new one
        for tab_id in self.tabs.tabs():
            if self.tabs.tab(tab_id, "text").startswith("#"):
                self.tabs.forget(tab_id)
        # Create new tab for channel
        chan_tab = tk.Frame(self.tabs, bg=self.theme_colors[self.theme]["tab_bg"])
        self.tabs.add(chan_tab, text=channel)
        # Always add a ScrolledText chat view to the channel tab
        chan_text = scrolledtext.ScrolledText(chan_tab, state='disabled', width=60, height=20,
                                              bg=self.theme_colors[self.theme]["tab_bg"],
                                              fg=self.theme_colors[self.theme]["tab_fg"],
                                              insertbackground=self.theme_colors[self.theme]["tab_fg"])
        chan_text.pack(fill=tk.BOTH, expand=True)
        self.tabs.select(chan_tab)
        # Load chat history if exists
        history_key = f"chan_{channel}"
        if history_key in self.tab_histories:
            chan_text.config(state='normal')
            chan_text.insert(tk.END, self.tab_histories[history_key])
            chan_text.config(state='disabled')
        # Request updated user list for the channel after joining
        if self.client and channel:
            try:
                self.client.sock.send(f"NAMES {channel}\r\n".encode('utf-8'))
            except Exception:
                pass

    def _parse_user_list(self, message):
        # Accumulate all users from multiple 353 replies until 366 is received
        if not hasattr(self, '_pending_names_users'):
            self._pending_names_users = set()
            self._pending_names_channel = None
        if '353' in message and ':' in message:
            try:
                parts = message.split()
                channel = None
                for i, part in enumerate(parts):
                    if part == '=' and i+1 < len(parts):
                        channel = parts[i+1]
                        break
                    elif part.startswith('#'):
                        channel = part
                        break
                if channel and self.client and channel == self.client.channel:
                    users = message.split(':')[-1].strip().split()
                    if self._pending_names_channel != channel:
                        self._pending_names_users = set()
                        self._pending_names_channel = channel
                    self._pending_names_users.update(users)
            except Exception:
                pass
        elif '366' in message:
            # End of NAMES list, update user listbox
            if self._pending_names_channel == self.client.channel:
                self.users = set(self._pending_names_users)
                self._update_user_listbox()
            self._pending_names_users = set()
            self._pending_names_channel = None
        elif 'JOIN' in message:
            try:
                nick = message.split('!')[0][1:]
                if self.client and self.client.nickname in message or (self.client.channel and self.client.channel in message):
                    self.users.add(nick)
                    self._update_user_listbox()
            except Exception:
                pass
        elif 'PART' in message or 'QUIT' in message:
            try:
                nick = message.split('!')[0][1:]
                if nick in self.users:
                    self.users.remove(nick)
                    self._update_user_listbox()
            except Exception:
                pass

    def _update_user_listbox(self):
        self.user_listbox.delete(0, tk.END)
        for user in sorted(self.users):
            self.user_listbox.insert(tk.END, user)
        # Update user count label
        self.user_count_label.config(text=f"Users online: {len(self.users)}")

    def send_message(self, event=None):
        msg = self.entry.get()
        if msg and self.client:
            selected_tab = self.tabs.select()
            tab_text = self.tabs.tab(selected_tab, "text")
            if tab_text.startswith("#"):
                self.client.sock.send(f"PRIVMSG {tab_text} :{msg}\r\n".encode('utf-8'))
                self.entry.delete(0, tk.END)
            else:
                if self.client.channel:
                    self.client.send_message(msg)
                    self.entry.delete(0, tk.END)
                else:
                    messagebox.showerror("No Channel", "You have not joined a channel.")
        elif not self.client:
            messagebox.showerror("Not Connected", "You are not connected to a server.")

    def edit_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Client Settings")
        win.geometry("300x220")
        tk.Label(win, text="Nickname:").pack()
        nick_entry = tk.Entry(win)
        nick_entry.insert(0, self.settings.get("nickname", ""))
        nick_entry.pack()
        tk.Label(win, text="Default Server:").pack()
        server_entry = tk.Entry(win)
        server_entry.insert(0, self.settings.get("server", ""))
        server_entry.pack()
        tk.Label(win, text="Default Port:").pack()
        port_entry = tk.Entry(win)
        port_entry.insert(0, str(self.settings.get("port", 6667)))
        port_entry.pack()
        tk.Label(win, text="Default Channel:").pack()
        chan_entry = tk.Entry(win)
        chan_entry.insert(0, self.settings.get("channel", ""))
        chan_entry.pack()

        def save():
            self.settings["nickname"] = nick_entry.get().strip()
            self.settings["server"] = server_entry.get().strip()
            try:
                self.settings["port"] = int(port_entry.get().strip())
            except Exception:
                self.settings["port"] = 6667
            self.settings["channel"] = chan_entry.get().strip()
            self._save_all_settings()
            messagebox.showinfo("Saved", "Settings saved.", parent=win)
            win.destroy()

        tk.Button(win, text="Save", command=save).pack(pady=10)

    def reconnect(self):
        if self.client:
            self.client.reconnect()

    def clear_chat(self):
        self.main_text.config(state='normal')
        self.main_text.delete('1.0', tk.END)
        self.main_text.config(state='disabled')

    def show_chat_menu(self, event):
        try:
            self.main_text.tag_remove("sel", "1.0", tk.END)
            index = self.main_text.index(f"@{event.x},{event.y}")
            line_start = index.split('.')[0] + ".0"
            line_end = index.split('.')[0] + ".end"
            self.main_text.tag_add("sel", line_start, line_end)
            self.chat_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.chat_menu.grab_release()

    def copy_selected_message(self):
        try:
            selected = self.main_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except Exception:
            pass

    def show_user_menu(self, event):
        try:
            idx = self.user_listbox.nearest(event.y)
            self.user_listbox.selection_clear(0, tk.END)
            self.user_listbox.selection_set(idx)
            self.user_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.user_menu.grab_release()

    def whois_selected_user(self):
        selection = self.user_listbox.curselection()
        if selection and self.client:
            user = self.user_listbox.get(selection[0])
            try:
                self.client.sock.send(f"WHOIS {user}\r\n".encode('utf-8'))
                self.append_message(f"Requested WHOIS for {user}")
            except Exception as e:
                self.append_message(f"WHOIS error: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    gui = IRCGui(root)
    root.mainloop()
