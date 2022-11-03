from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from stockfish import Stockfish
import pyautogui
import time
import sys
import os
import chess
import re
from utilities import char_to_num, attach_to_session


class StockfishBot:
	def __init__(self, url, session_id):
		self.url = url
		self.session_id = session_id
		self.chrome = None
		self.board_elem = None
		self.is_white = None

	# Sets the self.board_elem variable
	def update_board_elem(self):
		try:
			self.board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personalities']")
			return
		except NoSuchElementException:
			try:
				self.board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-single']")
				return
			except NoSuchElementException:
				self.board_elem = None
				return

	# Sets the self.is_white variable
	# True if white, False if black, None if the color is not found
	def update_player_color(self):
		# Find the square names list
		square_names = None
		try:
			square_names = self.chrome.find_elements(By.XPATH, "//*[@id='board-vs-personalities']//*[name()='svg']//*")
		except NoSuchElementException:
			try:
				square_names = self.chrome.find_elements(By.XPATH, "//*[@id='board-single']//*[name()='svg']//*")
			except NoSuchElementException:
				self.is_white = None
				return

		# Find the square with the smallest x and biggest y values (bottom left number)
		elem = None
		min_x = None
		max_y = None
		for i in range(len(square_names)):
			name_element = square_names[i]
			x = float(name_element.get_attribute("x"))
			y = float(name_element.get_attribute("y"))

			if i == 0 or (x <= min_x and y >= max_y):
				min_x = x
				max_y = y
				elem = name_element

		# Use this square to determine whether the player is white or black
		num = elem.text
		if num == "1":
			self.is_white = True
		else:
			self.is_white = False

	# Checks if the game over window popup is open
	# Returns True if it is, False if it isn't
	def is_game_over(self):
		try:
			# Find the game over window
			game_over_window = self.chrome.find_element(By.CLASS_NAME, "board-modal-container")
			if game_over_window is not None:
				return True
			else:
				return False
		except NoSuchElementException:
			# Return False since the game over window is not found
			return False

	# Converts a move to screen coordinates
	# Example: "a1" -> (x, y)
	def move_to_screen_pos(self, move):
		# Get the absolute top left corner of the website
		canvas_x_offset = self.chrome.execute_script("return window.screenX + (window.outerWidth - window.innerWidth) / 2 - window.scrollX;")
		canvas_y_offset = self.chrome.execute_script("return window.screenY + (window.outerHeight - window.innerHeight) - window.scrollY;")

		# Get the absolute board position
		board_x = canvas_x_offset + self.board_elem.location["x"]
		board_y = canvas_y_offset + self.board_elem.location["y"]

		# Get the square size
		square_size = self.board_elem.size['width'] / 8

		# Depending on the player color, the board is flipped, so the coordinates need to be adjusted
		x = None
		y = None
		if self.is_white:
			x = board_x + square_size * (char_to_num(move[0]) - 1) + square_size / 2
			y = board_y + square_size * (8 - int(move[1])) + square_size / 2
		else:
			x = board_x + square_size * (8 - char_to_num(move[0])) + square_size / 2
			y = board_y + square_size * (int(move[1]) - 1) + square_size / 2

		return x, y

	def make_move(self, move):
		# Get the start and end position screen coordinates
		start_pos_x, start_pos_y = self.move_to_screen_pos(move[0:2])
		end_pos_x, end_pos_y = self.move_to_screen_pos(move[2:4])

		# Move mouse to start position
		pyautogui.moveTo(start_pos_x, start_pos_y)

		# Click on start position and drag to end position
		pyautogui.dragTo(end_pos_x, end_pos_y, button='left')

		# Check for promotion. If there is a promotion,
		# promote to the corresponding piece type
		if len(move) == 5:
			time.sleep(0.1)
			if move[4] == "n":
				end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 1))
				pyautogui.dragTo(end_pos_x, end_pos_y, button='left')
			elif move[4] == "r":
				end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 2))
				pyautogui.dragTo(end_pos_x, end_pos_y, button='left')
			elif move[4] == "b":
				end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 3))
				pyautogui.dragTo(end_pos_x, end_pos_y, button='left')

			pyautogui.click(button='left')

	# Returns the current board move list
	# Ex. ["e4", "c5", "Nf3"]
	def get_move_list(self):
		# Move lines in bot games have different
		# structure than online games
		vs_bot = False

		# Find the moves list
		move_list_elem = None
		try:
			move_list_elem = self.chrome.find_element(By.XPATH, "/html/body/div[3]/div/vertical-move-list")
			vs_bot = True
		except NoSuchElementException:
			try:
				move_list_elem = self.chrome.find_element(By.XPATH, "//*[@id='move-list']/vertical-move-list")
			except NoSuchElementException:
				return None

		# Get a list with all the lines with the moves
		children = None
		try:
			children = move_list_elem.find_elements(By.XPATH, "./*")
		except NoSuchElementException:
			return None
		moves_list = []

		# Loop for every line in the moves list
		for moves_line in children:
			# Get the moves contained in that line
			try:
				moves = moves_line.find_elements(By.XPATH, "./*")
			except NoSuchElementException:
				return None

			# The second move index is different for
			# bot games and online games
			extra_index = []
			if len(moves) == 2 and vs_bot:
				extra_index = [1]
			elif len(moves) == 4 and not vs_bot:
				extra_index = [2]

			# Loop for every move in the line
			for i in [0] + extra_index:
				move = moves[i]

				# Find out if the move contains a piece character
				sub = None
				try:
					sub = move.find_elements(By.XPATH, "./*")
				except NoSuchElementException:
					return None

				if len(sub) == 0:
					moves_list.append(move.text)
				else:
					# Get the piece used to make the move
					piece = str(sub[0].get_attribute("data-figurine"))

					# Check if move was made with a piece or was en passant
					if piece == "None":
						moves_list.append(move.text)
					else:
						moves_list.append(piece + move.text)
		return moves_list

	# Starts the bot
	def run(self, pipe, stockfish_path, bongcloud, slow_mover):
		self.chrome = attach_to_session(self.url, self.session_id)

		# Initialize Stockfish
		parameters = {
			"Threads": 2,
			"Hash": 2048,
			"Ponder": "true",
			"Slow Mover": slow_mover,
		}
		try:
			stockfish = Stockfish(path=stockfish_path, parameters=parameters)
		except PermissionError:
			pipe.send("ERR_PERM")
			return
		except OSError:
			pipe.send("ERR_EXE")
			return

		try:
			# Return if the board element is not found
			self.update_board_elem()
			if self.board_elem is None:
				pipe.send("ERR_BOARD")
				return

			# Find out what color the player has
			self.update_player_color()
			if self.is_white is None:
				pipe.send("ERR_COLOR")
				return

			# Get the starting position
			# Return if the starting position is not found
			move_list = self.get_move_list()
			if move_list is None:
				pipe.send("ERR_MOVES")
				return

			# Check if the game is over
			score_pattern = r"([0-9]+)\-([0-9]+)"
			if len(move_list) > 0 and re.match(score_pattern, move_list[-1]):
				pipe.send("ERR_GAMEOVER")
				return

			# Update the board with the starting position
			board = chess.Board()
			for move in move_list:
				board.push_san(move)
			move_list_uci = [move.uci() for move in board.move_stack]

			# Update Stockfish with the starting position
			stockfish.set_position(move_list_uci)

			# Notify GUI that bot is ready
			pipe.send("START")

			# Send the first moves to the GUI (if there are any)
			if len(move_list) > 0:
				pipe.send("M_MOVE" + ",".join(move_list))

			# Start the game loop
			while True:
				# Act if it is the player's turn
				if (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK):
					# Think of a move
					move = None
					move_count = len(board.move_stack)
					if bongcloud and move_count <= 3:
						if move_count == 0:
							move = "e2e3"
						elif move_count == 1:
							move = "e7e6"
						elif move_count == 2:
							move = "e1e2"
						elif move_count == 3:
							move = "e8e7"

						# Hardcoded bongcloud move is not legal,
						# so find a legal move
						if not board.is_legal(chess.Move.from_uci(move)):
							move = stockfish.get_best_move()
					else:
						move = stockfish.get_best_move()
					move_san = board.san(chess.Move(chess.parse_square(move[0:2]), chess.parse_square(move[2:4])))

					# Make the move
					board.push_uci(move)
					stockfish.make_moves_from_current_position([move])
					move_list.append(move_san)
					self.make_move(move)

					# Send the move to the GUI
					pipe.send("S_MOVE" + move_san)

					# Check if the game is over
					if board.is_checkmate():
						return

					time.sleep(0.1)

				# Wait for a response from the opponent
				# by finding the differences between
				# the previous and current position
				previous_move_list = move_list
				while True:
					if self.is_game_over():
						return
					move_list = self.get_move_list()
					if move_list is None:
						return
					if len(move_list) > len(previous_move_list):
						break

				# Get the move that the opponent made
				move = move_list[-1]
				pipe.send("S_MOVE" + move)
				board.push_san(move)
				stockfish.make_moves_from_current_position([str(board.peek())])
				if board.is_checkmate():
					return
		except Exception as e:
			print(e)
			exc_type, exc_obj, exc_tb = sys.exc_info()
			fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
			print(exc_type, fname, exc_tb.tb_lineno)
