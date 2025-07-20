import socket
import threading

class TestIRCServer:
    def __init__(self, host='127.0.0.1', port=6667):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.running = True
        # Add fake users for testing
        self.channels = {
            '#general': [f'user{i}' for i in range(1, 31)],
            '#random': [f'randuser{i}' for i in range(1, 16)],
            '#help': [f'helper{i}' for i in range(1, 11)]
        }

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Test IRC server running on {self.host}:{self.port}")
        threading.Thread(target=self.accept_clients, daemon=True).start()
        try:
            while self.running:
                pass
        except KeyboardInterrupt:
            self.running = False
            self.server_socket.close()
            print("Server stopped.")

    def accept_clients(self):
        while self.running:
            client_sock, addr = self.server_socket.accept()
            print(f"Client connected from {addr}")
            self.clients.append(client_sock)
            threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()

    def handle_client(self, client_sock):
        nickname = None
        channel = None
        while self.running:
            try:
                data = client_sock.recv(2048).decode('utf-8', errors='ignore')
                for line in data.split('\r\n'):
                    if line:
                        print(f"Received: {line}")
                        if line.startswith('NICK'):
                            nickname = line.split()[1]
                            client_sock.send(f":server 001 {nickname} :Welcome to the Test IRC Server\r\n".encode('utf-8'))
                        elif line.startswith('USER'):
                            pass  # Ignore for simplicity
                        elif line.startswith('JOIN'):
                            channel = line.split()[1]
                            if channel not in self.channels:
                                self.channels[channel] = []
                            self.channels[channel].append(nickname)
                            client_sock.send(f":{nickname}!user@localhost JOIN {channel}\r\n".encode('utf-8'))
                            # Send NAMES reply
                            names = ' '.join(self.channels[channel])
                            client_sock.send(f":server 353 {nickname} = {channel} :{names}\r\n".encode('utf-8'))
                            client_sock.send(f":server 366 {nickname} {channel} :End of /NAMES list.\r\n".encode('utf-8'))
                        elif line.startswith('PRIVMSG'):
                            parts = line.split(' ', 2)
                            if len(parts) == 3:
                                target, msg = parts[1], parts[2][1:]
                                # If target is a channel, broadcast to all users in that channel
                                if target.startswith('#') and target in self.channels:
                                    for user_nick in self.channels[target]:
                                        for sock in self.clients:
                                            try:
                                                # Send to all clients in the channel
                                                sock.send(f":{nickname} {target} :{msg}\r\n".encode('utf-8'))
                                            except Exception:
                                                pass
                                else:
                                    # Private message, echo to sender only
                                    client_sock.send(f":{nickname} PRIVMSG {target} :{msg}\r\n".encode('utf-8'))
                        elif line.startswith('PING'):
                            client_sock.send(f"PONG {line.split()[1]}\r\n".encode('utf-8'))
                        elif line.startswith('LIST'):
                            # Send channel list
                            for ch in self.channels:
                                client_sock.send(f":server 322 {nickname} {ch} {len(self.channels[ch])} :Test channel\r\n".encode('utf-8'))
                            client_sock.send(f":server 323 {nickname} :End of /LIST\r\n".encode('utf-8'))
            except Exception as e:
                print(f"Client error: {e}")
                break
        client_sock.close()

if __name__ == "__main__":
    server = TestIRCServer()
    server.start()
