CXX = g++
CXXFLAGS = -std=c++11 -Wall -Wextra

SERVER = serwer
SERVER_SRC = $(SERVER).cpp

all: $(SERVER) install_python_packages

$(SERVER): $(SERVER_SRC)
	$(CXX) $(CXXFLAGS) -o $@ $<

install_python_packages:
	sudo apt install python3-PyQt5.QtSvg
	sudo apt install python3-pyqt5

clean:
	rm -f $(SERVER)

.PHONY: all clean install_python_packages