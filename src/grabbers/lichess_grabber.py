import re

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By

from grabbers.grabber import Grabber


class LichessGrabber(Grabber):
    def __init__(self, chrome_url, chrome_session_id):
        super().__init__(chrome_url, chrome_session_id)
        self.tag_name = None
        self.moves_list = {}

    def update_board_elem(self):
        try:
            # Try finding the normal board
            self._board_elem = self.chrome.find_element(By.XPATH,
                                                        '//*[@id="main-wrap"]/main/div[1]/div[1]/div/cg-container')
        except NoSuchElementException:
            try:
                # Try finding the board in the puzzles page
                self._board_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[1]/div/cg-container')
            except NoSuchElementException:
                self._board_elem = None

    def is_white(self):
        # Get "ranks" child
        children = self._board_elem.find_elements(By.XPATH, "./*")
        child = [x for x in children if "ranks" in x.get_attribute("class")][0]
        if child.get_attribute("class") == "ranks":
            return True
        else:
            return False

    def is_game_over(self):
        try:
            # Find the game over window
            self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/aside/div/section[2]')

            # If we don't have an exception at this point, we have found the game over window
            return True
        except NoSuchElementException:
            # Try finding the puzzles game over window and checking its class
            try:
                # The game over window
                game_over_window = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[3]/div[1]')

                if game_over_window.get_attribute("class") == "complete":
                    return True

                # If we don't have an exception at this point and the window's class is not "complete",
                # then the game is still going
                return False
            except NoSuchElementException:
                return False

    def set_moves_tag_name(self):
        if self.is_game_puzzles():
            return False

        move_list_elem = self.get_normal_move_list_elem()

        if move_list_elem is None or move_list_elem == []:
            return False

        try:
            last_child = move_list_elem.find_element(By.XPATH, "*[last()]")
            self.tag_name = last_child.tag_name

            return True
        except NoSuchElementException:
            return False

    def get_move_list(self):
        is_puzzles = self.is_game_puzzles()

        # Find the move list element
        if is_puzzles:
            move_list_elem = self.get_puzzles_move_list_elem()

            if move_list_elem is None:
                return None
        else:
            move_list_elem = self.get_normal_move_list_elem()

            if move_list_elem is None:
                return None
            if (not move_list_elem) or (self.tag_name is None and self.set_moves_tag_name() is False):
                return []

        # Get the move elements (children of the move list element)
        try:
            if not is_puzzles:
                if not self.moves_list:
                    # If the moves list is empty, find all moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, self.tag_name)
                else:
                    # If the moves list is not empty, find only the new moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, self.tag_name + ":not([data-processed])")
            else:
                if not self.moves_list:
                    # If the moves list is empty, find all moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, "move")
                else:
                    # If the moves list is not empty, find only the new moves
                    children = move_list_elem.find_elements(By.CSS_SELECTOR, "move:not([data-processed])")
        except NoSuchElementException:
            return None

        # Get the moves from the elements
        for move_element in children:
            # Sanitize the move
            move = re.sub(r"[^a-zA-Z0-9+-]", "", move_element.text)
            if move != "":
                self.moves_list[move_element.id] = move

            # Mark the move as processed
            self.chrome.execute_script("arguments[0].setAttribute('data-processed', 'true')", move_element)

        return [val for val in self.moves_list.values()]

    def get_puzzles_move_list_elem(self):
        try:
            # Try finding the move list in the puzzles page
            move_list_elem = self.chrome.find_element(By.XPATH, '/html/body/div[2]/main/div[2]/div[2]/div')

            return move_list_elem
        except NoSuchElementException:
            return None

    def get_normal_move_list_elem(self):
        try:
            # Try finding the normal move list
            move_list_elem = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6/l4x')

            return move_list_elem
        except NoSuchElementException:
            try:
                # Try finding the normal move list when there are no moves yet
                self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[1]/rm6')

                # If we don't have an exception at this point, we don't have any moves yet
                return []
            except NoSuchElementException:
                return None

    def is_game_puzzles(self):
        try:
            # Try finding the puzzles text
            self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/aside/div[1]/div[1]/div/p[1]")

            # If we don't have an exception at this point, the game is a puzzle
            return True
        except NoSuchElementException:
            return False

    def click_puzzle_next(self):
        # Find the next continue training button
        try:
            next_button = self.chrome.find_element(By.XPATH, "/html/body/div[2]/main/div[2]/div[3]/a")
        except NoSuchElementException:
            try:
                next_button = self.chrome.find_element(By.XPATH, '//*[@id="main-wrap"]/main/div[2]/div[3]/div[3]/a[2]')
            except NoSuchElementException:
                return

        # Click the continue training button
        self.chrome.execute_script("arguments[0].click();", next_button)

    def make_mouseless_move(self, move, move_count):
        message = '{"t":"move","d":{"u":"' + move + '","b":1,"a":' + str(move_count) + '}}'
        script = 'lichess.socket.ws.send(JSON.stringify(' + message + '))'
        self.chrome.execute_script(script)
