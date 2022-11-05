from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class ChesscomGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)

    def update_board_elem(self):
        try:
            self._board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personalities']")
        except NoSuchElementException:
            try:
                self._board_elem = self.chrome.find_element(By.XPATH, "//*[@id='board-single']")
            except NoSuchElementException:
                self._board_elem = None

    def update_player_color(self):
        # Find the square names list
        square_names = None
        try:
            coordinates = self.chrome.find_element(By.XPATH, "//*[@id='board-vs-personalities']//*[name()='svg']")
            square_names = coordinates.find_elements(By.XPATH, ".//*")
        except NoSuchElementException:
            try:
                coordinates = self.chrome.find_elements(By.XPATH, "//*[@id='board-single']//*[name()='svg']")
                coordinates = [x for x in coordinates if x.get_attribute("class") == "coordinates"][0]
                square_names = coordinates.find_elements(By.XPATH, ".//*")
            except NoSuchElementException:
                self._is_white = None
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
            self._is_white = True
        else:
            self._is_white = False

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
