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
import keyboard


class StockfishBot(multiprocess.Process):
    def __init__(self, chrome_url, chrome_session_id, website, pipe, overlay_queue, stockfish_path, enable_manual_mode, enable_mouseless_mode, enable_non_stop_puzzles, enable_non_stop_matches, mouse_latency, bongcloud, slow_mover, skill_level, stockfish_depth, memory, cpu_threads):
        multiprocess.Process.__init__(self)

        self.chrome_url = chrome_url
        self.chrome_session_id = chrome_session_id
        self.website = website
        self.pipe = pipe
        self.overlay_queue = overlay_queue
        self.stockfish_path = stockfish_path
        self.enable_manual_mode = enable_manual_mode
        self.enable_mouseless_mode = enable_mouseless_mode
        self.enable_non_stop_puzzles = enable_non_stop_puzzles
        self.enable_non_stop_matches = enable_non_stop_matches
        self.mouse_latency = mouse_latency
        self.bongcloud = bongcloud
        self.slow_mover = slow_mover
        self.skill_level = skill_level
        self.stockfish_depth = stockfish_depth
        self.grabber = None
        self.memory = memory
        self.cpu_threads = cpu_threads
        self.is_white = None

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
        if self.is_white:
            x = board_x + square_size * (char_to_num(move[0]) - 1) + square_size / 2
            y = board_y + square_size * (8 - int(move[1])) + square_size / 2
        else:
            x = board_x + square_size * (8 - char_to_num(move[0])) + square_size / 2
            y = board_y + square_size * (int(move[1]) - 1) + square_size / 2

        return x, y

    def get_move_pos(self, move):  # sourcery skip: remove-redundant-slice-index
        # Get the start and end position screen coordinates
        start_pos_x, start_pos_y = self.move_to_screen_pos(move[0:2])
        end_pos_x, end_pos_y = self.move_to_screen_pos(move[2:4])

        return (start_pos_x, start_pos_y), (end_pos_x, end_pos_y)


    def make_move(self, move):  # sourcery skip: extract-method
        # Get the start and end position screen coordinates
        start_pos, end_pos = self.get_move_pos(move)

        # Drag the piece from the start to the end position
        pyautogui.moveTo(start_pos[0], start_pos[1])
        time.sleep(self.mouse_latency)
        pyautogui.dragTo(end_pos[0], end_pos[1])

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

    def wait_for_gui_to_delete(self):
        while self.pipe.recv() != "DELETE":
            pass

    def go_to_next_puzzle(self):
        self.grabber.click_puzzle_next()
        self.pipe.send("RESTART")
        self.wait_for_gui_to_delete()

    def find_new_online_match(self):
        time.sleep(2)
        self.grabber.click_game_next()
        self.pipe.send("RESTART")
        self.wait_for_gui_to_delete()

    def run(self):
        # sourcery skip: extract-duplicate-method, switch, use-fstring-for-concatenation
        if self.website == "chesscom":
            self.grabber = ChesscomGrabber(self.chrome_url, self.chrome_session_id)
        else:
            self.grabber = LichessGrabber(self.chrome_url, self.chrome_session_id)
            
        # Reset the grabber's moves list to ensure a clean start
        self.grabber.reset_moves_list()

        # Initialize Stockfish
        parameters = {
            "Threads": self.cpu_threads,
            "Hash": self.memory,
            "Ponder": "true",
            "Slow Mover": self.slow_mover,
            "Skill Level": self.skill_level
        }
        try:
            stockfish = Stockfish(path=self.stockfish_path, depth=self.stockfish_depth, parameters=parameters)
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
            self.is_white = self.grabber.is_white()
            if self.is_white is None:
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
            
            # Track player moves and best moves for accuracy calculation
            white_moves = []
            white_best_moves = []
            black_moves = []
            black_best_moves = []
            
            # Send initial evaluation, WDL, and material data to GUI
            self.send_eval_data(stockfish, board)

            # Notify GUI that bot is ready
            self.pipe.send("START")

            # Send the first moves to the GUI (if there are any)
            if len(move_list) > 0:
                self.pipe.send("M_MOVE" + ",".join(move_list))

            # Start the game loop
            while True:
                # Act if it is the player's turn
                if (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK):
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
                    
                    # Store best move for accuracy calculation
                    if board.turn == chess.WHITE:
                        white_best_moves.append(move)
                    else:
                        black_best_moves.append(move)

                    # Wait for keypress or player movement if in manual mode
                    self_moved = False
                    if self.enable_manual_mode:
                        move_start_pos, move_end_pos = self.get_move_pos(move)
                        self.overlay_queue.put([
                            ((int(move_start_pos[0]), int(move_start_pos[1])), (int(move_end_pos[0]), int(move_end_pos[1]))),
                        ])
                        while True:
                            if keyboard.is_pressed("3"):
                                break

                            if len(move_list) != len(self.grabber.get_move_list()):
                                self_moved = True
                                move_list = self.grabber.get_move_list()
                                move_san = move_list[-1]
                                move = board.parse_san(move_san).uci()
                                # Store actual move for accuracy calculation
                                if board.turn == chess.WHITE:
                                    white_moves.append(move)
                                else:
                                    black_moves.append(move)
                                board.push_uci(move)
                                stockfish.make_moves_from_current_position([move])
                                break

                    if not self_moved:
                        move_san = board.san(chess.Move(chess.parse_square(move[0:2]), chess.parse_square(move[2:4])))
                        # Store actual move for accuracy calculation
                        if board.turn == chess.WHITE:
                            white_moves.append(move)
                        else:
                            black_moves.append(move)
                        board.push_uci(move)
                        stockfish.make_moves_from_current_position([move])
                        move_list.append(move_san)
                        if self.enable_mouseless_mode and not self.grabber.is_game_puzzles():
                            self.grabber.make_mouseless_move(move, move_count + 1)
                        else:
                            self.make_move(move)

                    self.overlay_queue.put([])

                    # Send evaluation, WDL, and material data to GUI
                    self.send_eval_data(stockfish, board, white_moves, white_best_moves, black_moves, black_best_moves)

                    # Send the move to the GUI
                    self.pipe.send("S_MOVE" + move_san)

                    # Check if the game is over
                    if board.is_checkmate():
                        # Send restart message to GUI
                        if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                            self.go_to_next_puzzle()
                        elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                            self.find_new_online_match()
                        return

                    time.sleep(0.1)

                # Wait for a response from the opponent
                # by finding the differences between
                # the previous and current position
                previous_move_list = move_list.copy()
                while True:
                    if self.grabber.is_game_over():
                        # Send restart message to GUI
                        if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                            self.go_to_next_puzzle()
                        elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                            self.find_new_online_match()
                        return
                    
                    # Get fresh move list from the grabber and check if it's a new game
                    new_move_list = self.grabber.get_move_list()
                    if new_move_list is None:
                        return
                        
                    # Check if this is a completely new game (moves reset to 0)
                    if len(new_move_list) == 0 and len(move_list) > 0:
                        # Reset everything for the new game
                        move_list = []
                        board = chess.Board()
                        stockfish.set_position([])
                        # Reset accuracy tracking
                        white_moves = []
                        white_best_moves = []
                        black_moves = []
                        black_best_moves = []
                        # Find out what color the player has for the new game
                        self.is_white = self.grabber.is_white()
                        self.pipe.send("RESTART")
                        self.wait_for_gui_to_delete()
                        # Send initial evaluation, WDL, and material data to GUI
                        self.send_eval_data(stockfish, board)
                        self.pipe.send("START")
                        break
                        
                    # Normal case - opponent made a move
                    if len(new_move_list) > len(previous_move_list):
                        move_list = new_move_list
                        break

                # Get the move that the opponent made
                move = move_list[-1]
                # Get UCI version of the move for accuracy tracking
                prev_board = board.copy()
                board.push_san(move)
                move_uci = prev_board.parse_san(move).uci()
                
                # Store actual move for accuracy calculation
                if prev_board.turn == chess.WHITE:
                    white_moves.append(move_uci)
                else:
                    black_moves.append(move_uci)
                
                # Get and store the best move that should have been played
                best_move = stockfish.get_best_move_time(300)  # Get best move with 300ms of thinking time
                if prev_board.turn == chess.WHITE:
                    white_best_moves.append(best_move)
                else:
                    black_best_moves.append(best_move)
                
                # Send evaluation, WDL, and material data to GUI
                stockfish.make_moves_from_current_position([str(board.peek())])
                self.send_eval_data(stockfish, board, white_moves, white_best_moves, black_moves, black_best_moves)
                
                # Send the move to the GUI
                self.pipe.send("S_MOVE" + move)
                
                if board.is_checkmate():
                    # Send restart message to GUI
                    if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                        self.go_to_next_puzzle()
                    elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                        self.find_new_online_match()
                    return
        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    def send_eval_data(self, stockfish, board, white_moves=None, white_best_moves=None, black_moves=None, black_best_moves=None):
        """Send evaluation, WDL, and material data to GUI"""
        try:
            # Get evaluation
            eval_data = stockfish.get_evaluation()
            eval_type = eval_data['type']
            eval_value = eval_data['value']
            
            # Convert evaluation to player's perspective if playing as black
            # Stockfish eval is always from white's perspective (+ve for white, -ve for black)
            player_perspective_eval_value = eval_value
            if not self.is_white:
                player_perspective_eval_value = -eval_value  # Negate to get black's perspective
            
            # Get WDL stats if available
            try:
                wdl_stats = stockfish.get_wdl_stats()
            except:
                wdl_stats = [0, 0, 0]
                
            # Calculate material advantage (basic version)
            material = self.calculate_material_advantage(board)
            
            # Calculate accuracy if enough moves
            white_accuracy = "-"
            black_accuracy = "-"
            if white_moves and white_best_moves and len(white_moves) > 0 and len(white_moves) == len(white_best_moves):
                matches = sum(1 for a, b in zip(white_moves, white_best_moves) if a == b)
                white_accuracy = f"{matches / len(white_moves) * 100:.1f}%"
            
            if black_moves and black_best_moves and len(black_moves) > 0 and len(black_moves) == len(black_best_moves):
                matches = sum(1 for a, b in zip(black_moves, black_best_moves) if a == b)
                black_accuracy = f"{matches / len(black_moves) * 100:.1f}%"
            
            # Format evaluation string from player's perspective
            if eval_type == "cp":
                eval_str = f"{player_perspective_eval_value/100:.2f}"
                # Convert centipawns to decimal value for the eval bar
                eval_value_decimal = player_perspective_eval_value/100
            else:  # mate
                eval_str = f"M{player_perspective_eval_value}"
                eval_value_decimal = player_perspective_eval_value  # Keep mate score as is
            
            # Format WDL string (win/draw/loss percentages)
            total = sum(wdl_stats)
            if total > 0:
                # WDL from Stockfish is from perspective of player to move
                # Need to invert if it's opponent's turn
                is_bot_turn = (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK)
                
                if is_bot_turn:
                    win_pct = wdl_stats[0] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[2] / total * 100
                else:
                    # Invert the win/loss when it's opponent's turn
                    win_pct = wdl_stats[2] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[0] / total * 100
                
                wdl_str = f"{win_pct:.1f}/{draw_pct:.1f}/{loss_pct:.1f}"
            else:
                wdl_str = "?/?/?"
            
            # Determine bot and opponent accuracies based on bot's color
            bot_accuracy = white_accuracy if self.is_white else black_accuracy
            opponent_accuracy = black_accuracy if self.is_white else white_accuracy
            
            # Send data to GUI
            data = f"EVAL|{eval_str}|{wdl_str}|{material}|{bot_accuracy}|{opponent_accuracy}"
            self.pipe.send(data)
            
            # Send evaluation data to overlay
            overlay_data = {
                "eval": eval_value_decimal,
                "eval_type": eval_type
            }
            
            # Add board position and dimensions for the eval bar positioning
            board_elem = self.grabber.get_board()
            if board_elem:
                # Get the absolute top left corner of the website
                canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()
                
                # Calculate absolute board position and dimensions
                overlay_data["board_position"] = {
                    'x': canvas_x_offset + board_elem.location['x'],
                    'y': canvas_y_offset + board_elem.location['y'],
                    'width': board_elem.size['width'],
                    'height': board_elem.size['height']
                }
                
            # Always include the bot's color
            overlay_data["is_white"] = self.is_white
            
            self.overlay_queue.put(overlay_data)
            
        except Exception as e:
            print(f"Error sending evaluation: {e}")
    
    def calculate_material_advantage(self, board):
        """Calculate material advantage in the position"""
        piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9
        }
        
        white_material = 0
        black_material = 0
        
        for piece_type in piece_values:
            white_material += len(board.pieces(piece_type, chess.WHITE)) * piece_values[piece_type]
            black_material += len(board.pieces(piece_type, chess.BLACK)) * piece_values[piece_type]
        
        advantage = white_material - black_material
        if advantage > 0:
            return f"+{advantage}"
        elif advantage < 0:
            return str(advantage)
        else:
            return "0"
