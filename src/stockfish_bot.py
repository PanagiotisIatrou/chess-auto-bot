import multiprocess
from stockfish import Stockfish
import pyautogui
import time
import sys
import os
import chess
import re
from grabbers.chesscom_grabber import ChesscomGrabber
from grabbers.lichess_grabber import LichessGrabber
from utilities import char_to_num


class StockfishBot(multiprocess.Process):
    def __init__(self, chrome_url, chrome_session_id, website, pipe, stockfish_path, bongcloud, slow_mover):
        multiprocess.Process.__init__(self)

        self.chrome_url = chrome_url
        self.chrome_session_id = chrome_session_id
        self.website = website
        self.pipe = pipe
        self.stockfish_path = stockfish_path
        self.bongcloud = bongcloud
        self.slow_mover = slow_mover
        self.grabber = None

    # Converts a move to screen coordinates
    # Example: "a1" -> (x, y)
    def move_to_screen_pos(self, move):
        # Get the absolute top left corner of the website
        canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()

        # Get the absolute board position
        board_x = canvas_x_offset + self.grabber.get_board().location["x"]
        board_y = canvas_y_offset + self.grabber.get_board().location["y"]

        # Get the square size
        square_size = self.grabber.get_board().size['width'] / 8

        # Depending on the player color, the board is flipped, so the coordinates need to be adjusted
        x = None
        y = None
        if self.grabber.is_player_white():
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
            end_pos_x = None
            end_pos_y = None
            if move[4] == "n":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 1))
            elif move[4] == "r":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 2))
            elif move[4] == "b":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 3))

            pyautogui.moveTo(x=end_pos_x, y=end_pos_y)
            pyautogui.click(button='left')

    def run(self):
        if self.website == "chesscom":
            self.grabber = ChesscomGrabber(self.chrome_url, self.chrome_session_id)
        else:
            self.grabber = LichessGrabber(self.chrome_url, self.chrome_session_id)

        # Initialize Stockfish
        parameters = {
            "Threads": 2,
            "Hash": 2048,
            "Ponder": "true",
            "Slow Mover": self.slow_mover,
        }
        try:
            stockfish = Stockfish(path=self.stockfish_path, parameters=parameters)
        except PermissionError:
            self.pipe.send("ERR_PERM")
            return
        except OSError:
            self.pipe.send("ERR_EXE")
            return

        try:
            # Return if the board element is not found
            self.grabber.update_board_elem()
            if self.grabber.get_board() is None:
                self.pipe.send("ERR_BOARD")
                return

            # Find out what color the player has
            self.grabber.update_player_color()
            if self.grabber.is_player_white() is None:
                self.pipe.send("ERR_COLOR")
                return

            # Get the starting position
            # Return if the starting position is not found
            move_list = self.grabber.get_move_list()
            if move_list is None:
                self.pipe.send("ERR_MOVES")
                return

            # Check if the game is over
            score_pattern = r"([0-9]+)\-([0-9]+)"
            if len(move_list) > 0 and re.match(score_pattern, move_list[-1]):
                self.pipe.send("ERR_GAMEOVER")
                return

            # Update the board with the starting position
            board = chess.Board()
            for move in move_list:
                board.push_san(move)
            move_list_uci = [move.uci() for move in board.move_stack]

            # Update Stockfish with the starting position
            stockfish.set_position(move_list_uci)

            # Notify GUI that bot is ready
            self.pipe.send("START")

            # Send the first moves to the GUI (if there are any)
            if len(move_list) > 0:
                self.pipe.send("M_MOVE" + ",".join(move_list))

            # Start the game loop
            while True:
                # Act if it is the player's turn
                if (self.grabber.is_player_white() and board.turn == chess.WHITE) or (not self.grabber.is_player_white() and board.turn == chess.BLACK):
                    # Think of a move
                    move = None
                    move_count = len(board.move_stack)
                    if self.bongcloud and move_count <= 3:
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
                    self.pipe.send("S_MOVE" + move_san)

                    # Check if the game is over
                    if board.is_checkmate():
                        return

                    time.sleep(0.1)

                # Wait for a response from the opponent
                # by finding the differences between
                # the previous and current position
                previous_move_list = move_list
                while True:
                    if self.grabber.is_game_over():
                        return
                    move_list = self.grabber.get_move_list()
                    if move_list is None:
                        return
                    if len(move_list) > len(previous_move_list):
                        break

                # Get the move that the opponent made
                move = move_list[-1]
                self.pipe.send("S_MOVE" + move)
                board.push_san(move)
                stockfish.make_moves_from_current_position([str(board.peek())])
                if board.is_checkmate():
                    return
        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
