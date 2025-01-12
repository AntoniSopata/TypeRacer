#include <iostream>
#include <vector>
#include <map>
#include <thread>
#include <poll.h>
#include <netinet/in.h>
#include <unistd.h>
#include <functional>
#include <algorithm>
#include <string.h>
#include <random>
#include <fstream>
#include <stdexcept>
#include <iterator>
#include <sstream>

#define MAX_PLAYERS_PER_ROOM 4


int readPortFromConfig() {
    std::ifstream config("resources/config.conf");
    if (!config.is_open()) {
        throw std::runtime_error("Could not open resources/config.conf");
    }

    std::string line;
    while (std::getline(config, line)) {
        std::istringstream iss(line);
        std::string key;
        int value;
        if (iss >> key >> value) {
            if (key == "port") {
                return value;
            }
        }
    }
    throw std::runtime_error("Port not found in config file");
}

bool sendAll(int sockfd, const std::string &message) {
    size_t totalSent = 0;
    size_t messageLength = message.length();
    const char* msgPtr = message.c_str();

    while (totalSent < messageLength) {
        ssize_t bytesSent = send(sockfd, msgPtr + totalSent, messageLength - totalSent, MSG_NOSIGNAL);
        if (bytesSent == -1) {
            return false;
        }
        totalSent += bytesSent;
    }
    return true;
}

class Player {
public:
    int socket;
    std::string nickname;
    int carNumber;
    double position;
    bool isAdmin;
    int id;

    Player(int sock, std::string nick) : 
        socket(sock),
        nickname(nick),
        carNumber(0),
        position(0.0),
        isAdmin(false),
        id(generateId()) {}

    bool operator==(const Player& other) {
        return socket == other.socket;
    }

private:
    static int generateId() {
        static int nextId = 0;
        return ++nextId;
    }
};

class Room {
public:
    int id;
    std::vector<Player*> players;
    bool gameStarted;
    int backgroundNumber;
    std::vector<int> usedCarNumbers;
    std::vector<std::string> finishOrder;

    Room(int roomId) : id(roomId), gameStarted(false), backgroundNumber(1) {}

    void addPlayer(Player* player) {
        player->isAdmin = players.empty();
        players.push_back(player);
        backgroundNumber = std::min(4, (int)players.size());
    }

    void removePlayer(Player* player) {
        auto it = std::find(players.begin(), players.end(), player);
        if (it != players.end()) {
            bool wasAdmin = player->isAdmin;
            players.erase(it);
            if (wasAdmin && !players.empty()) {
                players[0]->isAdmin = true;
                std::string adminMsg = "ADMIN|You are now the admin\n";
                sendAll(players[0]->socket, adminMsg);
            }
            std::string msg = "ROOM|" + std::to_string(id) + "|";
            for (auto p : players) {
                msg += p->nickname + " " + (p->isAdmin ? "1" : "0") + "|";
            }
            broadcast(msg, [](int){});
        }
    }

    void broadcast(const std::string& message, std::function<void(int)> disconnectCallback) {
        for (auto player : players) {
            if (!sendAll(player->socket, message)) {
                std::cerr << "[SERVER] Failed to send message to client: " << player->socket << std::endl;
                disconnectCallback(player->socket);
            }
        }
    }
};

class TypeRacerServer {
private:
    int serverSocket;
    std::map<int, Player*> players;
    std::map<int, Room*> rooms;
    int nextRoomId;
    std::mt19937 rng;

public:
    TypeRacerServer() : nextRoomId(0) {
        rng.seed(std::random_device()());
    }

    void start(int port) {
        serverSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (serverSocket < 0) {
            throw std::runtime_error("Failed to create socket");
        }

        const int one = 1;
        setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

        sockaddr_in serverAddr{};
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_addr.s_addr = INADDR_ANY;
        serverAddr.sin_port = htons(port);

        if (bind(serverSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) < 0) {
            throw std::runtime_error("Failed to bind");
        }

        if (listen(serverSocket, SOMAXCONN) < 0) {
            throw std::runtime_error("Failed to listen");
        }

        std::cout << "Server listening on port " << port << std::endl;

        pollfd serverPoll{};
        serverPoll.fd = serverSocket;
        serverPoll.events = POLLIN;

        while (true) {
            if (poll(&serverPoll, 1, -1) > 0) {
                int clientSocket = accept(serverSocket, nullptr, nullptr);
                if (clientSocket >= 0) {
                    std::thread(&TypeRacerServer::handleClient, this, clientSocket).detach();
                }
            }
        }
    }

private:
    void handleClient(int clientSocket) {
        char buffer[1024];
        while (true) {
            int bytes = recv(clientSocket, buffer, sizeof(buffer)-1, 0);
            if (bytes <= 0) {
                disconnectClient(clientSocket);
                break;
            }
            buffer[bytes] = '\0';
            
            std::string request(buffer);
            handleRequest(clientSocket, request);
        }
    }

    void handleRequest(int clientSocket, const std::string& request) {
        size_t sep = request.find('|');
        if (sep == std::string::npos) return;

        std::string cmd = request.substr(0, sep);
        std::string params = request.substr(sep + 1);

        std::cout << "[SERVER] Received command: " << cmd << " with params: " << params << std::endl;

        if (cmd == "LOGIN") {
            handleLogin(clientSocket, params);
        }
        else if (cmd == "CREATE") {
            handleCreateRoom(clientSocket);
        }
        else if (cmd == "JOIN") {
            try {
                int roomId = std::stoi(params);
                handleJoinRoom(clientSocket, roomId);
            } catch (const std::invalid_argument& e) {
                std::cerr << "[SERVER] Invalid room ID: " << params << std::endl;
                sendAll(clientSocket, "ERROR|Invalid room ID\n");
            }
        }
        else if (cmd == "START") {
            handleStartGame(clientSocket);
        }
        else if (cmd == "UPDATE") {
            try {
                double position = std::stod(params);
                handlePositionUpdate(clientSocket, position);
            } catch (const std::invalid_argument& e) {
                std::cerr << "[SERVER] Invalid position: " << params << std::endl;
                sendAll(clientSocket, "ERROR|Invalid position\n");
            }
        }
        else if (cmd == "LIST") {
            sendRoomList(clientSocket);
        }
        else if (cmd == "LEAVE") {
            handleLeaveRoom(clientSocket, params);
        }
    }

    void handleLeaveRoom(int clientSocket, const std::string& params) {
        size_t sep = params.find('|');
        if (sep == std::string::npos) return;

        std::string playerId = params.substr(0, sep);
        std::string roomIdStr = params.substr(sep + 1);

        try {
            int roomId = std::stoi(roomIdStr);

            if (rooms.count(roomId) == 0) {
                sendAll(clientSocket, "ERROR|Invalid room\n");
                return;
            }

            Room* room = rooms[roomId];
            Player* player = players[clientSocket];

            room->removePlayer(player);
            std::cout << "[SERVER] Player '" << player->nickname << "' left room " << roomId << std::endl;

            broadcastRoomState(room);

            if (room->players.empty()) {
                delete room;
                rooms.erase(roomId);
                broadcastRoomList();
            }
        } catch (const std::invalid_argument& e) {
            std::cerr << "[SERVER] Invalid room ID: " << roomIdStr << std::endl;
            sendAll(clientSocket, "ERROR|Invalid room ID\n");
        }
    }

    void handleLogin(int clientSocket, const std::string& nickname) {
        for (const auto& pair : players) {
            if (pair.second->nickname == nickname) {
                std::string errorMsg = "ERROR|Nickname taken\n";
                sendAll(clientSocket, errorMsg);
                std::cerr << "[SERVER] Nickname '" << nickname << "' is already taken. Disconnecting client." << std::endl;
                disconnectClient(clientSocket);
                return;
            }
        }

        players[clientSocket] = new Player(clientSocket, nickname);
        std::cout << "[SERVER] Player '" << nickname << "' connected to server" << std::endl;
        sendRoomList(clientSocket);
    }

    void handleCreateRoom(int clientSocket) {
        Room* room = new Room(nextRoomId++);
        room->addPlayer(players[clientSocket]);
        rooms[room->id] = room;

        std::string response = "CREATED|" + std::to_string(room->id) + "\n";

        if (!sendAll(clientSocket, response)) {
            std::cerr << "[SERVER] Failed to send CREATED response to clientSocket: " << clientSocket << std::endl;
            disconnectClient(clientSocket);
            return;
        }
        usleep(100000);
        broadcastRoomList();
    }


    void handleJoinRoom(int clientSocket, int roomId) {
        if (rooms.count(roomId) == 0) {
            sendAll(clientSocket, "ERROR|Invalid room\n");
            return;
        }

        Room* room = rooms[roomId];
        
        if (room->gameStarted) {
            sendAll(clientSocket, "ERROR|Game in progress\n");
            return;
        }

        if (room->players.size() >= MAX_PLAYERS_PER_ROOM) {
            sendAll(clientSocket, "ERROR|Room full\n");
            return;
        }

        room->addPlayer(players[clientSocket]);
        std::cout << "[SERVER] Player '" << players[clientSocket]->nickname
                << "' joined room " << roomId << std::endl;

        std::string response = "JOIN|" + std::to_string(room->id) + "\n";
        if (!sendAll(clientSocket, response)) {
            std::cerr << "[SERVER] Failed to send JOIN response to clientSocket: " << clientSocket << std::endl;
            disconnectClient(clientSocket);
            return;
        }

        broadcastRoomState(room);
    }


    void handleStartGame(int clientSocket) {
        Player* player = players[clientSocket];
        Room* room = findPlayerRoom(player);

        if (!room || !player->isAdmin) {
            std::cout << "Cannot start game - not admin or no room" << std::endl;
            return;
        }

        std::cout << "Starting game in room " << room->id << std::endl;

        room->gameStarted = true;
        assignRandomCars(room);
        broadcastGameStart(room);
    }

    void handlePositionUpdate(int clientSocket, double position) {
        Player* player = players[clientSocket];
        Room* room = findPlayerRoom(player);

        if (!room || !room->gameStarted) return;

        position = std::round(position * 1000000.0) / 1000000.0;
        player->position = position;
        broadcastPositions(room);
        if (position >= 1.0 && 
            std::find(room->finishOrder.begin(), room->finishOrder.end(), player->nickname) 
            == room->finishOrder.end()) {
            
            room->finishOrder.push_back(player->nickname);
            if (room->finishOrder.size() >= room->players.size()) {
                usleep(100000);
                broadcastGameEnd(room);
            }
        }
    }

    void sendRoomList(int clientSocket) {
        std::string msg = "ROOMS|";
        for (const auto& pair : rooms) {
            Room* room = pair.second;
            std::string names;
            for (auto player : room->players) {
                if (!names.empty()) names += ", ";
                names += player->nickname;
            }
            msg += "Room" + std::to_string(room->id) + ": " +
                std::to_string(room->players.size()) + " [" + names + "]|";
        }
        msg += "\n";
        if (!sendAll(clientSocket, msg)) {
            std::cerr << "[SERVER] Failed to send room list to client: " << clientSocket << std::endl;
            disconnectClient(clientSocket);
        }
    }

    Room* findPlayerRoom(Player* player) {
        for (auto& pair : rooms) {
            Room* room = pair.second;
            if (std::find(room->players.begin(), room->players.end(), player) != room->players.end()) {
                return room;
            }
        }
        return nullptr;
    }

    void assignRandomCars(Room* room) {
        room->usedCarNumbers.clear();
        std::uniform_int_distribution<> dist(1, 12);
        
        for (auto player : room->players) {
            int carNum;
            do {
                carNum = dist(rng);
            } while (std::find(room->usedCarNumbers.begin(), 
                            room->usedCarNumbers.end(), 
                            carNum) != room->usedCarNumbers.end());
            
            player->carNumber = carNum;
            room->usedCarNumbers.push_back(carNum);
        }
    }

    void broadcastRoomList() {
    for (const auto& pair : players) {
        sendRoomList(pair.first);
    }
    }

    void broadcastRoomState(Room* room) {
        std::string msg = "ROOM|" + std::to_string(room->id) + "|";
        for (auto player : room->players) {
            msg += player->nickname + " " +
                (player->isAdmin ? "1" : "0") + "|";
        }
        room->broadcast(msg, [this](int socket) { disconnectClient(socket); });
    }

    std::string readTextFromFile(int number) {
        std::string filePath = "resources/text/" + std::to_string(number) + ".txt";
        std::ifstream file(filePath);

        if (!file.is_open()) {
            std::cerr << "Failed to open text file: " << filePath << std::endl;
            throw std::runtime_error("Failed to open text file");
        }
        std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        file.close();
        return text;
    }

    void broadcastGameStart(Room* room) {
        int textNumber = std::uniform_int_distribution<>(1, 10)(rng);
        std::string text = readTextFromFile(textNumber);


        std::string textMsg = "TEXT|" + text + "\n";
        for (auto player : room->players) {
            send(player->socket, textMsg.c_str(), textMsg.length(), 0);
        }

        int background = 0;
        for (size_t i = 0; i < room->players.size(); i++) {
            background++;
        }
        std::string msg = "START|" + std::to_string(background);
        for (size_t i = 0; i < room->players.size(); i++) {
            msg += " " + std::to_string(room->players[i]->carNumber) + "|" + 
                room->players[i]->nickname;
        }
        
        msg += "\n";
        std::cout << "Broadcasting start: " << msg << std::endl;
        
        room->broadcast(msg, [this](int socket) { disconnectClient(socket); });
        
        std::cout.flush();
    }


    void broadcastPositions(Room* room) {
        std::string msg = "POS|";
        for (auto player : room->players) {
            msg += " " + std::to_string(player->position) + "|" + player->nickname;
        }
        msg += "\n"; 
        std::cout << "Broadcasting positions: " << msg << std::endl;
        room->broadcast(msg, [this](int socket) { disconnectClient(socket); });
    }

    void broadcastGameEnd(Room* room) {
        std::cout << "[SERVER] Game ended in room " << room->id << std::endl;
        std::cout << "[SERVER] Final rankings:" << std::endl;
        for(size_t i = 0; i < room->finishOrder.size(); i++) {
            std::cout << (i+1) << ". " << room->finishOrder[i] << std::endl;
        }

        std::string msg = "END|";
        for (const auto& nickname : room->finishOrder) {
            msg += nickname + "|";
        }
        msg += "\n"; 
        std::cout << "Broadcasting end: " << msg << std::endl;
        room->broadcast(msg, [this](int socket) { disconnectClient(socket); });
        room->gameStarted = false;
        room->finishOrder.clear();
        for (auto player : room->players) {
            player->position = 0.0;
        }
    }

    void disconnectClient(int clientSocket) {
        auto playerIt = players.find(clientSocket);
        if (playerIt != players.end()) {
            Player* player = playerIt->second;
            std::cout << "[SERVER] Player '" << player->nickname << "' disconnected" << std::endl;

            for (auto& roomPair : rooms) {
                Room* room = roomPair.second;
                room->removePlayer(player);
                if (room->players.empty()) {
                    delete room;
                    rooms.erase(roomPair.first);
                    break;
                }
            }
            players.erase(playerIt);
            delete player;
        }
        close(clientSocket);
    }

    void cleanupRooms() {
        std::vector<int> roomsToRemove;
        for (const auto& pair : rooms) {
            if (pair.second->players.empty()) {
                roomsToRemove.push_back(pair.first);
            }
        }
        
        for (int roomId : roomsToRemove) {
            delete rooms[roomId];
            rooms.erase(roomId);
        }
    }
};


int main() {
    try {
        int port = readPortFromConfig();
        std::cout << "Starting server on port " << port << std::endl;
        TypeRacerServer server;
        server.start(port);
    }
    catch (const std::exception& e) {
        std::cerr << "Server error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}