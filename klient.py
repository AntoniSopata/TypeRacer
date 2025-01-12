import os
import sys
import socket
import time
import random
import threading
from queue import Queue
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextEdit, QListWidgetItem, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox, QHBoxLayout
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
from PyQt5.QtCore import Qt, QTimer, QRectF, QSize, pyqtSignal, QObject, QMetaObject, pyqtSlot, Q_ARG
from PyQt5.QtGui import QPainter, QTextCursor, QTextCharFormat, QColor, QFont


def read_port_from_config():
    try:
        with open("resources/config.conf", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0] == "port":
                    return int(parts[1])
    except FileNotFoundError:
        print("[CONFIG] Config file not found")
        return
    except ValueError:
        print("[CONFIG] Invalid port in config") 
        return


class NetworkClient:
    def __init__(self):
        self.connected = False

    def connect(self, ip, port):
        try:
            if self.connected:
                self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((ip, port))
            self.connected = True
            return True
        except Exception as e:
            print(f"[NETWORK] Connection error: {e}")
            self.connected = False
            self.socket.close()
            return False

    def send(self, message):
        if self.connected:
            self.socket.send(message.encode())

class LoginDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.ip_input = QLineEdit("")
        self.ip_input.setPlaceholderText("Server IP")
        self.nick_input = QLineEdit("")
        self.nick_input.setPlaceholderText("Nickname")
        
        self.connect_btn = QPushButton("Connect")
        
        layout.addWidget(self.ip_input)
        layout.addWidget(self.nick_input)
        layout.addWidget(self.connect_btn)
        
        self.setLayout(layout)

        self.connect_btn.setFocus()

class Client(QMainWindow):
    position_updated = pyqtSignal(str)
    game_started = pyqtSignal(str) 
    game_ended = pyqtSignal(str)
    room_updated = pyqtSignal(str)
    room_list_updated = pyqtSignal(str)
    button_states_updated = pyqtSignal()
    show_room_list_signal = pyqtSignal(str)
    login_error_signal = pyqtSignal(str)
    left_room_signal = pyqtSignal()
    admin_status_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.network = NetworkClient()
        self.player_id = None
        self.room_id = None
        self.is_admin = False
        self.game_finished = False
        self.server_thread = None
        
        self.text= ["Welcome to TypeRacer.$Enjoy!"] #do usuniecia
        self.text_lines = self.text[0].split("$")
        self.words_to_type = self.text_lines[0].split()
        self.current_word = self.words_to_type[0]
        self.current_word_index = 0
        self.current_line_index = 0
        self.word_count = 0
        self.accuracy = 0
        self.acc = 1
        self.a = 0
        self.start_time = None
        self.game_finished = False
        self.total_words = sum(len(line.split()) for line in self.text_lines)
        
        self.position_updated.connect(self.updatePositions)
        self.game_started.connect(self.startRace)
        self.game_ended.connect(self.showRanking)
        self.room_list_updated.connect(self.updateRoomListItems)
        self.button_states_updated.connect(self.updateButtonStates)
        self.show_room_list_signal.connect(self.showRoomList)
        self.login_error_signal.connect(self.handleLoginError)
        self.left_room_signal.connect(self.showLeftRoomMessage)
        self.admin_status_updated.connect(self.handleAdminStatusUpdate)

        self.showLoginScreen()


    def initUI(self):
        self.setWindowTitle(f'TypeRacer Client {self.player_id}')
        self.setGeometry(100, 100, 1280, 720)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        self.bg_widget = BackgroundWidget('resources/background/bg1.svg')
        self.bg_widget.setMinimumSize(1000, 500)
        layout.addWidget(self.bg_widget)

        self.current_line_label = QLabel(self.text_lines[0])
        self.current_line_label.setAlignment(Qt.AlignCenter)
        self.current_line_label.setWordWrap(True)
        self.current_line_label.setFont(QFont("Arial", 18))
        self.current_line_label.setStyleSheet("QLabel { padding: 10px; }")
        layout.addWidget(self.current_line_label)

        self.next_line_label = QLabel(self.text_lines[1])
        self.next_line_label.setAlignment(Qt.AlignCenter)
        self.next_line_label.setWordWrap(True)
        self.next_line_label.setFont(QFont("Arial", 18))
        self.next_line_label.setStyleSheet("QLabel { padding: 10px; color: gray; }")
        layout.addWidget(self.next_line_label)

        self.word_label = QLabel(self.current_word)
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setFont(QFont("Arial", 24, QFont.Bold))
        layout.addWidget(self.word_label)

        self.text_input = QLineEdit()
        self.text_input.setFixedHeight(50)
        self.text_input.setFixedWidth(400)
        self.text_input.setFont(QFont("Arial", 24))
        self.text_input.textChanged.connect(self.on_text_changed)
        self.text_input.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_input, 0, Qt.AlignCenter)

        self.speed_label = QLabel('WPM: 0, Time: 0s')
        self.speed_label.setFont(QFont("Arial", 24))

        self.current_wpm = 0
        self.elapsed_time = 0

        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time_label)
        self.time_timer.start(1000)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.speed_label, alignment=Qt.AlignLeft)
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            text = self.text_input.text()
            if text == self.current_word:
                self.word_count += 1
                if self.a == 0:
                    self.acc = 1
                else:
                    self.acc = 0
                self.accuracy += self.acc
                self.a = 0
                self.calculate_wpm()
                self.next_word()
                self.calculate_progress()
                self.text_input.clear()

    def calculate_progress(self):
        total_words_before = sum(len(line.split()) for line in self.text_lines[:self.current_line_index])
        words_completed = total_words_before + self.current_word_index
        
        progress = round(min(1.0, words_completed / self.total_words), 6)
        print(f"[CLIENT] Calculated progress: {progress}")
        
        if not self.game_finished:
            if hasattr(self, 'bg_widget'):
                self.bg_widget.updateCarPosition(self.player_id, progress)
            self.sendPosition(progress)

    def calculate_wpm(self):
        if self.start_time and self.word_count >= 1:
            elapsed_time = int(time.time() - self.start_time)
            minutes = elapsed_time / 60
            self.current_wpm = int(self.word_count / minutes) if minutes > 0 else 0
        else:
            self.current_wpm = 0

    @pyqtSlot()
    def update_time_label(self):
        if self.start_time and not self.game_finished:
            self.elapsed_time = int(time.time() - self.start_time)
        else:
            self.elapsed_time = 0
        self.speed_label.setText(f'WPM: {self.current_wpm}, Time: {self.elapsed_time}s')
        
    @pyqtSlot()
    def showLeftRoomMessage(self):
        QMessageBox.information(self, "Left Room", "You have successfully left the room.")

    def on_text_changed(self):
        text = self.text_input.text()
        if self.a == 0:
            self.acc = 1
            self.a = 1
        if text.endswith(' '):
            typed_word = text[:-1]
            if typed_word == self.current_word:
                self.word_count += 1
                self.a = 0
                self.accuracy += self.acc
                self.calculate_wpm()
                self.next_word()
                if not self.game_finished:
                    self.calculate_progress()
                self.text_input.clear()
            return

        if self.start_time is None and len(text) > 0:
            self.start_time = time.time()

        if self.current_word.startswith(text):
            self.text_input.setStyleSheet("color: green")
        else:
            self.text_input.setStyleSheet("color: red")
            self.acc = 0

    def next_word(self):
        if self.current_word_index + 1 >= len(self.words_to_type):
            self.move_to_next_line()
        else:
            self.current_word_index += 1
            self.current_word = self.words_to_type[self.current_word_index]
            self.word_label.setText(self.current_word)
        

    def move_to_next_line(self):
        self.current_line_index += 1
        if self.current_line_index < len(self.text_lines):
            self.current_line_label.setText(self.text_lines[self.current_line_index])
            
            if self.current_line_index + 1 < len(self.text_lines):
                self.next_line_label.setText(self.text_lines[self.current_line_index + 1])
            else:
                self.next_line_label.setText("")
                
            self.words_to_type = self.text_lines[self.current_line_index].split()
            self.current_word_index = 0
            self.current_word = self.words_to_type[0]
            self.word_label.setText(self.current_word)
        else:
            self.text_input.hide()
            self.word_label.hide()
            self.speed_label.hide()
            self.time_timer.stop()
            
            final_time = time.time() - self.start_time
            final_wpm = int(self.word_count / (final_time / 60))
            accuracy = int((self.accuracy / self.word_count) * 100)
            
            self.calculate_progress()
            self.game_finished = True
            
            self.current_line_label.setText("Game finished!")
            stats_text = (
                f"Time: {int(final_time)}s\n"
                f"Number of words: {self.word_count}\n"
                f"Average Speed: {final_wpm} WPM\n"
                f"Accuracy: {accuracy}%"
            )
            self.next_line_label.setText(stats_text)

    def restart_game(self):
        if hasattr(self, 'restart_button'):
            layout = self.centralWidget().layout()
            layout.removeWidget(self.restart_button)
            self.restart_button.deleteLater()
        self.network.send("START|")

    def showLoginScreen(self):
        self.login_dialog = LoginDialog()
        self.login_dialog.connect_btn.clicked.connect(self.handleLogin)
        self.login_dialog.show()

    def handleLogin(self):
        ip = self.login_dialog.ip_input.text().strip()
        nickname = self.login_dialog.nick_input.text().strip()
        
        print(f"[CLIENT] Attempting to connect to {ip} with nickname '{nickname}'")
        
        if not ip or not nickname:
            QMessageBox.warning(self, "Error", "Please enter both IP and nickname")
            return False

        port = read_port_from_config()   
        if self.network.connect(ip, port):
            print("[CLIENT] Connected to server")
            self.player_id = nickname
            self.network.send(f"LOGIN|{nickname}")
            print(f"[CLIENT] Sent LOGIN|{nickname}")
            
            if not self.server_thread or not self.server_thread.is_alive():
                self.server_thread = threading.Thread(target=self.handleServerCommunication)
                self.server_thread.daemon = True
                self.server_thread.start()
                print("[CLIENT] Started communication thread")
            
            self.login_dialog.hide()
            return True
                
        print("[CLIENT] Could not connect to server")
        QMessageBox.warning(self, "Error", "Could not connect to server")
        return False
            
    def updateRoomListItems(self, rooms_data):
        if hasattr(self, 'room_list'):
            self.room_list.clear()
            rooms = rooms_data.split("|")[1:]
            for room_info in rooms:
                room_info = room_info.strip()
                if not room_info:
                    continue

                try:
                    room_id_str, remainder = room_info.split(":", 1)
                    room_id_str = room_id_str.strip().replace("Room", "")
                    room_id = int(room_id_str)

                    remainder = remainder.strip()
                    parts = remainder.split(None, 1)
                    if not parts:
                        continue

                    count = int(parts[0])
                    names_str = ""
                    if len(parts) > 1:
                        names_str = parts[1]

                    if names_str.startswith("[") and names_str.endswith("]"):
                        player_list = [p.strip() for p in names_str[1:-1].split(",")]
                        for i, p in enumerate(player_list):
                            if p == self.player_id:
                                player_list[i] = f"[You] {p}"
                        names_str = "[" + ", ".join(player_list) + "]"

                    game_in_progress = "[In Progress]" if "gameStarted" in room_info.lower() else ""
                    display_str = f"Room {room_id}: {count} {game_in_progress}"
                    if names_str:
                        display_str += f" {names_str}"
                    room_item = QListWidgetItem(display_str)
                    if game_in_progress:
                        room_item.setFlags(room_item.flags() & ~Qt.ItemIsEnabled)
                    self.room_list.addItem(room_item)

                except ValueError as e:
                    print(f"[CLIENT] Error parsing room info '{room_info}': {e}")

            self.updateRoomList()

    def updateRoomList(self):
        if hasattr(self, 'start_button'):
            layout = self.room_window.layout()
            layout.removeWidget(self.start_button)
            self.start_button.deleteLater()
            del self.start_button

        if self.room_id is not None and self.is_admin:
            layout = self.room_window.layout()
            self.start_button = QPushButton("Start Game")
            self.start_button.clicked.connect(self.startGame)
            layout.addWidget(self.start_button)

    def showRoomList(self, rooms_data):
        if hasattr(self, 'room_window') and self.room_window.isVisible():
            self.room_window.close()
        
        self.room_window = QWidget()
        self.room_window.setWindowTitle("Game Rooms")
        layout = QVBoxLayout()
        
        self.room_list = QListWidget()
        self.updateRoomListItems(rooms_data)
        
        button_layout = QHBoxLayout()
        
        self.create_btn = QPushButton("Create Room")
        self.create_btn.clicked.connect(self.createRoom)
        
        self.join_btn = QPushButton("Join Room")
        self.join_btn.clicked.connect(self.joinRoom)
        
        self.leave_btn = QPushButton("Leave Room")
        self.leave_btn.clicked.connect(self.leaveRoom)
        self.leave_btn.setEnabled(False)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refreshRooms)
        
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.join_btn)
        button_layout.addWidget(self.leave_btn)
        button_layout.addWidget(refresh_btn)
        
        layout.addWidget(self.room_list)
        layout.addLayout(button_layout)
        
        self.room_window.setLayout(layout)
        self.room_window.show()
        
        self.updateButtonStates()
        self.updateRoomList()

    def updateButtonStates(self):
        if self.room_id is not None:
            self.create_btn.setEnabled(False)
            self.create_btn.setText("")
            self.join_btn.setEnabled(False)
            self.join_btn.setText("")
            self.leave_btn.setEnabled(True)
        else:
            self.create_btn.setEnabled(True)
            self.create_btn.setText("Create Room")
            self.join_btn.setEnabled(True)
            self.join_btn.setText("Join Room")
            self.leave_btn.setEnabled(False)

    def leaveRoom(self):
        if self.room_id is None:
            QMessageBox.warning(self, "Error", "You are not in any room!")
            return
        
        self.network.send(f"LEAVE|{self.player_id}|{self.room_id}")
        print(f"[CLIENT] Sent LEAVE request for room {self.room_id} by player {self.player_id}")
        
        self.room_id = None
        self.is_admin = False
        
        if hasattr(self, 'start_button'):
            layout = self.room_window.layout()
            layout.removeWidget(self.start_button)
            self.start_button.deleteLater()
            del self.start_button
        
        self.updateButtonStates()
        
        self.refreshRooms()

    def refreshRooms(self):
        if self.network.connected:
            self.updateRoomList()
            self.network.send("LIST|\n")
        else:
            QMessageBox.warning(self, "Error", "Not connected to the server.")

    def startGame(self):
        self.network.send("START|")
        self.start_button.setEnabled(False)

    @pyqtSlot(str)
    def startRace(self, data):
        print("[CLIENT] Starting race with data:", data)
        try:
            self.start_time = None
            self.word_count = 0
            self.accuracy = 0
            self.acc = 1
            self.a = 0
            self.current_line_index = 0
            self.words_to_type = self.text_lines[0].split()
            self.current_word_index = 0
            self.current_word = self.words_to_type[0]
            self.game_finished = False

            self.initUI()
            
            self.bg_widget.set_car_position(0)
            self.sendPosition(0.0)

            parts = data.split()
            bg_num = int(parts[0])
            print(f"[CLIENT] Background number: {bg_num}")
                
            bg_file = f'resources/background/bg{bg_num}.svg'
            print(f"[CLIENT] Setting background: {bg_file}")
            self.bg_widget.setBackground(bg_file)
            
            for player_data in parts[1:]:
                if '|' not in player_data:
                    continue
                    
                car_num, nickname = player_data.split('|')
                try:
                    car_num = int(car_num)
                    print(f"[CLIENT] Adding player: {nickname} with car: {car_num}")
                    self.bg_widget.addCar(nickname, car_num)
                    if nickname == self.player_id:
                        self.bg_widget.player_id = nickname
                except ValueError as e:
                    print(f"[CLIENT] Error processing player data: {e}")
                    continue
            
            self.show()
            if hasattr(self, 'room_window'):
                self.room_window.hide()
            
            self.text_input.setEnabled(True) 
            self.text_input.setFocus()
            
            print("[CLIENT] Game started successfully!\n")
            
        except Exception as e:
            print(f"[CLIENT] Error in startRace: {e}")


    def createRoom(self):
        if self.room_id is not None:
            QMessageBox.warning(self, "Error", "You are already in a room!")
            return
        self.network.send("CREATE|")


    def joinRoom(self):
        if self.room_id is not None:
            QMessageBox.warning(self, "Error", "You are already in a room!")
            return
                    
        selected = self.room_list.currentItem()
        if selected:
            room_id = int(selected.text().split(" ")[1][:-1])
            self.network.send(f"JOIN|{room_id}")
            

    def sendPosition(self, progress=None):
        """Send position update to server"""
        if progress is None:
            return
        if hasattr(self, 'bg_widget') and self.bg_widget.player_id:
            print(f"[CLIENT] Sending position update: {progress}")
            self.network.send(f"UPDATE|{progress}")
    
    def resetConnection(self):
        """Reset the network connection to allow for a new login attempt."""
        if self.network.connected and hasattr(self.network, 'socket'):
            try:
                self.network.socket.shutdown(socket.SHUT_RDWR)
                self.network.socket.close()
                print("[CLIENT] Socket shut down and closed.")
            except Exception as e:
                print(f"[CLIENT] Error closing socket: {e}")

        self.network = NetworkClient()
        self.network.connected = False
        print("[CLIENT] NetworkClient reset.")
        if self.server_thread and self.server_thread.is_alive():
            self.network.connected = False
            self.server_thread.join(timeout=1)
            if self.server_thread.is_alive():
                print("[CLIENT] Warning: Communication thread did not terminate properly.")
            else:
                print("[CLIENT] Communication thread terminated.")
        self.server_thread = None
        print("[CLIENT] Server communication thread reset.")

    @pyqtSlot(str)
    def handleLoginError(self, message):
        """Handle login errors on the main thread."""
        print(f"[CLIENT] Login error: {message}")
        self.resetConnection()
        QMessageBox.warning(self, "Error", message)
        self.login_dialog.nick_input.clear()
        self.login_dialog.nick_input.setPlaceholderText("Nickname")
        self.login_dialog.ip_input.setFocus()
        if not self.login_dialog.isVisible():
            self.login_dialog.show()

    @pyqtSlot(str)
    def handleServerCommunication(self):
        """Main server communication thread"""
        try:
            self.network.socket.settimeout(5)
            data = self.network.socket.recv(1024).decode()
            if not data:
                print("[NETWORK] Connection closed by server")
                self.network.connected = False
                return
            print(f"[NETWORK] Received: {data.strip()}")
            messages = data.strip().split('\n')

            for msg in messages:
                if '|' not in msg:
                    continue
                cmd, payload = msg.split('|', 1)
                if cmd == "ROOMS":
                    if not hasattr(self, 'room_window'):
                        self.login_dialog.hide()
                        self.show_room_list_signal.emit(msg)
                elif cmd == "LEFT":
                    print("[CLIENT] Successfully left the room.")
                    self.left_room_signal.emit()
                elif cmd == "CREATED":
                    self.room_id = int(payload)
                    self.is_admin = True
                    self.button_states_updated.emit()
                elif cmd == "JOIN":
                    self.room_id = int(payload)
                    self.is_admin = False
                    self.button_states_updated.emit()
                elif cmd == "START":
                    self.game_started.emit(payload)
                elif cmd == "END":
                    self.game_ended.emit(payload)
                elif cmd == "POS":
                    self.position_updated.emit(payload)
                elif cmd == "ROOM":
                    self.room_updated.emit(payload)
                    self.network.send("LIST|\n")
                elif cmd == "ADMIN":
                    self.is_admin = True
                    self.button_states_updated.emit()
                elif cmd == "ERROR":
                    if payload == "Nickname taken":
                        print("[CLIENT] Nickname taken error")
                        self.login_error_signal.emit("This nickname is already taken")
                    elif payload == "Game in progress":
                        QMessageBox.warning(self, "Error", "Cannot join the room: Game in progress.")
                    else:
                        print(f"[NETWORK] Error: {payload}")
                        QMessageBox.warning(self, "Error", payload)

            self.network.socket.settimeout(None)
            while self.network.connected:
                try:
                    data = self.network.socket.recv(1024).decode()
                    if not data:
                        print("[NETWORK] Connection closed by server")
                        break
                    print(f"[NETWORK] Received: {data.strip()}")
                    messages = data.strip().split('\n')
                    for msg in messages:
                        if '|' not in msg:
                            continue
                        cmd, payload = msg.split('|', 1)
                        if cmd == "ROOMS":
                            if not hasattr(self, 'room_window'):
                                self.login_dialog.hide()
                                self.show_room_list_signal.emit(msg)
                            else:
                                self.room_list_updated.emit(msg)
                        elif cmd == "LEFT":
                            print("[CLIENT] Successfully left the room.")
                            self.left_room_signal.emit()
                        elif cmd == "CREATED":
                            self.room_id = int(payload)
                            self.is_admin = True
                            self.button_states_updated.emit()
                        elif cmd == "JOIN":
                            self.room_id = int(payload)
                            self.is_admin = False
                            self.button_states_updated.emit()
                        elif cmd == "START":
                            self.game_started.emit(payload)
                        elif cmd == "END":
                            self.game_ended.emit(payload)
                        elif cmd == "POS":
                            self.position_updated.emit(payload)
                        elif cmd == "ROOM":
                            self.room_updated.emit(payload)
                            self.network.send("LIST|\n")
                        elif cmd == "TEXT":
                            self.text = payload.split("|")
                            self.text_lines = self.text[0].split("$")
                            self.words_to_type = self.text_lines[0].split()
                            self.current_word = self.words_to_type[0]
                            self.total_words = sum(len(line.split()) for line in self.text_lines)
                        elif cmd == "ADMIN":
                            self.admin_status_updated.emit()
                        elif cmd == "ERROR":
                            if payload == "Nickname taken":
                                print("[CLIENT] Nickname taken error")
                                self.login_error_signal.emit("This nickname is already taken")
                            elif payload == "Game in progress":
                                QMessageBox.warning(self, "Error", "Cannot join the room: Game in progress.")
                            else:
                                print(f"[NETWORK] Error: {payload}")
                                QMessageBox.warning(self, "Error", payload)
                    
                except Exception as e:
                    print(f"[NETWORK] Error in communication thread: {e}")
                    break

        except socket.timeout as e:
            print(f"[NETWORK] Connection timeout: {e}")
            self.network.connected = False
            self.network.socket.close()
            self.login_error_signal.emit("Connection timed out. Please check the server IP and try again.")
        except Exception as e:
            print(f"[NETWORK] Unexpected error: {e}")
            self.network.connected = False
            self.network.socket.close()
            self.login_error_signal.emit("An unexpected error occurred.")
        finally:
            if self.network:
                self.network.connected = False
            print("[NETWORK] Communication thread ended")


    @pyqtSlot(str)
    def updatePositions(self, data):
        if not hasattr(self, 'bg_widget'):
            return
        try:
            data = data.replace("POS|", "").strip()
            pairs = [p.strip() for p in data.split() if p.strip()]
            positions_debug = []
            
            for pair in pairs:
                try:
                    pos_str, nickname = pair.split('|')
                    position = float(pos_str)
                    self.bg_widget.updateCarPosition(nickname, position)
                    positions_debug.append(f"{nickname} position set to: {position:.6f}\n")
                except (ValueError, IndexError) as e:
                    print(f"[CLIENT] Error parsing position pair '{pair}': {e}")
                    continue
                    
            if positions_debug:
                print(f"[CLIENT] {' '.join(positions_debug)}")
                
        except Exception as e:
            print(f"[CLIENT] Error updating positions: {e}")

    def showRanking(self, data):
        self.game_finished = True
        """Handle game end and show rankings"""
        rankings = data.split("|")
        
        self.current_line_label.setText("Game finished!")
        existing_stats = self.next_line_label.text()
        ranking_text = "\n\nRankings:\n"
        for i, nickname in enumerate(rankings, 1):
            if nickname:
                ranking_text += f"{i}: {nickname}\n"

        self.next_line_label.setText(existing_stats + ranking_text)
        
        if self.is_admin:
            self.showRestartButton()
            
    def showRestartButton(self):
        self.restart_button = QPushButton("Play Again")
        self.restart_button.setFixedSize(200, 50)
        self.restart_button.setFont(QFont("Arial", 16))
        self.restart_button.clicked.connect(self.restart_game)
        layout = self.centralWidget().layout()
        layout.addWidget(self.restart_button, 0, Qt.AlignCenter)
        self.restart_button.setFocus()

    @pyqtSlot()
    def handleAdminStatusUpdate(self):
        self.is_admin = True
        self.updateButtonStates()
        self.updateRoomList() 

        if self.game_finished:
            self.next_line_label.setText(self.next_line_label.text() + "\n\nYou are now the admin.")
            self.showRestartButton()

class BackgroundWidget(QSvgWidget):
    def __init__(self, svg_file, parent=None):
        super().__init__(svg_file, parent)
        self.bg_renderer = self.renderer()
        self.cars = {}  
        self.car_renderers = {}
        self.player_id = None
    


        self.y_offsets_config = {
            'resources/background/bg1.svg': [0.87],
            'resources/background/bg2.svg': [0.67, 0.9],
            'resources/background/bg3.svg': [0.55, 0.73, 0.9],
            'resources/background/bg4.svg': [0.46, 0.62, 0.77, 0.93],
        }

        self.CAR_HEIGHT_RATIOS = {
            'resources/background/bg1.svg': 0.15,
            'resources/background/bg2.svg': 0.12,
            'resources/background/bg3.svg': 0.09,
            'resources/background/bg4.svg': 0.07,
        }

        self.current_y_offsets = []
        self.CAR_HEIGHT_RATIO = 0.9

    def setBackground(self, bg_file):
        self.load(bg_file)
        self.bg_renderer = self.renderer()
        self.update()
        
        self.current_y_offsets = self.y_offsets_config.get(bg_file, [0])
        self.CAR_HEIGHT_RATIO = self.CAR_HEIGHT_RATIOS.get(bg_file, 0.90)

    def addCar(self, nickname, car_number):
        y_offset_index = len(self.cars)
        if y_offset_index < len(self.current_y_offsets):
            y_offset = self.current_y_offsets[y_offset_index]
        else:
            y_offset = self.current_y_offsets[-1] + 60 * (y_offset_index - len(self.current_y_offsets) + 1)
        
        self.cars[nickname] = [car_number, 0.0, y_offset]
        self.car_renderers[nickname] = QSvgRenderer(f'resources/cars/{car_number}.svg')
        self.update()

    def updateCarPosition(self, nickname, position):
        if nickname in self.cars:
            self.cars[nickname][1] = position
            self.update()

    def set_car_position(self, position):
        if self.player_id and self.player_id in self.cars:
            self.updateCarPosition(self.player_id, position)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        painter.fillRect(self.rect(), Qt.white)
        
        bg_size = self.bg_renderer.defaultSize()
        
        widget_width = self.width()
        widget_height = self.height()
        bg_aspect = bg_size.width() / bg_size.height()


        target_width = widget_width
        target_height = widget_width / bg_aspect
        
        if target_height > widget_height:
            target_height = widget_height
            target_width = widget_height * bg_aspect
            
        x = (widget_width - target_width) / 2
        y = 0

        clip_rect = QRectF(x, y, target_width, target_height)
        painter.setClipRect(clip_rect)
        self.bg_renderer.render(painter, clip_rect)
        
        for nickname, (car_number, position, y_offset) in self.cars.items():
            if nickname in self.car_renderers:
                car_renderer = self.car_renderers[nickname]
                car_size = car_renderer.defaultSize()
                car_aspect = car_size.width() / car_size.height()
                
                car_height = target_height * self.CAR_HEIGHT_RATIO
                
                car_width = car_height * car_aspect
                
                usable_width = target_width - car_width
                car_x = x + (position * usable_width)
                
                car_y = y + target_height * y_offset - car_height / 2
                
                car_y = max(y, min(car_y, y + target_height - car_height))

                car_bounds = QRectF(car_x, car_y, car_width, car_height)
                car_renderer.render(painter, car_bounds)

        painter.end()

if __name__ == '__main__':
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    app = QApplication(sys.argv)
    client = Client()
    sys.exit(app.exec_())